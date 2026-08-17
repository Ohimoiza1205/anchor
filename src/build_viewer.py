"""Generates a single self-contained HTML file that visualizes session.json.
No build step, no server: double-click it and it opens in a browser, because
the session data is embedded directly rather than fetched. Rendering is inline
SVG built by vanilla JS; there are no external dependencies and no network
requests, so the output is statically inspectable."""

import json
from pathlib import Path

SESSION_PATH = Path(__file__).parent.parent / "output" / "session.json"
OUT_PATH = Path(__file__).parent.parent / "viewer.html"

TEMPLATE = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Anchor session viewer</title>
<style>
  :root {
    --bg: #fbfbfa;
    --ink: #24272b;
    --dim: #6b7076;
    --measured: #45494f;
    --recon: #b08205;
    --flag: #a3341f;
    --rest: #f1f0ed;
    --rule: #d8d6d1;
    --mono: ui-monospace, "SF Mono", "Cascadia Code", Consolas, monospace;
    --sans: -apple-system, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0;
    background: var(--bg);
    color: var(--ink);
    font-family: var(--sans);
    font-size: 15px;
    line-height: 1.6;
    padding: 56px 24px 72px;
  }
  .wrap { max-width: 860px; margin: 0 auto; }

  header { margin-bottom: 56px; }
  h1 {
    font-size: 20px;
    font-weight: 600;
    letter-spacing: -0.01em;
    margin: 0 0 6px;
  }
  .subtitle {
    color: var(--dim);
    font-size: 14px;
    margin: 0 0 32px;
    max-width: 62ch;
  }
  .stats { display: flex; gap: 56px; flex-wrap: wrap; }
  .stat .value {
    font-size: 27px;
    font-weight: 600;
    font-variant-numeric: tabular-nums;
    line-height: 1.2;
  }
  .stat .label {
    font-size: 12px;
    color: var(--dim);
    text-transform: uppercase;
    letter-spacing: 0.04em;
    margin-top: 2px;
  }

  section { margin-bottom: 56px; }
  h2 {
    font-size: 12px;
    font-weight: 600;
    text-transform: uppercase;
    letter-spacing: 0.08em;
    color: var(--dim);
    margin: 0 0 6px;
  }
  .caption {
    font-size: 13px;
    color: var(--dim);
    margin: 0 0 16px;
    max-width: 72ch;
  }
  svg { display: block; width: 100%; height: auto; }
  .legend {
    display: flex;
    gap: 22px;
    flex-wrap: wrap;
    font-size: 12px;
    color: var(--dim);
    margin-top: 10px;
  }
  .legend span { display: inline-flex; align-items: center; gap: 6px; }
  .swatch { display: inline-block; width: 12px; height: 3px; }
  .swatch.tick { width: 2px; height: 10px; }

  .flag-row { margin-bottom: 22px; }
  .flag-row .flag-meta {
    font-family: var(--mono);
    font-size: 13px;
  }
  .flag-row .flag-meta .conf { color: var(--flag); }
  .flag-row p {
    margin: 2px 0 0;
    font-size: 14px;
    color: #3c4046;
    max-width: 72ch;
  }
  .flag-row .pr-note {
    font-size: 13px;
    color: var(--dim);
  }

  footer {
    font-size: 12.5px;
    color: var(--dim);
    line-height: 1.7;
    max-width: 76ch;
  }
  footer p { margin: 0 0 8px; }
</style>
</head>
<body>
<div class="wrap">
  <header>
    <h1>Anchor</h1>
    <p class="subtitle" id="subtitle"></p>
    <div class="stats" id="stats"></div>
  </header>

  <section>
    <h2>Session timeline</h2>
    <p class="caption" id="timelineCaption"></p>
    <div id="timeline"></div>
    <div class="legend">
      <span><i class="swatch" style="background:var(--measured)"></i>measured</span>
      <span><i class="swatch" style="background:var(--recon)"></i>reconstructed, confidence 0.6 or higher</span>
      <span><i class="swatch" style="background:var(--flag)"></i>reconstructed, confidence below 0.6</span>
      <span><i class="swatch tick" style="background:var(--measured)"></i>rep</span>
      <span><i class="swatch tick" style="background:var(--flag)"></i>flagged rep</span>
    </div>
  </section>

  <section>
    <h2>Flagged reps</h2>
    <p class="caption">Reps where the reconstruction overlaps a moment the rep detector depends on. Explanations are taken verbatim from the pipeline output.</p>
    <div id="flagList"></div>
  </section>

  <footer>
    <p id="countsNote"></p>
    <p id="sourceNote"></p>
  </footer>
</div>

<script>
const SESSION = __SESSION_JSON__;

const meta = SESSION.meta;
const samples = SESSION.samples;

function fmtTime(s) {
  let m = Math.floor(s / 60);
  let sec = Math.round(s % 60);
  if (sec === 60) { m += 1; sec = 0; }
  return m + ":" + String(sec).padStart(2, "0");
}

const css = (name) =>
  getComputedStyle(document.documentElement).getPropertyValue(name).trim();
const C = {
  measured: css("--measured"),
  recon: css("--recon"),
  flag: css("--flag"),
  rest: css("--rest"),
  rule: css("--rule"),
  dim: css("--dim"),
  bg: css("--bg"),
};

// ---------- derived data ----------

// Short display labels: exercise name plus a per-exercise counter in session
// order, e.g. "ohp 3". Raw labels are kept for tooltips and the flagged list.
const shortLabels = (() => {
  const counts = {};
  return SESSION.sets.map((set) => {
    const name = set.label.split("-")[0];
    counts[name] = (counts[name] || 0) + 1;
    return name + " " + counts[name];
  });
})();
const shortByLabel = {};
SESSION.sets.forEach((set, i) => { shortByLabel[set.label] = shortLabels[i]; });

// Contiguous runs of identical label (sets and rest periods).
const labelRuns = [];
for (const s of samples) {
  const last = labelRuns[labelRuns.length - 1];
  if (last && last.label === s.label) last.end = s.t;
  else labelRuns.push({ label: s.label, start: s.t, end: s.t });
}
const setRuns = labelRuns.filter((r) => r.label !== "rest");
const restRuns = labelRuns.filter((r) => r.label === "rest");

// Contiguous runs of reconstructed samples, with min confidence per run.
const reconRuns = [];
for (const s of samples) {
  if (s.is_real) continue;
  const last = reconRuns[reconRuns.length - 1];
  if (last && s.t - last.end <= 0.15) {
    last.end = s.t;
    last.min = Math.min(last.min, s.confidence);
  } else {
    reconRuns.push({ start: s.t, end: s.t, min: s.confidence });
  }
}

// Trace split into runs of one drawing class, repeating the boundary sample
// so the polyline stays continuous.
const clsOf = (s) => (s.is_real ? 0 : (s.confidence >= 0.6 ? 1 : 2));
const traceRuns = [];
{
  let run = null;
  for (const s of samples) {
    const c = clsOf(s);
    if (!run || run.c !== c) {
      const next = { c: c, pts: [] };
      if (run) next.pts.push(run.pts[run.pts.length - 1]);
      traceRuns.push(next);
      run = next;
    }
    run.pts.push(s);
  }
}

const allReps = [];
SESSION.sets.forEach((set, i) => {
  set.reps.forEach((r) => {
    allReps.push({ short: shortLabels[i], rawLabel: set.label, rep: r });
  });
});
const flaggedReps = allReps.filter((x) => x.rep.explanation);

const totalN = samples.length;
const reconN = samples.filter((s) => !s.is_real).length;
const reconPct = (100 * reconN / totalN).toFixed(1);

// ---------- header ----------

document.getElementById("subtitle").textContent =
  "A training session reconstructed from wrist sensor data, with a confidence score on every sample and every detected rep. Participant " +
  meta.participant + ", " + meta.session_date + ", " + meta.n_sets + " sets.";

const stats = [
  [fmtTime(meta.duration_s), "duration"],
  [String(meta.total_reps_detected), "reps detected"],
  [reconPct + "%", "samples reconstructed"],
  [String(meta.reps_flagged_low_confidence), "reps flagged"],
];
document.getElementById("stats").innerHTML = stats
  .map(([v, l]) => '<div class="stat"><div class="value">' + v +
    '</div><div class="label">' + l + "</div></div>")
  .join("");

document.getElementById("timelineCaption").textContent =
  "Acceleration magnitude (g) at " + meta.resample_hz +
  " Hz. Shaded vertical bands mark reconstructed stretches, dimmed background marks rest, ticks along the top mark detected reps. The strip underneath is per-sample confidence: full height means 1.0, notches show where and how far it drops.";

// ---------- timeline SVG ----------

const NS = "http://www.w3.org/2000/svg";
function el(name, attrs, parent) {
  const e = document.createElementNS(NS, name);
  for (const k in attrs) e.setAttribute(k, attrs[k]);
  if (parent) parent.appendChild(e);
  return e;
}
function addTitle(node, text) {
  const t = document.createElementNS(NS, "title");
  t.textContent = text;
  node.appendChild(t);
}

const W = 1000, H = 306;
const mL = 40, mR = 10;
const plotTop = 34, plotBot = 226;
const stripTop = 268, stripH = 28;
const dur = meta.duration_s;

const px = (t) => mL + (t / dur) * (W - mL - mR);
const accVals = samples.map((s) => s.acc_r);
const vLo = Math.min.apply(null, accVals);
const vHi = Math.max.apply(null, accVals);
const vPad = 0.06 * (vHi - vLo);
const lo = vLo - vPad, hi = vHi + vPad;
const py = (v) => plotBot - ((v - lo) / (hi - lo)) * (plotBot - plotTop);

const svg = el("svg", {
  viewBox: "0 0 " + W + " " + H,
  role: "img",
  "aria-label": "Session timeline: acceleration trace with reconstructed regions, set boundaries, rep markers, and a per-sample confidence strip",
});
document.getElementById("timeline").appendChild(svg);

// Rest periods: quiet dimmed background.
for (const r of restRuns) {
  el("rect", {
    x: px(r.start).toFixed(2), y: plotTop,
    width: Math.max(px(r.end) - px(r.start), 0.5).toFixed(2),
    height: plotBot - plotTop,
    fill: C.rest,
  }, svg);
}

// Reconstructed regions: shaded band behind the trace, stronger when the
// run's minimum confidence is below 0.6.
for (const r of reconRuns) {
  let x1 = px(r.start), x2 = px(r.end);
  if (x2 - x1 < 2) { const c = (x1 + x2) / 2; x1 = c - 1; x2 = c + 1; }
  const low = r.min < 0.6;
  el("rect", {
    x: x1.toFixed(2), y: plotTop,
    width: (x2 - x1).toFixed(2), height: plotBot - plotTop,
    fill: low ? C.flag : C.recon,
    "fill-opacity": low ? 0.28 : 0.16,
  }, svg);
}

// Axes: recessive baseline, x ticks each minute. No y ticks: the trace shape,
// not the absolute g value, is what carries meaning here.
el("line", { x1: mL, y1: plotBot, x2: W - mR, y2: plotBot, stroke: C.rule, "stroke-width": 1 }, svg);
for (let t = 0; t <= dur; t += 60) {
  const x = px(t).toFixed(2);
  el("line", { x1: x, y1: plotBot, x2: x, y2: plotBot + 5, stroke: C.rule, "stroke-width": 1 }, svg);
  el("text", {
    x: x, y: plotBot + 20, "text-anchor": "middle",
    "font-size": 11, fill: C.dim,
  }, svg).textContent = fmtTime(t);
}

// Set boundaries: thin vertical rules with small labels, alternating between
// two rows so adjacent labels do not collide.
setRuns.forEach((seg, i) => {
  const x1 = px(seg.start), x2 = px(seg.end);
  for (const x of [x1, x2]) {
    el("line", {
      x1: x.toFixed(2), y1: 28, x2: x.toFixed(2), y2: plotBot,
      stroke: C.rule, "stroke-width": 1,
    }, svg);
  }
  const label = el("text", {
    x: Math.min(x1 + 3, W - mR - 44).toFixed(2),
    y: i % 2 === 0 ? 12 : 24,
    "font-size": 10.5, fill: C.dim,
  }, svg);
  label.textContent = shortByLabel[seg.label] || seg.label;
  addTitle(label, seg.label);
});

// Acceleration trace, one polyline per confidence class.
const traceStyle = [
  { stroke: C.measured, width: 1 },
  { stroke: C.recon, width: 1.4 },
  { stroke: C.flag, width: 1.4 },
];
for (const run of traceRuns) {
  const st = traceStyle[run.c];
  el("polyline", {
    points: run.pts.map((s) => px(s.t).toFixed(2) + "," + py(s.acc_r).toFixed(2)).join(" "),
    fill: "none",
    stroke: st.stroke,
    "stroke-width": st.width,
    "stroke-linejoin": "round",
    "stroke-linecap": "round",
  }, svg);
}

// Rep markers: short ticks hanging from the top of the plot. Flagged reps
// are longer, heavier, and in the flag color.
for (const { rep } of allReps) {
  const flagged = !!rep.explanation;
  const x = px(rep.t).toFixed(2);
  el("line", {
    x1: x, y1: 36, x2: x, y2: flagged ? 52 : 44,
    stroke: flagged ? C.flag : C.measured,
    "stroke-width": flagged ? 1.8 : 1,
  }, svg);
}

// Confidence strip, time-aligned under the trace. A solid bar at full height
// is confidence 1.0; reconstructed runs are cut down to their confidence.
el("text", {
  x: mL, y: stripTop - 6, "font-size": 11, fill: C.dim,
}, svg).textContent = "confidence";
el("rect", {
  x: mL, y: stripTop, width: W - mL - mR, height: stripH, fill: "#565b61",
}, svg);
for (const r of reconRuns) {
  let x1 = px(r.start), x2 = px(r.end);
  if (x2 - x1 < 2) { const c = (x1 + x2) / 2; x1 = c - 1; x2 = c + 1; }
  el("rect", {
    x: x1.toFixed(2), y: stripTop,
    width: (x2 - x1).toFixed(2), height: stripH, fill: C.bg,
  }, svg);
  const h = Math.max(r.min * stripH, 1);
  const bar = el("rect", {
    x: x1.toFixed(2), y: (stripTop + stripH - h).toFixed(2),
    width: (x2 - x1).toFixed(2), height: h.toFixed(2),
    fill: r.min < 0.6 ? C.flag : C.recon,
  }, svg);
  addTitle(bar, "confidence drops to " + r.min.toFixed(2) + " at " + fmtTime(r.start));
}

// ---------- flagged reps ----------

document.getElementById("flagList").innerHTML = flaggedReps
  .map(({ short, rawLabel, rep }) => {
    let row = '<div class="flag-row">' +
      '<div class="flag-meta">' + short + " (" + rawLabel + ") · " +
      fmtTime(rep.t) + ' · confidence <span class="conf">' +
      rep.confidence.toFixed(2) + "</span></div>" +
      "<p>" + rep.explanation + "</p>";
    if (!rep.counts_toward_pr && rep.counts_toward_pr_reason) {
      row += '<p class="pr-note">' + rep.counts_toward_pr_reason + "</p>";
    }
    return row + "</div>";
  })
  .join("");

// ---------- footer ----------

document.getElementById("countsNote").textContent =
  (totalN - reconN) + " of " + totalN + " samples are direct sensor readings; " +
  reconN + " samples (" + reconPct + "%) were reconstructed across dropout gaps. " +
  "Confidence is a heuristic score and is uncalibrated: use it to rank uncertainty within this session, not as a probability. " +
  "Rest periods are compressed from the original recording (up to 20x), so displayed times are not elapsed gym time.";
document.getElementById("sourceNote").textContent =
  "Source recordings: " + meta.source +
  ". Dropouts, reconstruction, and confidence scoring are synthetic, applied on top of measured accelerometer and gyroscope data. See README.md and data/SOURCE.md for the pipeline and its limitations.";
</script>
</body>
</html>
"""


def main():
    with open(SESSION_PATH) as f:
        session = json.load(f)

    html = TEMPLATE.replace("__SESSION_JSON__", json.dumps(session))

    OUT_PATH.write_text(html, encoding="utf-8")
    print(f"Wrote {OUT_PATH} ({OUT_PATH.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
