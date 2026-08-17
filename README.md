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

## Unexpected Findings

The rep counter was tuned against bench and overhead press, both of which
show one acceleration peak per rep. Run against the deadlift set, it
returned 20 reps in 31 seconds.

Checking rep-to-rep timing showed gaps alternating between about 1.0 and
2.0 seconds, not a consistent tempo. A deadlift produces two acceleration
peaks per rep, one at liftoff and one at lockout. The peak detector was
counting both. The one-peak-per-rep assumption held for bench and overhead
press and was never tested against a two-peak movement until this run.

We increased the minimum peak-spacing threshold from 1.0s to 1.4s, which
merges the two deadlift peaks into one rep without losing reps on faster
movements. Rep count for that set went from 20 to 11.

The error did not surface as a failure state. It returned a plausible
number with no indication it was wrong. It was caught by checking timing
between reps, not by inspecting the rep count itself.

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
