"""
Anchor - session builder

Takes real wrist-worn accelerometer + gyroscope recordings from a single
training session (participant A, 2019-01-11, from the SmartLift-Analysis-Project
open dataset, itself a rebuild of a Vrije Universiteit Amsterdam wearable
strength-training study) and:

  1. Stitches 12 real sets (bench / overhead press / squat / deadlift) into
     one continuous session timeline, in the order they actually happened.
  2. Compresses real inter-set rest gaps into a demo-friendly range while
     keeping their *relative* lengths (a 24-minute real gap should still be
     the longest rest in the session, just not 24 minutes long on screen).
  3. Injects synthetic BLE dropouts and sampling jitter on top of the real
     signal. This is the one part of the pipeline that is not observed data,
     and it is the only part meant to model failure, not fitness.
  4. Reconstructs the gaps with interpolation, the way a real ingest
     pipeline has to, so the stream stays continuous for whatever sits
     downstream of it.
  5. Scores confidence per sample: distance from the nearest real reading,
     how volatile the signal was right before the gap opened, and how large
     the jump is between the real sample before and after the gap.

Everything upstream of step 3 is real sensor data. Everything from step 3
onward is engineered, and is documented as such in the README.
"""

import json
import re
from pathlib import Path

import numpy as np
import pandas as pd

RAW_DIR = Path(__file__).parent.parent / "data" / "raw" / "MetaMotion"
OUT_PATH = Path(__file__).parent.parent / "output" / "session.json"

RESAMPLE_HZ = 10  # common grid both sensors get resampled onto
REST_COMPRESSION = 0.05  # real inter-set gap * this factor
REST_MIN_S = 15
REST_MAX_S = 60

FILE_RE = re.compile(
    r"^([A-E])-([a-z]+)-([a-z0-9\-]+)_MetaWear_"
    r"(\d{4}-\d{2}-\d{2})T(\d{2}\.\d{2}\.\d{2}\.\d+)_\w+_"
    r"(Accelerometer|Gyroscope)_(\d+\.\d+)Hz"
)

rng = np.random.default_rng(7)


def discover_sets():
    """Group the 24 raw files into 12 (accel, gyro) set pairs, in real
    chronological order."""
    by_key = {}
    for f in RAW_DIR.iterdir():
        m = FILE_RE.match(f.name)
        if not m:
            continue
        participant, exercise, category, date, time_str, sensor, hz = m.groups()
        key = (exercise, category)
        by_key.setdefault(key, {})[sensor] = f

    sets = []
    for (exercise, category), files in by_key.items():
        if "Accelerometer" not in files or "Gyroscope" not in files:
            continue  # need both sensors for this set
        acc = pd.read_csv(files["Accelerometer"])
        gyr = pd.read_csv(files["Gyroscope"])
        start_epoch_ms = acc["epoch (ms)"].iloc[0]
        sets.append(
            {
                "exercise": exercise,
                "category": category,
                "label": f"{exercise}-{category}",
                "start_epoch_ms": int(start_epoch_ms),
                "acc": acc,
                "gyr": gyr,
            }
        )
    sets.sort(key=lambda s: s["start_epoch_ms"])
    return sets


def resample_set(acc, gyr):
    """Put accel (12.5Hz) and gyro (25Hz) on one common time grid, relative
    to the start of this set, in seconds."""
    acc = acc.rename(
        columns={"x-axis (g)": "acc_x", "y-axis (g)": "acc_y", "z-axis (g)": "acc_z"}
    )
    gyr = gyr.rename(
        columns={
            "x-axis (deg/s)": "gyr_x",
            "y-axis (deg/s)": "gyr_y",
            "z-axis (deg/s)": "gyr_z",
        }
    )
    acc["t"] = (acc["epoch (ms)"] - acc["epoch (ms)"].iloc[0]) / 1000.0
    gyr["t"] = (gyr["epoch (ms)"] - gyr["epoch (ms)"].iloc[0]) / 1000.0

    duration = min(acc["t"].iloc[-1], gyr["t"].iloc[-1])
    if duration < 1.0:
        return None  # too short to be worth including

    grid = np.arange(0, duration, 1.0 / RESAMPLE_HZ)
    out = pd.DataFrame({"t": grid})
    for col in ["acc_x", "acc_y", "acc_z"]:
        out[col] = np.interp(grid, acc["t"], acc[col])
    for col in ["gyr_x", "gyr_y", "gyr_z"]:
        out[col] = np.interp(grid, gyr["t"], gyr[col])

    out["acc_r"] = np.sqrt(out.acc_x**2 + out.acc_y**2 + out.acc_z**2)
    out["gyr_r"] = np.sqrt(out.gyr_x**2 + out.gyr_y**2 + out.gyr_z**2)
    return out


def build_stitched_session(sets):
    """Concatenate resampled sets with compressed rest gaps between them."""
    rows = []
    cursor = 0.0
    prev_start_epoch = None

    for i, s in enumerate(sets):
        resampled = resample_set(s["acc"], s["gyr"])
        if resampled is None:
            continue

        if prev_start_epoch is not None:
            real_gap_s = (s["start_epoch_ms"] - prev_start_epoch) / 1000.0
            rest_s = float(
                np.clip(real_gap_s * REST_COMPRESSION, REST_MIN_S, REST_MAX_S)
            )
            rest_grid = np.arange(0, rest_s, 1.0 / RESAMPLE_HZ)
            for rt in rest_grid:
                rows.append(
                    {
                        "t": cursor + rt,
                        "acc_x": 0.0, "acc_y": 1.0, "acc_z": 0.0,
                        "gyr_x": 0.0, "gyr_y": 0.0, "gyr_z": 0.0,
                        "acc_r": 1.0, "gyr_r": 0.0,
                        "label": "rest",
                        "real_gap_compressed_from_s": round(real_gap_s, 1),
                    }
                )
            cursor += rest_s

        resampled["label"] = s["label"]
        resampled["real_gap_compressed_from_s"] = None
        resampled["t"] = resampled["t"] + cursor
        rows.extend(resampled.to_dict("records"))
        cursor = resampled["t"].iloc[-1] + 1.0 / RESAMPLE_HZ
        prev_start_epoch = s["start_epoch_ms"]

    df = pd.DataFrame(rows).reset_index(drop=True)
    df["is_real"] = True
    return df


def inject_dropouts(df):
    """Randomly drop chunks of samples, weighted toward high-motion moments,
    the way a BLE radio actually behaves on a moving wrist."""
    n = len(df)
    dropped = np.zeros(n, dtype=bool)

    motion = (df["acc_r"] - 1.0).abs().to_numpy()
    motion_norm = motion / (motion.max() + 1e-9)
    hazard = 0.003 + 0.03 * motion_norm  # per-sample dropout onset chance

    i = 0
    while i < n:
        if rng.random() < hazard[i] and not dropped[i]:
            gap_s = float(np.clip(rng.lognormal(mean=-0.6, sigma=0.6), 0.3, 3.0))
            gap_samples = max(1, int(gap_s * RESAMPLE_HZ))
            end = min(n, i + gap_samples)
            dropped[i:end] = True
            i = end
        else:
            i += 1

    df["is_real"] = ~dropped
    return df


def reconstruct_and_score(df):
    """Linear-interpolate through the dropped samples, then score confidence
    per sample."""
    cols = ["acc_x", "acc_y", "acc_z", "gyr_x", "gyr_y", "gyr_z"]
    raw = df[cols].copy()
    raw[~df["is_real"]] = np.nan
    interpolated = raw.interpolate(method="linear", limit_direction="both")
    for c in cols:
        df[c + "_recon"] = interpolated[c]
    df["acc_r_recon"] = np.sqrt(
        df.acc_x_recon**2 + df.acc_y_recon**2 + df.acc_z_recon**2
    )
    df["gyr_r_recon"] = np.sqrt(
        df.gyr_x_recon**2 + df.gyr_y_recon**2 + df.gyr_z_recon**2
    )

    n = len(df)
    is_real = df["is_real"].to_numpy()
    confidence = np.ones(n)

    # distance (in seconds) to nearest real sample, for reconstructed points
    dist_prev = np.full(n, np.inf)
    last_real = -np.inf
    for i in range(n):
        if is_real[i]:
            last_real = i
        dist_prev[i] = (i - last_real) / RESAMPLE_HZ

    dist_next = np.full(n, np.inf)
    next_real = np.inf
    for i in range(n - 1, -1, -1):
        if is_real[i]:
            next_real = i
        dist_next[i] = (next_real - i) / RESAMPLE_HZ

    dist_to_real = np.minimum(dist_prev, dist_next)

    # pre-gap volatility: std of real acc_r in the 1s window right before
    # each gap started, broadcast across that whole gap. A gap that opens
    # mid-rep (volatile) is a worse bet than one that opens during a still
    # moment (top/bottom pause, or rest).
    acc_r = df["acc_r"].to_numpy()
    gap_ids = np.cumsum(np.diff(np.concatenate([[1], is_real.astype(int)])) != 0)
    vol_penalty = np.ones(n)
    for gid in np.unique(gap_ids[~is_real]):
        idx = np.where((gap_ids == gid) & (~is_real))[0]
        if len(idx) == 0:
            continue
        start = idx[0]
        window_start = max(0, start - int(1.0 * RESAMPLE_HZ))
        pre_window = acc_r[window_start:start]
        pre_window = pre_window[~np.isnan(pre_window)]
        if len(pre_window) > 1:
            local_std = np.std(pre_window)
            vol_penalty[idx] = np.clip(1.0 - local_std / 1.2, 0.45, 1.0)

    # turning-point check: linear interpolation draws a straight line
    # through a gap. If the signal's slope reverses sign from just before
    # the gap to just after it, a peak or trough (e.g. the bottom of a
    # squat) almost certainly happened inside the gap, and the straight
    # line silently missed it. That is a structurally different failure
    # from "slightly wrong values" and gets penalized hard.
    edge_penalty = np.ones(n)
    for gid in np.unique(gap_ids[~is_real]):
        idx = np.where((gap_ids == gid) & (~is_real))[0]
        if len(idx) == 0:
            continue
        before, after = idx[0] - 1, idx[-1] + 1
        if before >= 1 and after < n - 1:
            slope_before = acc_r[before] - acc_r[before - 1]
            slope_after = acc_r[after + 1] - acc_r[after]
            if slope_before * slope_after < 0:
                edge_penalty[idx] = 0.3  # likely turning point inside the gap
            else:
                edge_penalty[idx] = 0.9  # monotonic continuation, plausible

    dist_conf = np.exp(-dist_to_real / 1.0)
    confidence = np.where(
        is_real, 1.0, np.clip(dist_conf * vol_penalty * edge_penalty, 0.02, 0.98)
    )

    df["confidence"] = confidence
    df["dist_to_real_s"] = np.where(is_real, 0.0, dist_to_real)
    df["turning_point_flag"] = (~is_real) & (edge_penalty < 0.5)
    return df


def count_reps(df):
    """Peak-count reps per set on the reconstructed stream, the same signal
    a downstream model would actually see. Each rep gets a confidence score
    pulled straight from the per-sample scores already computed, and a plain
    explanation when a dropout landed on a likely turning point inside it."""
    from scipy.signal import butter, filtfilt, find_peaks

    min_distance = int(1.4 * RESAMPLE_HZ)
    b, a = butter(4, 1.2 / (RESAMPLE_HZ / 2), btype="low")

    sets_out = []
    for label in df["label"].unique():
        if label == "rest":
            continue
        sub = df[df["label"] == label].reset_index(drop=True)
        if len(sub) < min_distance * 2:
            continue

        signal = sub["acc_r_recon"].to_numpy()
        filtered = filtfilt(b, a, signal)
        peaks, _ = find_peaks(filtered, distance=min_distance, prominence=0.15)

        half = min_distance // 2
        reps = []
        for p in peaks:
            lo, hi = max(0, p - half), min(len(sub), p + half)
            window = sub.iloc[lo:hi]
            conf = float(window["confidence"].mean())
            turning_flag = bool(window["turning_point_flag"].any())
            has_recon = bool((~window["is_real"]).any())

            explanation = None
            if turning_flag:
                explanation = (
                    "A sensor dropout landed right at a likely turning point in "
                    "this rep, so the exact bottom or top of the movement is a "
                    "reconstructed guess, not a direct reading."
                )
            elif has_recon and conf < 0.6:
                explanation = (
                    "Part of this rep was reconstructed from a short sensor "
                    "gap, so this rep's numbers are a lower-confidence estimate."
                )

            # Product decision: a rep below 0.6 confidence does not count
            # toward a personal record. A record is a claim of evidence,
            # and a rep whose samples are partly reconstructed guesses is
            # not evidence. Streaks and volume totals are unaffected.
            counts_toward_pr = conf >= 0.6
            pr_reason = None
            if not counts_toward_pr:
                pr_reason = (
                    "Rep confidence is below 0.6 because part of this rep "
                    "was reconstructed after a sensor dropout, so it does "
                    "not count toward a personal record. It still counts "
                    "toward volume and streaks."
                )

            reps.append(
                {
                    "t": round(float(sub["t"].iloc[p]), 2),
                    "confidence": round(conf, 3),
                    "explanation": explanation,
                    "counts_toward_pr": counts_toward_pr,
                    "counts_toward_pr_reason": pr_reason,
                }
            )

        sets_out.append(
            {
                "label": label,
                "rep_count": len(reps),
                "mean_confidence": round(
                    float(np.mean([r["confidence"] for r in reps])) if reps else 1.0, 3
                ),
                "reps": reps,
            }
        )
    return sets_out


def main():
    sets = discover_sets()
    print(f"Discovered {len(sets)} real sets")
    df = build_stitched_session(sets)
    print(f"Stitched session: {len(df)} samples, {df['t'].iloc[-1]:.1f}s")
    df = inject_dropouts(df)
    dropped_frac = (~df["is_real"]).mean()
    print(f"Dropout injection: {dropped_frac*100:.1f}% of samples marked missing")
    df = reconstruct_and_score(df)
    print(f"Mean confidence overall: {df['confidence'].mean():.3f}")
    print(f"Mean confidence on reconstructed samples: {df.loc[~df.is_real, 'confidence'].mean():.3f}")

    sets_out = count_reps(df)
    total_reps = sum(s["rep_count"] for s in sets_out)
    flagged = sum(1 for s in sets_out for r in s["reps"] if r["explanation"])
    pr_excluded = sum(
        1 for s in sets_out for r in s["reps"] if not r["counts_toward_pr"]
    )
    print(f"Rep counting: {total_reps} reps detected across {len(sets_out)} sets, {flagged} flagged low-confidence")
    print(f"PR gate: {pr_excluded} reps excluded from personal records (confidence < 0.6)")
    for s in sets_out:
        print(f"  {s['label']:20s} reps={s['rep_count']:2d} mean_conf={s['mean_confidence']:.3f}")

    OUT_PATH.parent.mkdir(exist_ok=True)
    out = {
        "meta": {
            "participant": "A",
            "session_date": "2019-01-11",
            "source": "SmartLift-Analysis-Project (open dataset, wrist-worn MetaMotion sensor)",
            "resample_hz": RESAMPLE_HZ,
            "n_sets": len(sets),
            "duration_s": round(float(df["t"].iloc[-1]), 1),
            "dropout_fraction": round(float(dropped_frac), 4),
            "mean_confidence": round(float(df["confidence"].mean()), 4),
            "total_reps_detected": total_reps,
            "reps_flagged_low_confidence": flagged,
            "reps_excluded_from_pr": pr_excluded,
        },
        "sets": sets_out,
        "samples": [
            {
                "t": round(float(r.t), 2),
                "label": r.label,
                "is_real": bool(r.is_real),
                "acc_r": round(float(r.acc_r_recon), 4),
                "gyr_r": round(float(r.gyr_r_recon), 4),
                "confidence": round(float(r.confidence), 3),
            }
            for r in df.itertuples()
        ],
    }
    with open(OUT_PATH, "w") as f:
        json.dump(out, f)
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
