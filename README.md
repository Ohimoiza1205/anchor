# Anchor

Confidence-aware reconstruction for wearable sensor data.

Anchor reconstructs a wrist-worn accelerometer and gyroscope session from a
public barbell-training dataset, injects synthetic Bluetooth dropouts on
top of the recorded signal, reconstructs the missing samples with
interpolation, and scores each reconstructed sample for confidence. Rep
counts are computed on the reconstructed stream, and each rep carries the
confidence of the samples it spans, with a one-line reason attached when
that confidence is low.

## The Problem

Wearable sensors lose connection to the host device intermittently, more
often during high-motion periods than during rest. When that happens, the
system has to produce a continuous value for whatever consumes the stream
downstream. Most pipelines fill the gap with interpolation and report the
result with the same certainty as measured data.

## Why This Problem Matters

Dropouts are more likely at the moments a rep is decided: the bottom of a
squat, the lockout of a deadlift. A pipeline that does not distinguish
measured samples from reconstructed samples cannot tell a user, or a
downstream model, when a rep count or a metric is based on a guess rather
than a reading.

## Approach

The pipeline starts from twelve sets recorded on a single day from one
participant in an open dataset (wrist-worn accelerometer and gyroscope,
bench, overhead press, squat, deadlift). The sets are stitched into one
continuous session in the order they were recorded. Rest between sets is
compressed to a shorter interval, scaled from the original gap length, to
keep total session length under ten minutes.

Dropouts are injected on the stitched, measured signal. Onset probability
is a function of instantaneous motion: higher during reps, lower during
rest. Gap duration is drawn from a lognormal distribution, clipped to
0.3 to 3.0 seconds. Everything before this step is measured data.
Everything from this step forward is synthetic.

Missing samples are filled with linear interpolation. Each reconstructed
sample is scored on three factors: time distance to the nearest measured
sample, standard deviation of the measured signal in the second before the
gap opened, and whether the signal's slope reverses sign across the gap,
which is evidence a peak or trough occurred inside the gap and was
interpolated over.

Rep counting runs on the reconstructed stream, using a low-pass filter and
peak detection with a minimum spacing threshold. Each detected rep is
assigned the mean confidence of the samples in its window. Reps with
confidence below 0.6, or reps where the turning-point check fired, get a
one-line explanation generated from the same computed values, with no
external model call.

## Key Design Decisions

**Stitched recorded sets instead of generating synthetic accelerometer
data.**
What: used recorded lifts as the base signal.
Why: motion structure (rep shape, redirection points, fatigue variation)
needed to be present for the confidence system to have something worth
scoring. Generating this synthetically would require deciding in advance
what a rep looks like, which removes the thing being tested.
Alternative rejected: a procedurally generated, sine-based rep signal,
which would allow computing ground-truth reconstruction error but would
test the generator, not the confidence system.
Limitation remaining: no ground truth exists for what the missing signal
should have been, so reconstruction accuracy cannot be measured directly.
Confidence values are relative, not calibrated.

**Synthetic corruption applied only to the failure, not the underlying
signal.**
What: dropouts are the only synthetic component; the measured signal is
untouched outside gaps.
Why: keeps the boundary between measured and synthetic traceable, in the
data and in this document.
Alternative rejected: adding synthetic noise throughout the session.
Limitation remaining: outside injected gaps, the pipeline assumes the
source recording is clean. Sensor noise or calibration error already
present in the original dataset is not separated from signal.

**Confidence computed from three heuristics, not a trained model.**
What: distance decay, pre-gap volatility, and a slope-reversal check,
combined multiplicatively.
Why: no labeled data exists on reconstruction error to train against. A
trained model would fit a proxy target rather than the quantity we care
about.
Alternative rejected: training a regression model on synthetic
ground-truth error, generated from a synthetic base signal.
Limitation remaining: weights for each factor were chosen by inspection,
not fit to any outcome. A confidence of 0.44 is meaningful only relative
to other values in this session, not as a calibrated probability.

**Rep-level explanations generated from computed values, no LLM call.**
What: explanation strings are templated from confidence, the is_real flag,
and the turning-point boolean.
Why: every input to the explanation is already a structured value the
pipeline computed. An LLM call adds latency and a failure mode, the
generated sentence not matching the underlying values, with no
corresponding gain.
Alternative rejected: passing rep statistics to a language model and
prompting it to narrate them.
Limitation remaining: explanations are limited to the fixed set of
conditions the code checks for. A failure mode not covered by the three
heuristics is reflected only in a lower number, not described.

**Rest intervals compressed proportionally instead of fixed length or
unmodified.**
What: each inter-set gap is scaled by a fixed factor and clamped to a
15 to 60 second range.
Why: unmodified gaps ranged from about 2 minutes to 24 minutes, too long
to review as a demo. A fixed rest length would erase the difference
between a short break and a long one.
Alternative rejected: replacing every rest period with the same fixed
duration.
Limitation remaining: displayed rest durations do not correspond to actual
elapsed time in the original recording. This is disclosed in code comments
but not obvious from the interface alone.

## Findings

All numbers in this section come from `src/analyze_findings.py`, which
reads `output/session.json` and prints them. Run it to reproduce.

### Deadlift double counting

Observation: the rep counter, tuned against bench and overhead press,
returned 20 reps for the deadlift set (`dead-medium1-rpe6`, 309 samples,
30.9 seconds of lifting).

Evidence: with the original 1.0 second minimum peak spacing, the
rep-to-rep gaps were 2.7, 1.1, 2.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.0, 1.1,
1.0, 1.3, 1.9, 1.2, 2.0, 1.1, 1.1, 3.0, 1.9 seconds. The run of nine
consecutive gaps near 1.0 second is the double-count signature: liftoff
and lockout of the same rep, counted separately. After raising the
minimum spacing to 1.4 seconds, the count is 11 with gaps of 1.9 to 4.1
seconds, a consistent tempo.

Why it surprised us: bench and overhead press produce one acceleration
peak per rep, and we tuned against those. We did not test the
one-peak-per-rep assumption until the deadlift run, and the failure did
not look like a failure. 20 is a plausible rep count. We caught it by
checking rep-to-rep timing, not by looking at the count.

Impact on system design: we raised the global minimum spacing to 1.4
seconds and added the timing check to the analysis script. The larger
change is to how we treat outputs: a plausible number is not a validated
number, and per-exercise detector settings are on the future work list
because one global threshold demonstrably does not transfer across
movement shapes.

### Turning-point sensitivity

Observation: distance to the nearest measured sample, the intuitive
driver of reconstruction confidence, explains less of the confidence
spread than what the signal was doing around the gap.

Evidence: reconstructed samples within 0.1 seconds of a measured sample
have mean confidence 0.652, but the range in that bucket runs from 0.229
to 0.814. The spread inside the closest bucket (0.585) is wider than the
drop in means from the closest bucket to the farthest occupied one
(0.652 down to 0.376). Samples that score near the bottom of their
bucket are the ones where the signal slope reverses across the gap,
which triggers the 0.3 turning-point penalty.

Why it surprised us: we expected distance decay to dominate. At the gap
durations that occur here (up to about 1.5 seconds), whether a
redirection point fell inside the gap matters more than how long the gap
was.

Impact on system design: the three penalty factors stay multiplicative,
and the turning-point check is the main source of flagged reps. A
distance-only confidence score would have passed exactly the samples
that deserve the most suspicion.

### Confidence degradation around reconstructed regions

Observation: no reconstructed sample gets close to full confidence, even
immediately adjacent to measured data.

Evidence: mean confidence is 0.985 across all 4766 samples and 0.531
across the 155 reconstructed samples. By distance to the nearest
measured sample: 0.652 mean at 0.1 seconds or less, 0.575 at 0.1 to 0.2,
0.457 at 0.2 to 0.4, 0.376 at 0.4 to 0.8. No reconstructed sample in
this run sits farther than 0.8 seconds from a measured one.

Why it surprised us: we expected samples one grid step from measured
data to score close to 1.0. They average 0.652 because the volatility
and turning-point penalties apply to a whole gap, not per sample, so a
sample can be near a measured neighbor and still sit inside a suspect
gap.

Impact on system design: rep confidence is the mean over the rep window,
so a single short gap inside a rep pulls the rep visibly below 1.0. That
is intentional and we kept it: adjacency to measured data should not
launder a suspect gap back to full confidence.

### Differences between lifts

Observation: dropout exposure was similar across the four lifts, but the
rep-level impact was not.

Evidence: reconstructed sample share by exercise: bench 3.9%, overhead
press 4.4%, squat 3.3%, deadlift 4.9%. Rep-level impact: overhead press
had 6 of 43 reps below confidence 1.0 and 2 flagged with explanations;
squat 2 of 26 below 1.0 and 2 flagged; deadlift 1 of 11 below 1.0, none
flagged; bench 0 of 9 below 1.0, none flagged. Bench still has the
lowest mean sample confidence of the four (0.969), driven by a
low-confidence gap at t=0.6 to 1.7 seconds that fell outside every
detected rep window.

Why it surprised us: we assumed sample-level damage and rep-level damage
would track each other. Bench shows they can diverge: the worst gap in
the set landed between reps, so every bench rep reports confidence 1.0
while the set contains a 0.207 mean-confidence reconstruction.

Impact on system design: rep-window averaging can hide low-confidence
regions that fall between reps. Set-level confidence aggregation is on
the future work list for exactly this case.

### Interpolation that looks plausible but scores low

Observation: the smoothest-looking reconstructions are not the most
trustworthy ones. Four in-set gaps produce traces that join their
neighbors almost seamlessly and still score among the lowest confidence
in the session.

Evidence: in `bench-heavy2-rpe8`, the gap from t=0.6 to 1.7 seconds has
a maximum step of 0.0081 g between consecutive samples across the gap
edges, visually continuous, and mean confidence 0.207. In
`ohp-heavy1-rpe8`, the gap from t=114.5 to 115.4 seconds runs smoothly
from 1.3767 g down to 0.7466 g and carries the session's minimum
confidence, 0.153. Similar cases: `ohp-medium2-rpe7` at t=258.9 to 259.5
(mean 0.205) and `squat-medium1-rpe7` at t=317.1 to 317.6 (mean 0.233).

Why it surprised us: we knew interpolation smooths, but seeing a
sub-0.16 confidence region that a person scanning the plot would not
notice made the point concrete. Visual inspection of the reconstructed
trace carries no information about reconstruction quality.

Impact on system design: the viewer shows confidence explicitly rather
than relying on the trace looking wrong, because the trace never looks
wrong.

### Where confidence stays highest through a dropout

Observation: we looked for gaps where confidence stayed high despite the
dropout, and found that in this scoring scheme no gap fully escapes.
The best cases are short gaps during rest.

Evidence: no gap in the session keeps every sample at or above 0.8. The
practical ceiling for a reconstructed sample is 0.814: one grid step
from measured data (decay exp(-0.1) = 0.905) times the 0.9 edge penalty
applied even to monotonic gaps. The highest-scoring gaps are rest-period
gaps of 0.3 to 0.4 seconds at t=154.1, t=160.8, and t=432.9, with mean
confidence 0.775 to 0.788: pre-gap volatility 0.0, no slope reversal,
worst-case distance 0.2 seconds. Overall, rest-period gaps average
0.679 confidence against 0.437 for in-set gaps.

Why it surprised us: we expected some dropouts to be nearly free and
score in the high 0.9s. The scoring never grants that, because even a
monotonic gap keeps a 0.9 edge penalty and distance decay starts
immediately.

Impact on system design: every reconstructed region is visible in the
output, including benign ones. Whether rest-period gaps should be
exempted from downstream penalties is a product decision, discussed
under Product Implications; the pipeline itself does not exempt them.

## What the User Sees

The session renders as one continuous timeline. Measured samples and
reconstructed samples are visually distinct, with a confidence value
attached to each point on the reconstructed portions.

Each detected rep displays its own confidence rather than a session
average. Reps above the 0.6 threshold, without a turning-point flag,
display with no further explanation. Reps below that threshold, or with
the turning-point flag set, display a one-line reason: a sensor gap
occurred at a likely turning point in the movement, so part of that rep's
data is reconstructed rather than measured.

## Limitations

Confidence values are heuristic. Weights for the three scoring factors
were set by inspection, not fit to labeled data, because no labeled data
exists for this task at this scope. A value of 0.44 indicates lower
confidence than 0.9 within this session. It should not be read as a
calibrated probability.

Dropout frequency, duration, and motion correlation were chosen to be
plausible for a Bluetooth wearable. They were not fit to Fort's hardware
logs, which we did not have access to. Dropout behavior on a specific
device may differ.

All tuning (volatility window size, turning-point threshold, rep-spacing
threshold) was done against one participant's one-day session. The
deadlift case shows these do not transfer automatically across movement
patterns. They have not been tested across different bodies, lifting
styles, or device placements.

Rep counting uses one global minimum-spacing threshold and one low-pass
filter cutoff across all four exercises. This is not tuned per exercise
and would need to be before covering additional movement types.

Sensor drift, device repositioning during a session, and battery-related
signal changes over a device's operating life are not modeled.

## Future Work

Confidence scoring could be fit to labeled reconstruction error, given a
dataset with paired clean and corrupted recordings of the same session.

Rep detection could move to per-exercise thresholds instead of one global
setting, validated against a labeled rep count rather than by inspection.

Confidence could be aggregated to the set level in addition to the rep
level.

The pipeline has not been run against more than one participant or more
than one recording day.

## Key Insights

Distance from a measured sample alone would not have flagged the deadlift
case. The samples nearest a gap can be close in time and still fall on
either side of a turning point the interpolation missed.

The deadlift error did not produce an error state. It produced a wrong
count that looked like every correct one next to it. It was found by
checking rep timing, not by checking the count.

Confidence and correctness were treated as separate properties throughout.
Confidence estimates how much a given reconstruction should be trusted. It
does not estimate whether the reconstruction is correct.
