# Question 2 Audit

The prompt: "Prototype a feature/system that you would be excited to
own." This audit checks the submission against that sentence, honestly.

## What is the feature?

Per-rep trust. A rep count where each rep carries a confidence value, a
flag when part of the movement was reconstructed rather than measured,
a one-line reason a user can read, and one consequence wired to it: a
rep below 0.6 confidence does not count toward a personal record
(specified in the README's Product Implications; the pipeline field
`counts_toward_pr` lands in the commit following this audit). The
feature is not the interpolation and not the charts; it is the product
answering "can I trust this number" instead of pretending the question
does not exist.

## What is the system?

An offline pipeline (`src/build_session.py`): stitch twelve recorded
sets into a session, inject synthetic BLE dropouts weighted toward
high-motion moments, reconstruct gaps with linear interpolation, score
every reconstructed sample on distance decay, pre-gap volatility, and
slope reversal across the gap, then count reps on the reconstructed
stream and roll sample confidence up to rep confidence. Two
verification scripts (`analyze_findings.py`, `validate_reconstruction.py`)
regenerate every number claimed anywhere in the repository, and a
generated viewer renders the session with confidence as the primary
visual story.

## What would I personally own?

The layer between raw sensor readings and every feature that consumes
them: reconstruction, confidence scoring, and the contract that
downstream consumers (records, streaks, recommendations, models)
receive uncertainty alongside values and must have a policy for it.
Ownership shows in the artifacts: the failure model, the scoring
heuristics, the validation experiment, and the first downstream policy
decision are all in this repo. What ownership does not yet include,
because the prototype does not reach it: the real-time path and the
actual hardware failure characteristics.

## What user problem does it solve?

A lifter makes decisions from numbers their wearable produces: add
weight, count the set, trust the record. When the radio drops mid-rep,
today's pipelines hand them a number indistinguishable from a measured
one. The problem solved here is narrower than "count reps accurately":
it is making the difference between measured and guessed visible at
the moment it affects a decision the user cares about, like a PR.

## What evidence from the prototype supports that?

- The gap between looking right and being right is demonstrated, twice.
  The deadlift set returned 20 reps with nothing visibly wrong (fixed
  to 11 by timing analysis), and four interpolated gaps join their
  neighbors seamlessly while scoring 0.153 to 0.233 confidence.
- The confidence score is not decorative: held-out validation shows
  rho -0.392 against true reconstruction error, and it outranks plain
  distance-to-sample. Above 0.6 confidence the median error is 0.0.
- The score drives a decision: the `counts_toward_pr` field in the
  pipeline output, with the reason attached (added in the commit
  following this audit).
- The failure lands where it matters: dropouts were injected
  motion-weighted, and in-set gaps score 0.437 mean confidence against
  0.679 for rest gaps, so the uncertainty concentrates exactly where
  rep decisions happen.

## What parts of the prompt are addressed well?

"Prototype": yes. It runs end to end from raw CSVs to a decision field
and a viewer, and every claim regenerates from two scripts. "A
feature/system": the system is complete at prototype scope; the
feature exists in one concrete slice (flags, explanations, PR gate).
"Excited": the artifacts show engagement beyond the minimum, a
validation experiment, an honest findings section, a viewer built
around the one idea. Excitement is easier to claim than demonstrate,
but the follow-through is on file.

## What parts are addressed weakly?

"Own" is the weak word. Ownership means accountability for behavior in
the world, and this prototype has never touched the world: invented
dropouts, one participant, no real-time path, no user reaction to a
flagged rep, rep counts unvalidated against ground truth. The feature
surface is thin: one decision consumer (PRs), and the streaks and
recommendations policies are stated in prose, not implemented. A
skeptical reader can fairly say this is a well-instrumented pipeline
with one product decision attached, and the distance from there to an
ownable production feature is the majority of the work.

## If Paul spent three minutes on this, what would he remember?

Most likely: "the deadlift double-count story," because it is concrete,
self-inflicted, honestly told, and shows the failure mode the whole
project is about (plausible wrong numbers). Second: "they deleted
samples, kept the originals, and checked their confidence score
against truth," because take-homes almost never audit themselves.
Third, less flattering and also true: "all of it is synthetic failure
on one person's data." If he remembers one sentence, the submission
wants it to be "wrong numbers do not look wrong, so the pipeline has
to say how sure it is," and the repo gives that sentence evidence.
