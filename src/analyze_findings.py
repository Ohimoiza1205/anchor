"""Analyze output/session.json findings. Loads the built session only,
never reruns the pipeline. Prints six labeled sections of computed numbers."""

import json
from pathlib import Path

import numpy as np
from scipy.signal import butter, filtfilt, find_peaks

SESSION_PATH = Path(__file__).parent.parent / "output" / "session.json"
HZ = 10


def load_session():
    with open(SESSION_PATH) as f:
        return json.load(f)


def find_gaps(samples):
    """Return list of (start_idx, end_idx) inclusive runs where is_real is False."""
    gaps = []
    start = None
    for i, s in enumerate(samples):
        if not s["is_real"]:
            if start is None:
                start = i
        else:
            if start is not None:
                gaps.append((start, i - 1))
                start = None
    if start is not None:
        gaps.append((start, len(samples) - 1))
    return gaps


def gap_class(samples, gap):
    """rest-period if every sample in the gap is labeled rest, else in-set."""
    lo, hi = gap
    labels = {samples[i]["label"] for i in range(lo, hi + 1)}
    return "rest-period" if labels == {"rest"} else "in-set"


def conf_stats(vals):
    return (
        round(float(np.mean(vals)), 3),
        round(float(np.min(vals)), 3),
        round(float(np.max(vals)), 3),
    )


def section_header(title):
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def print_summary(samples):
    n = len(samples)
    recon = [s for s in samples if not s["is_real"]]
    all_conf = [s["confidence"] for s in samples]
    recon_conf = [s["confidence"] for s in recon]
    print("SUMMARY")
    print(f"  total samples: {n}")
    print(f"  total reconstructed samples: {len(recon)}")
    print(f"  overall mean confidence: {round(float(np.mean(all_conf)), 3)}")
    print(f"  mean confidence on reconstructed samples: {round(float(np.mean(recon_conf)), 3)}")


def section1(samples, gaps):
    section_header("1. GAP LOCATION SPLIT")
    for cls in ["rest-period", "in-set"]:
        cls_gaps = [g for g in gaps if gap_class(samples, g) == cls]
        idxs = [i for lo, hi in cls_gaps for i in range(lo, hi + 1)]
        confs = [samples[i]["confidence"] for i in idxs]
        durations = [(hi - lo + 1) / HZ for lo, hi in cls_gaps]
        print(f"  {cls}:")
        print(f"    gaps: {len(cls_gaps)}")
        print(f"    samples: {len(idxs)}")
        if confs:
            m, lo_c, hi_c = conf_stats(confs)
            print(f"    confidence mean/min/max: {m} / {lo_c} / {hi_c}")
            print(f"    mean gap duration: {round(float(np.mean(durations)), 1)} s")
        else:
            print("    confidence mean/min/max: n/a")
            print("    mean gap duration: n/a")


def dist_to_real(samples):
    """Distance in seconds from each sample to the nearest is_real sample."""
    n = len(samples)
    is_real = np.array([s["is_real"] for s in samples])
    dist_prev = np.full(n, np.inf)
    last = -np.inf
    for i in range(n):
        if is_real[i]:
            last = i
        dist_prev[i] = (i - last) / HZ
    dist_next = np.full(n, np.inf)
    nxt = np.inf
    for i in range(n - 1, -1, -1):
        if is_real[i]:
            nxt = i
        dist_next[i] = (nxt - i) / HZ
    return np.minimum(dist_prev, dist_next)


def section2(samples):
    section_header("2. CONFIDENCE VS DISTANCE TABLE")
    dist = dist_to_real(samples)
    recon_idx = [i for i, s in enumerate(samples) if not s["is_real"]]
    buckets = [
        ("[0-0.1]", 0.0, 0.1),
        ("(0.1-0.2]", 0.1, 0.2),
        ("(0.2-0.4]", 0.2, 0.4),
        ("(0.4-0.8]", 0.4, 0.8),
        ("(0.8-1.5]", 0.8, 1.5),
        ("(1.5+]", 1.5, np.inf),
    ]
    print(f"  {'bucket (s)':<12} {'n':>5} {'mean_conf':>10} {'min_conf':>9} {'max_conf':>9}")
    for name, lo, hi in buckets:
        if lo == 0.0:
            in_bucket = [i for i in recon_idx if lo <= dist[i] <= hi]
        else:
            in_bucket = [i for i in recon_idx if lo < dist[i] <= hi]
        confs = [samples[i]["confidence"] for i in in_bucket]
        if confs:
            m, lo_c, hi_c = conf_stats(confs)
            print(f"  {name:<12} {len(confs):>5} {m:>10.3f} {lo_c:>9.3f} {hi_c:>9.3f}")
        else:
            print(f"  {name:<12} {0:>5} {'n/a':>10} {'n/a':>9} {'n/a':>9}")


def section3(data):
    section_header("3. PER-EXERCISE STATS")
    samples = data["samples"]
    by_ex = {}
    for st in data["sets"]:
        ex = st["label"].split("-")[0]
        by_ex.setdefault(ex, []).append(st)
    for ex in ["bench", "ohp", "squat", "dead"]:
        sets = by_ex.get(ex, [])
        reps = [r for st in sets for r in st["reps"]]
        ex_samples = [s for s in samples if s["label"].startswith(ex + "-")]
        recon = [s for s in ex_samples if not s["is_real"]]
        print(f"  {ex}:")
        print(f"    sets: {len(sets)}")
        print(f"    total reps: {sum(st['rep_count'] for st in sets)}")
        if reps:
            print(f"    mean rep confidence: {round(float(np.mean([r['confidence'] for r in reps])), 3)}")
        else:
            print("    mean rep confidence: n/a")
        print(f"    reps with confidence < 1.0: {sum(1 for r in reps if r['confidence'] < 1.0)}")
        print(f"    reps with non-null explanation: {sum(1 for r in reps if r['explanation'] is not None)}")
        if ex_samples:
            mc = round(float(np.mean([s["confidence"] for s in ex_samples])), 3)
            pct = round(100.0 * len(recon) / len(ex_samples), 1)
            print(f"    mean sample confidence: {mc}")
            print(f"    percent samples reconstructed: {pct}%")


def gap_edge_series(samples, gap):
    """acc_r from the measured sample before the gap through the measured
    sample after. Returns (indices, values) or None if the gap touches an edge."""
    lo, hi = gap
    if lo - 1 < 0 or hi + 1 >= len(samples):
        return None
    idxs = list(range(lo - 1, hi + 2))
    vals = [samples[i]["acc_r"] for i in idxs]
    return idxs, vals


def section4(samples, gaps):
    section_header("4. SMOOTH BUT LOW CONFIDENCE")
    in_set_gaps = [g for g in gaps if gap_class(samples, g) == "in-set"]

    def candidates(step_threshold):
        out = []
        for gap in in_set_gaps:
            lo, hi = gap
            confs = [samples[i]["confidence"] for i in range(lo, hi + 1)]
            if max(confs) >= 0.35:
                continue
            edge = gap_edge_series(samples, gap)
            if edge is None:
                continue
            idxs, vals = edge
            steps = np.abs(np.diff(vals))
            if float(np.max(steps)) < step_threshold:
                out.append((gap, confs, idxs, vals, float(np.max(steps))))
        return out

    threshold = 0.08
    found = candidates(threshold)
    relaxed = False
    while len(found) < 2 and threshold < 2.0:
        threshold *= 2
        relaxed = True
        found = candidates(threshold)

    print(f"  smoothness threshold: max abs step between consecutive acc_r values")
    print(f"  across gap edges < {threshold}")
    if relaxed:
        print(f"  note: initial threshold 0.08 yielded fewer than 2 examples, relaxed to {threshold}")
    print(f"  candidates found: {len(found)}")
    for k, (gap, confs, idxs, vals, max_step) in enumerate(found[:4], 1):
        lo, hi = gap
        label = next(samples[i]["label"] for i in range(lo, hi + 1) if samples[i]["label"] != "rest")
        mid = idxs[len(idxs) // 2]
        print(f"  example {k}:")
        print(f"    set label: {label}")
        print(f"    gap start t: {round(samples[lo]['t'], 1)} s, gap end t: {round(samples[hi]['t'], 1)} s")
        print(f"    gap duration: {round((hi - lo + 1) / HZ, 1)} s")
        print(f"    confidence min/mean: {round(float(np.min(confs)), 3)} / {round(float(np.mean(confs)), 3)}")
        print(f"    max abs step across gap edges: {round(max_step, 4)}")
        print(f"    acc_r measured before (t={round(samples[idxs[0]]['t'], 1)}): {samples[idxs[0]]['acc_r']}")
        print(f"    acc_r middle interpolated (t={round(samples[mid]['t'], 1)}): {samples[mid]['acc_r']}")
        print(f"    acc_r measured after (t={round(samples[idxs[-1]]['t'], 1)}): {samples[idxs[-1]]['acc_r']}")


def section5(samples, gaps):
    section_header("5. HIGH CONFIDENCE DESPITE DROPOUT")
    print("  note: factors below are recomputed from the output sample stream")
    print("  (reconstructed acc_r as proxy), not read from pipeline internals")
    acc_r = np.array([s["acc_r"] for s in samples])
    n = len(samples)

    threshold = 0.8
    while threshold > 0.4:
        qualifying = [
            g for g in gaps
            if min(samples[i]["confidence"] for i in range(g[0], g[1] + 1)) >= threshold
        ]
        if len(qualifying) >= 2:
            break
        threshold = round(threshold - 0.05, 2)
    if threshold < 0.8:
        print(f"  note: no gap has all samples with confidence >= 0.8 in this run")
        print(f"  (highest per-gap minimum is below 0.8), threshold relaxed to {threshold};")
        print(f"  the gaps below are the highest-confidence gaps in the session")
    print(f"  criterion: every sample in the gap has confidence >= {threshold}")

    shown = 0
    for gap in qualifying:
        lo, hi = gap
        confs = [samples[i]["confidence"] for i in range(lo, hi + 1)]
        dur = (hi - lo + 1) / HZ
        max_dist = np.ceil((hi - lo + 1) / 2) / HZ
        dist_decay_worst = float(np.exp(-max_dist / 1.0))
        wstart = max(0, lo - HZ)
        pre = acc_r[wstart:lo]
        vol = float(np.std(pre)) if len(pre) > 1 else float("nan")
        vol_penalty = float(np.clip(1.0 - vol / 1.2, 0.45, 1.0)) if len(pre) > 1 else float("nan")
        before, after = lo - 1, hi + 1
        if before >= 1 and after < n - 1:
            slope_before = acc_r[before] - acc_r[before - 1]
            slope_after = acc_r[after + 1] - acc_r[after]
            reversal = slope_before * slope_after < 0
            rev_str = "yes" if reversal else "no"
        else:
            rev_str = "n/a (gap at stream edge)"
        labels = {samples[i]["label"] for i in range(lo, hi + 1)}
        label = "rest" if labels == {"rest"} else next(l for l in labels if l != "rest")
        shown += 1
        print(f"  example {shown}:")
        print(f"    label: {label}")
        print(f"    start t: {round(samples[lo]['t'], 1)} s, end t: {round(samples[hi]['t'], 1)} s, duration: {round(dur, 1)} s")
        print(f"    mean confidence: {round(float(np.mean(confs)), 3)}")
        print(f"    why (recomputed from output stream):")
        print(f"      short gap: worst-case distance to real sample {round(max_dist, 1)} s,")
        print(f"        distance decay exp(-d/1.0) at gap center = {round(dist_decay_worst, 3)}")
        print(f"      pre-gap volatility: std of acc_r in 1 s before gap = {round(vol, 4)},")
        print(f"        volatility penalty clip(1 - std/1.2, 0.45, 1.0) = {round(vol_penalty, 3)}")
        print(f"      slope reversal across gap: {rev_str}")
        if shown >= 3:
            break


def section6(samples):
    section_header("6. DEADLIFT DOUBLE COUNT")
    label = "dead-medium1-rpe6"
    sub = [s for s in samples if s["label"] == label]
    sig = np.array([s["acc_r"] for s in sub])
    ts = np.array([s["t"] for s in sub])
    b, a = butter(4, 1.2 / (HZ / 2), btype="low")
    filtered = filtfilt(b, a, sig)
    print(f"  set: {label}, samples: {len(sub)}")
    for name, dist_s in [("pre-fix (min distance 1.0 s)", 1.0), ("post-fix (min distance 1.4 s)", 1.4)]:
        min_distance = int(dist_s * HZ)
        peaks, _ = find_peaks(filtered, distance=min_distance, prominence=0.15)
        peak_ts = [round(float(ts[p]), 1) for p in peaks]
        gaps = [round(peak_ts[i + 1] - peak_ts[i], 1) for i in range(len(peak_ts) - 1)]
        print(f"  {name}:")
        print(f"    rep count: {len(peaks)}")
        print(f"    peak timestamps (s): {peak_ts}")
        print(f"    rep-to-rep gaps (s): {gaps}")


def main():
    data = load_session()
    samples = data["samples"]
    gaps = find_gaps(samples)
    print_summary(samples)
    section1(samples, gaps)
    section2(samples)
    section3(data)
    section4(samples, gaps)
    section5(samples, gaps)
    section6(samples)


if __name__ == "__main__":
    main()
