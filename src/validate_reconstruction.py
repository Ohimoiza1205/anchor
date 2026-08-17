"""
Anchor - reconstruction validator

build_session.py deletes samples itself (synthetic dropouts), so the true
value of every reconstructed sample is known. This script rebuilds the
session by calling the same functions in the same order as
build_session.main(), then measures reconstruction error on the held-out
true values and checks whether the confidence score tracks that error.

It never calls build_session.main(), so output/session.json is untouched.
"""

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.signal import butter, filtfilt, find_peaks
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).parent))

import build_session as bs


def rebuild():
    """Rerun the pipeline exactly as main() does, minus the JSON write.
    build_session's module-level rng = np.random.default_rng(7) is fresh on
    import, so inject_dropouts reproduces the committed dropout pattern."""
    sets = bs.discover_sets()
    df = bs.build_stitched_session(sets)
    df = bs.inject_dropouts(df)
    df = bs.reconstruct_and_score(df)
    return df


def rep_windows(df):
    """Replicate count_reps peak detection to recover each rep's window
    (peak index +/- half, half = int(1.4 * RESAMPLE_HZ) // 2) as row slices
    of the per-set sub-frame. Returned in the same order count_reps emits
    reps, so they align 1:1 with its output."""
    min_distance = int(1.4 * bs.RESAMPLE_HZ)
    b, a = butter(4, 1.2 / (bs.RESAMPLE_HZ / 2), btype="low")
    half = min_distance // 2

    windows = []
    for label in df["label"].unique():
        if label == "rest":
            continue
        sub = df[df["label"] == label].reset_index(drop=True)
        if len(sub) < min_distance * 2:
            continue
        signal = sub["acc_r_recon"].to_numpy()
        filtered = filtfilt(b, a, signal)
        peaks, _ = find_peaks(filtered, distance=min_distance, prominence=0.15)
        for p in peaks:
            lo, hi = max(0, p - half), min(len(sub), p + half)
            windows.append({"label": label, "peak_t": float(sub["t"].iloc[p]),
                            "window": sub.iloc[lo:hi]})
    return windows


def main():
    df = rebuild()

    n_total = len(df)
    dropped = df[~df["is_real"]]
    n_dropped = len(dropped)

    print("REPRODUCTION CHECK")
    print(f"total samples: {n_total}")
    print(f"dropped samples: {n_dropped}")
    assert n_total == 4766, f"expected 4766 total samples, got {n_total}"
    assert n_dropped == 155, f"expected 155 dropped samples, got {n_dropped}"
    print("assertions passed: totals match the committed session")
    print()

    acc_err = (dropped["acc_r"] - dropped["acc_r_recon"]).abs()
    gyr_err = (dropped["gyr_r"] - dropped["gyr_r_recon"]).abs()

    print("1. OVERALL ERROR (155 dropped samples)")
    print("acc_r (g):")
    print(f"  mean abs error:   {acc_err.mean():.4f}")
    print(f"  median abs error: {acc_err.median():.4f}")
    print(f"  p90 abs error:    {acc_err.quantile(0.9):.4f}")
    print(f"  max abs error:    {acc_err.max():.4f}")
    print("gyr_r (deg/s):")
    print(f"  mean abs error:   {gyr_err.mean():.4f}")
    print(f"  median abs error: {gyr_err.median():.4f}")
    print(f"  p90 abs error:    {gyr_err.quantile(0.9):.4f}")
    print(f"  max abs error:    {gyr_err.max():.4f}")
    print()

    print("2. ERROR BY CONFIDENCE BAND (abs acc_r error, g)")
    bands = [(0.0, 0.2), (0.2, 0.4), (0.4, 0.6), (0.6, 0.8), (0.8, 1.0)]
    conf = dropped["confidence"]
    for lo, hi in bands:
        if hi == 1.0:
            mask = (conf >= lo) & (conf <= hi)
            band_label = f"[{lo:.1f}-{hi:.1f}]"
        else:
            mask = (conf >= lo) & (conf < hi)
            band_label = f"[{lo:.1f}-{hi:.1f})"
        e = acc_err[mask]
        if len(e) == 0:
            print(f"  {band_label}: n=0")
        else:
            print(f"  {band_label}: n={len(e)}, mean={e.mean():.4f}, "
                  f"median={e.median():.4f}, max={e.max():.4f}")
    print()

    print("3. CORRELATION (across 155 dropped samples)")
    rho_conf, p_conf = spearmanr(conf, acc_err)
    rho_dist, p_dist = spearmanr(dropped["dist_to_real_s"], acc_err)
    print(f"  spearman(confidence, abs acc_r error):     rho={rho_conf:.4f}, p={p_conf:.4g}")
    print(f"  spearman(dist_to_real_s, abs acc_r error): rho={rho_dist:.4f}, p={p_dist:.4g}")
    if rho_conf < 0 and rho_dist > 0:
        print("  confidence is negatively correlated with error and "
              "dist_to_real_s is positively correlated with error, as designed")
    if abs(rho_dist) > abs(rho_conf):
        print("  dist_to_real_s tracks error more strongly than the combined "
              "confidence score does")
    else:
        print("  the combined confidence score tracks error more strongly "
              "than dist_to_real_s alone")
    print()

    print("4. TURNING POINT CHECK VALUE (abs acc_r error, g)")
    tp = dropped["turning_point_flag"]
    e_tp = acc_err[tp]
    e_no = acc_err[~tp]
    print(f"  turning_point_flag true:  n={len(e_tp)}, mean abs error={e_tp.mean():.4f}")
    print(f"  turning_point_flag false: n={len(e_no)}, mean abs error={e_no.mean():.4f}")
    if e_tp.mean() > e_no.mean():
        print("  flagged samples have higher mean error, so the 0.3 edge "
              "penalty is pointing at genuinely worse reconstructions")
    else:
        print("  flagged samples do not have higher mean error in this "
              "session, so the 0.3 edge penalty is not separating error here")
    print()

    print("5. REST VS IN-SET (abs acc_r error, g)")
    rest_mask = dropped["label"] == "rest"
    e_rest = acc_err[rest_mask]
    e_set = acc_err[~rest_mask]
    print(f"  rest:   n={len(e_rest)}, mean abs error={e_rest.mean():.4f}")
    print(f"  in-set: n={len(e_set)}, mean abs error={e_set.mean():.4f}")
    print()

    print("6. REP LEVEL")
    sets_out = bs.count_reps(df)
    reps_flat = [(s["label"], r) for s in sets_out for r in s["reps"]]
    total_reps = len(reps_flat)
    print(f"  total reps from count_reps: {total_reps}")
    assert total_reps == 89, f"expected 89 reps, got {total_reps}"

    windows = rep_windows(df)
    assert len(windows) == total_reps, "window replication does not match count_reps"
    for (label, r), w in zip(reps_flat, windows):
        assert label == w["label"] and abs(r["t"] - round(w["peak_t"], 2)) < 1e-9, \
            "rep/window alignment mismatch"

    rep_rows = []
    for (label, r), w in zip(reps_flat, windows):
        win = w["window"]
        wd = win[~win["is_real"]]
        if len(wd) > 0:
            mean_err = float((wd["acc_r"] - wd["acc_r_recon"]).abs().mean())
        else:
            mean_err = None
        rep_rows.append({"label": label, "t": r["t"],
                         "confidence": r["confidence"],
                         "explanation": r["explanation"],
                         "n_dropped_in_window": len(wd),
                         "mean_err": mean_err})

    with_drop = [r for r in rep_rows if r["n_dropped_in_window"] > 0]
    without_drop = [r for r in rep_rows if r["n_dropped_in_window"] == 0]
    print(f"  reps whose window contains at least one dropped sample: {len(with_drop)}")
    print(f"  reps with no dropped samples in window (no error exposure): {len(without_drop)}")

    for name, group in [("confidence < 0.6", [r for r in rep_rows if r["confidence"] < 0.6]),
                        ("confidence >= 0.6", [r for r in rep_rows if r["confidence"] >= 0.6])]:
        g_exposed = [r for r in group if r["n_dropped_in_window"] > 0]
        if g_exposed:
            g_mean = np.mean([r["mean_err"] for r in g_exposed])
            print(f"  {name}: n={len(group)} reps ({len(g_exposed)} with dropped "
                  f"samples in window), mean window abs error over dropped "
                  f"samples={g_mean:.4f}")
        else:
            print(f"  {name}: n={len(group)} reps, none with dropped samples in window")

    flagged = [r for r in rep_rows if r["explanation"] is not None]
    print(f"  flagged reps (non-null explanation): {len(flagged)}")
    assert len(flagged) == 4, f"expected 4 flagged reps, got {len(flagged)}"
    for r in flagged:
        err_str = f"{r['mean_err']:.4f}" if r["mean_err"] is not None else "no dropped samples in window"
        print(f"    {r['label']}: t={r['t']}, confidence={r['confidence']:.3f}, "
              f"mean abs error over dropped samples in window={err_str}")
    print()

    print("7. THRESHOLD CHECK")
    median_err = acc_err.median()
    print(f"  session median abs acc_r error on dropped samples: {median_err:.4f}")
    low = acc_err[conf < 0.35]
    high = acc_err[conf >= 0.6]
    print(f"  confidence < 0.35:  n={len(low)}, fraction with abs error above "
          f"median: {(low > median_err).mean():.4f}")
    print(f"  confidence >= 0.6:  n={len(high)}, fraction with abs error above "
          f"median: {(high > median_err).mean():.4f}")


if __name__ == "__main__":
    main()
