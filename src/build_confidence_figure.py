"""Generates docs/figures/confidence_by_distance.png for the README.

Uses the exact bucketing from analyze_findings.py (the source of the
README's confidence-vs-distance table) so the figure cannot drift from
the stated numbers. Replaces the confidence figure formerly in
build_figures.py, whose bucket masks re-counted samples sitting exactly
on bucket edges and produced means that did not match the README.
"""

import json
import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np

sys.path.insert(0, str(Path(__file__).parent))
from analyze_findings import dist_to_real

SESSION_PATH = Path(__file__).parent.parent / "output" / "session.json"
OUT_PATH = (
    Path(__file__).parent.parent / "docs" / "figures" / "confidence_by_distance.png"
)

INK = "#1a1a1a"
DIM = "#6b6b66"
BG = "#faf9f6"
HIGH_CONF = "#8a7530"
LOW_CONF = "#8b3a2f"

plt.rcParams.update({
    "font.family": "monospace",
    "axes.edgecolor": DIM,
    "text.color": INK,
    "axes.labelcolor": INK,
    "xtick.color": DIM,
    "ytick.color": DIM,
    "figure.facecolor": BG,
    "axes.facecolor": BG,
})


def main():
    with open(SESSION_PATH) as f:
        session = json.load(f)
    samples = session["samples"]

    dist = dist_to_real(samples)
    conf = np.array([s["confidence"] for s in samples])
    recon_idx = [i for i, s in enumerate(samples) if not s["is_real"]]

    # Same buckets and same boundary handling as analyze_findings.section2:
    # first bucket closed on both ends, the rest half-open (lo, hi].
    buckets = [
        ("0-0.1s", 0.0, 0.1),
        ("0.1-0.2s", 0.1, 0.2),
        ("0.2-0.4s", 0.2, 0.4),
        ("0.4-0.8s", 0.4, 0.8),
    ]
    members = []
    for _, lo, hi in buckets:
        if lo == 0.0:
            members.append([i for i in recon_idx if lo <= dist[i] <= hi])
        else:
            members.append([i for i in recon_idx if lo < dist[i] <= hi])

    total = sum(len(m) for m in members)
    assert total == len(recon_idx), (
        f"buckets cover {total} of {len(recon_idx)} reconstructed samples; "
        "boundary handling has drifted from analyze_findings"
    )

    means = [float(np.mean(conf[m])) for m in members]
    print("bucket means:", {b[0]: round(m, 3) for b, m in zip(buckets, means)})

    fig, ax = plt.subplots(figsize=(8, 4.5))
    rng = np.random.default_rng(3)
    for x, m in enumerate(members):
        jitter = rng.uniform(-0.15, 0.15, len(m))
        ax.scatter(
            np.full(len(m), x) + jitter, conf[m],
            s=14, color=DIM, alpha=0.5, zorder=2,
        )

    ax.bar(range(len(buckets)), means, color=HIGH_CONF, alpha=0.35, width=0.5, zorder=1)
    for x, mean in enumerate(means):
        ax.text(
            x - 0.33, mean, f"{mean:.3f}",
            fontsize=8.5, color=INK, ha="right", va="center",
        )

    ax.axhline(0.6, color=LOW_CONF, linewidth=1, linestyle=(0, (3, 2)))
    ax.text(
        len(buckets) - 0.55, 0.615, "0.6 flag threshold",
        fontsize=8, color=LOW_CONF, ha="right",
    )

    ax.set_xticks(range(len(buckets)))
    ax.set_xticklabels(
        [f"{name}\nn={len(m)}" for (name, _, _), m in zip(buckets, members)],
        fontsize=9,
    )
    ax.set_ylabel("confidence", fontsize=9)
    ax.set_xlabel("distance to nearest measured sample", fontsize=9)
    ax.set_ylim(0, 1.0)
    ax.set_title(
        f"Confidence by distance to measured data "
        f"({len(recon_idx)} reconstructed samples)",
        fontsize=11, loc="left", color=INK, pad=10,
    )
    for spine in ["top", "right"]:
        ax.spines[spine].set_visible(False)

    fig.text(
        0.99, 0.01,
        "bars: bucket mean   dots: individual samples   "
        "spread inside the closest bucket exceeds the drop between bucket means",
        fontsize=7.5, color=DIM, ha="right",
    )

    fig.tight_layout()
    fig.savefig(OUT_PATH, dpi=180, facecolor=BG)
    print("wrote", OUT_PATH)


if __name__ == "__main__":
    main()
