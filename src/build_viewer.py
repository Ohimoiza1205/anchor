"""Generates a single self-contained HTML file that visualizes session.json.
No build step, no server: double-click it and it opens in a browser, because
the session data is embedded directly rather than fetched."""

import json
from pathlib import Path

SESSION_PATH = Path(__file__).parent.parent / "output" / "session.json"
OUT_PATH = Path(__file__).parent.parent / "viewer.html"

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anchor — session viewer</title>
<script src="https://cdnjs.cloudflare.com/ajax/libs/Chart.js/4.4.4/chart.umd.min.js"></script>
<style>
  :root {
    --bg: #15171b;
    --panel: #1c1f24;
    --border: #2b2f36;
    --text: #e7e5e0;
    --text-dim: #96999f;
    --measured: #5c7c99;
    --recon-high: #c9a430;
    --recon-low: #b5504a;
    --mono: ui-monospace, "SF Mono", "Cascadia Code", "Roboto Mono", Consolas, monospace;
    --sans: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--text);
    font-family: var(--sans);
    padding: 32px 24px 64px;
  }
  .wrap { max-width: 980px; margin: 0 auto; }
  header { margin-bottom: 28px; }
  h1 {
    font-size: 22px;
    font-weight: 600;
    letter-spacing: -0.01em;
    margin: 0 0 4px;
  }
  .subtitle {
    color: var(--text-dim);
    font-size: 14px;
    margin: 0 0 20px;
  }
  .stats {
    display: flex;
    flex-wrap: wrap;
    gap: 10px;
  }
  .stat {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 10px 14px;
    min-width: 108px;
  }
  .stat .value {
    font-family: var(--mono);
    font-size: 18px;
    font-weight: 600;
  }
  .stat .label {
    font-size: 11px;
    color: var(--text-dim);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 2px;
  }
  .panel {
    background: var(--panel);
    border: 1px solid var(--border);
    border-radius: 8px;
    padding: 20px 20px 8px;
    margin-top: 20px;
  }
  .panel h2 {
    font-size: 13px;
    text-transform: uppercase;
    letter-spacing: 0.05em;
    color: var(--text-dim);
    margin: 0 0 14px;
    font-weight: 600;
  }
  .chart-container { position: relative; height: 340px; }
  .legend {
    display: flex;
    gap: 18px;
    margin: 14px 0 4px;
    font-size: 12px;
    color: var(--text-dim);
    flex-wrap: wrap;
  }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .swatch { width: 10px; height: 10px; border-radius: 2px; display: inline-block; }
  .rep-grid {
    display: grid;
    grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
    gap: 10px;
    margin-top: 4px;
  }
  .set-card {
    border: 1px solid var(--border);
    border-radius: 6px;
    padding: 12px 14px;
  }
  .set-card .set-name {
    font-size: 13px;
    font-weight: 600;
    margin-bottom: 6px;
  }
  .set-card .set-meta {
    font-family: var(--mono);
    font-size: 12px;
    color: var(--text-dim);
  }
  .rep-dot {
    display: inline-block;
    width: 8px;
    height: 8px;
    border-radius: 50%;
    margin-right: 3px;
  }
  .explain {
    margin-top: 8px;
    font-size: 12px;
    color: #d8b979;
    line-height: 1.5;
    padding-top: 8px;
    border-top: 1px solid var(--border);
  }
  footer {
    margin-top: 28px;
    font-size: 12px;
    color: var(--text-dim);
    line-height: 1.6;
  }
  footer a { color: var(--measured); }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Anchor</h1>
    <p class="subtitle">Confidence-aware reconstruction of a wrist-worn training session. Participant A, __SESSION_DATE__, __N_SETS__ sets.</p>
    <div class="stats" id="stats"></div>
  </header>

  <div class="panel">
    <h2>Session timeline</h2>
    <div class="legend">
      <span><i class="swatch" style="background:var(--measured)"></i>Measured</span>
      <span><i class="swatch" style="background:var(--recon-high)"></i>Reconstructed, confidence ≥ 0.6</span>
      <span><i class="swatch" style="background:var(--recon-low)"></i>Reconstructed, confidence &lt; 0.6</span>
      <span><i class="swatch" style="background:#4a4d54"></i>Rep marker (hover for detail)</span>
    </div>
    <div class="chart-container"><canvas id="chart"></canvas></div>
  </div>

  <div class="panel">
    <h2>Reps by set</h2>
    <div class="rep-grid" id="repGrid"></div>
  </div>

  <footer>
    Source recordings: SmartLift-Analysis-Project (open dataset, wrist-worn
    MetaMotion sensor). Dropouts, reconstruction, and confidence scoring are
    synthetic, applied on top of measured accelerometer and gyroscope data.
    See README.md and data/SOURCE.md for the full pipeline and its
    limitations.
  </footer>
</div>

<script>
const SESSION = __SESSION_JSON__;

function fmtTime(s) {
  const m = Math.floor(s / 60);
  const sec = Math.round(s % 60).toString().padStart(2, "0");
  return m + ":" + sec;
}

function confColor(sample) {
  if (sample.is_real) return getComputedStyle(document.documentElement).getPropertyValue("--measured").trim();
  return sample.confidence >= 0.6
    ? getComputedStyle(document.documentElement).getPropertyValue("--recon-high").trim()
    : getComputedStyle(document.documentElement).getPropertyValue("--recon-low").trim();
}

// --- stats header ---
const meta = SESSION.meta;
const stats = [
  ["Duration", fmtTime(meta.duration_s)],
  ["Sets", meta.n_sets],
  ["Reps detected", meta.total_reps_detected],
  ["Dropout", (meta.dropout_fraction * 100).toFixed(1) + "%"],
  ["Mean confidence", meta.mean_confidence.toFixed(3)],
  ["Flagged reps", meta.reps_flagged_low_confidence],
];
document.getElementById("stats").innerHTML = stats.map(
  ([label, value]) => `<div class="stat"><div class="value">${value}</div><div class="label">${label}</div></div>`
).join("");

// --- exercise segments, for background bands ---
const segments = [];
{
  let curLabel = null, curStart = null, prevT = null;
  for (const s of SESSION.samples) {
    if (s.label !== curLabel) {
      if (curLabel !== null && curLabel !== "rest") {
        segments.push({ label: curLabel, start: curStart, end: prevT });
      }
      curLabel = s.label;
      curStart = s.t;
    }
    prevT = s.t;
  }
  if (curLabel !== "rest") segments.push({ label: curLabel, start: curStart, end: prevT });
}

const bandPlugin = {
  id: "exerciseBands",
  beforeDatasetsDraw(chart) {
    const { ctx, chartArea, scales } = chart;
    if (!chartArea) return;
    ctx.save();
    segments.forEach((seg, i) => {
      const x1 = scales.x.getPixelForValue(seg.start);
      const x2 = scales.x.getPixelForValue(seg.end);
      ctx.fillStyle = i % 2 === 0 ? "rgba(255,255,255,0.025)" : "rgba(255,255,255,0.005)";
      ctx.fillRect(x1, chartArea.top, x2 - x1, chartArea.bottom - chartArea.top);
      ctx.fillStyle = "rgba(231,229,224,0.35)";
      ctx.font = "10px " + getComputedStyle(document.body).fontFamily;
      ctx.save();
      ctx.translate((x1 + x2) / 2, chartArea.top + 10);
      ctx.textAlign = "center";
      ctx.fillText(seg.label.split("-")[0], 0, 0);
      ctx.restore();
    });
    ctx.restore();
  }
};

// --- main trace + rep markers ---
const traceData = SESSION.samples.map(s => ({ x: s.t, y: s.acc_r, sample: s }));

const yMax = Math.max(...SESSION.samples.map(s => s.acc_r)) + 0.4;
const repPoints = [];
SESSION.sets.forEach(set => {
  set.reps.forEach(r => {
    repPoints.push({
      x: r.t,
      y: yMax,
      confidence: r.confidence,
      explanation: r.explanation,
      label: set.label,
    });
  });
});

const ctx = document.getElementById("chart").getContext("2d");
new Chart(ctx, {
  type: "line",
  data: {
    datasets: [
      {
        label: "acc_r",
        data: traceData,
        borderWidth: 1.5,
        pointRadius: 0,
        tension: 0,
        segment: {
          borderColor: (c) => confColor(traceData[c.p1DataIndex].sample),
        },
      },
      {
        type: "scatter",
        label: "reps",
        data: repPoints,
        pointRadius: 4,
        pointHoverRadius: 6,
        pointBackgroundColor: (c) => {
          const p = c.raw;
          if (!p) return "#888";
          return p.confidence >= 0.6
            ? getComputedStyle(document.documentElement).getPropertyValue("--recon-high").trim()
            : (p.confidence < 0.6 && p.explanation
                ? getComputedStyle(document.documentElement).getPropertyValue("--recon-low").trim()
                : "#4a4d54");
        },
        pointBorderWidth: 0,
      },
    ],
  },
  options: {
    animation: false,
    interaction: { mode: "nearest", intersect: true },
    scales: {
      x: {
        type: "linear",
        min: 0,
        max: SESSION.meta.duration_s,
        ticks: {
          color: "#96999f",
          callback: (v) => fmtTime(v),
        },
        grid: { color: "rgba(255,255,255,0.05)" },
      },
      y: {
        title: { display: true, text: "acceleration magnitude (g)", color: "#96999f", font: { size: 11 } },
        ticks: { color: "#96999f" },
        grid: { color: "rgba(255,255,255,0.05)" },
      },
    },
    plugins: {
      legend: { display: false },
      tooltip: {
        callbacks: {
          title: (items) => fmtTime(items[0].raw.x),
          label: (item) => {
            if (item.dataset.label === "reps") {
              const p = item.raw;
              const lines = [`${p.label} — confidence ${p.confidence.toFixed(2)}`];
              if (p.explanation) lines.push(p.explanation);
              return lines;
            }
            const s = item.raw.sample;
            return `${s.is_real ? "measured" : "reconstructed"} — confidence ${s.confidence.toFixed(2)}`;
          },
        },
      },
    },
  },
  plugins: [bandPlugin],
});

// --- rep grid below chart ---
const grid = document.getElementById("repGrid");
grid.innerHTML = SESSION.sets.map(set => {
  const dots = set.reps.map(r => {
    const color = r.confidence >= 0.6 ? "var(--recon-high)" : (r.explanation ? "var(--recon-low)" : "var(--measured)");
    const c = r.confidence === 1 ? "var(--measured)" : color;
    return `<span class="rep-dot" style="background:${c}" title="${r.confidence.toFixed(2)}"></span>`;
  }).join("");
  const flagged = set.reps.filter(r => r.explanation);
  const explainHtml = flagged.length
    ? `<div class="explain">${flagged.map(r => `t=${fmtTime(r.t)}: ${r.explanation}`).join("<br>")}</div>`
    : "";
  return `<div class="set-card">
    <div class="set-name">${set.label}</div>
    <div class="set-meta">${set.rep_count} reps · mean confidence ${set.mean_confidence.toFixed(3)}</div>
    <div style="margin-top:8px">${dots}</div>
    ${explainHtml}
  </div>`;
}).join("");
</script>
</body>
</html>
"""


def main():
    with open(SESSION_PATH) as f:
        session = json.load(f)

    html = TEMPLATE.replace("__SESSION_JSON__", json.dumps(session))
    html = html.replace("__SESSION_DATE__", session["meta"]["session_date"])
    html = html.replace("__N_SETS__", str(session["meta"]["n_sets"]))

    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
