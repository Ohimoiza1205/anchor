# Founder Review

Written as a founder reviewing an intern take-home, one of dozens.
Every criticism ends with what was done about it in this session, or
why it was not fixable within a take-home.

## Reasons To Reject

**Everything is tuned and evaluated on the same eight minutes of data.**
One participant, one day, twelve sets. The 1.4 second peak spacing, the
volatility window, the turning-point penalty, the 0.6 threshold: all
set by looking at this session, all evaluated on this session. The
deadlift bug is presented as a finding, but it is also proof that the
first untested movement pattern broke the detector. A second
participant would likely break something else, and we would not know
what until it happened.
Disposition: not fixed. The source dataset contains other participants,
but pulling new raw data into the repository mid-review would change
the dataset story without time to redo the tuning honestly. It is the
first thing to do after submission, and the Limitations section says
there is no basis for assuming thresholds transfer.

**The failure model is fiction.** The entire confidence system responds
to dropouts we invented: onset hazard, lognormal durations, motion
correlation, all chosen because they sounded plausible. No BLE log from
any device was consulted. If real dropouts are bursty, longer, or
triggered by distance rather than motion, every distribution in this
project shifts by an unknown amount.
Disposition: not fixable here; requires hardware logs we do not have.
Stated bluntly in Limitations. The validation experiment added this
session is explicitly labeled as internal-consistency evidence only.

**The confidence score was never tested against error until this
review forced it.** The pipeline deleted samples itself, kept the true
values, and for the whole project prior to this session nobody checked
whether low confidence actually meant high reconstruction error. That
check cost one script.
Disposition: fixed this session. `src/validate_reconstruction.py`
measures error on the 155 held-out samples: Spearman rho of -0.392
between confidence and absolute error, error medians collapsing to 0.0
above confidence 0.6, and an inconvenient middle band (0.4 to 0.6)
holding the worst single error (0.9463 g). Results and caveats are in
the README Findings.

**Rep counts are unvalidated, and the headline finding depends on
them.** The deadlift story says the count went from 20 to 11. Nobody
knows the participant did 11 reps. The timing structure supports it,
but "consistent with" is not "correct," and the README's 89 total reps
carries the same asterisk.
Disposition: not fixable; the dataset ships no rep labels or video.
Limitations now says this in its first paragraph rather than burying
it.

**It is an offline pipeline being pitched with real-time language.**
Dropouts, reps, confidence: all computed after the session is complete,
with the right edge of every gap available. A live product does not
have the right edge. The turning-point check, the strongest part of the
confidence design, cannot run until the gap closes, and nobody has
designed what the user sees during those seconds.
Disposition: not fixable in scope; a real-time variant is a different
design. Limitations states what breaks (interpolation and the
turning-point check both need the far edge) instead of hand-waving
that it could be streamed.

**Confidence was computed and then used for almost nothing.** As
submitted for review, the pipeline scores every sample and rep, and the
only consumers are a viewer and a text flag. No decision changes
because a number is low. That is instrumentation, not a feature.
Disposition: accepted, fix scheduled in this session as its own
change: a personal-record gate where reps below 0.6 confidence do not
count toward a PR, with the reason attached in the pipeline output, as
the first decision consumer. One decision is a start, not a product.
(If the commit adding `counts_toward_pr` to `build_session.py` is not
in the history after this one, the fix did not land and this criticism
stands in full.)

**User value is asserted, not observed.** No user has seen the flagged
reps, the explanations, or the viewer. Whether "measured 8, estimated
1" builds trust or reads as the product making excuses for its own
hardware is exactly the kind of question this team would care about,
and the prototype has no evidence either way. Flag fatigue is untested:
4 flags out of 89 reps is tolerable, but a worse radio could flag a
third of a session.
Disposition: not fixable in a take-home with no users. The Product
Implications section takes positions (records vs streaks asymmetry, no
mid-set interruptions) so there is at least a testable stance on file.

**The demo timeline is not real time.** Rest periods are compressed up
to 20x. Anyone screenshotting the viewer sees a session that did not
happen at that pace. Disclosed in the README, invisible in the viewer
itself.
Disposition: documented, not fixed in the interface. Adding a
disclosure line to the viewer is cheap and should happen in the design
pass; if it does not fit the ten-second read it stays a README
disclosure.

## Reasons To Advance

**The deadlift bug was caught, diagnosed, and honestly reported.** The
detector returned a plausible wrong number; the intern checked
rep-to-rep timing, found the alternating 1.0 second gaps, identified
the two-peaks-per-rep cause, and wrote it up as a failure of their own
assumption rather than a quirk of the data. That is the debugging
instinct we hire for.

**The measured/synthetic boundary is clean and never blurred.** Raw
files untouched, corruption injected downstream, every document states
which side of the line each number lives on. This is rarer in
take-homes than it should be.

**The confidence design has a non-obvious insight in it.** Distance
decay is what everyone builds first. The finding that distance explains
less than gap context (spread 0.229 to 0.814 within the closest
distance bucket), and that slope reversal across a gap is the signal
worth penalizing, shows actual thought about failure modes. The
validation run backs it: combined confidence outranks distance alone.

**Every number is regenerable.** Two scripts reproduce every figure in
the README from the committed data. Claims and evidence stay attached.

**Product judgment shows up where it counts.** The records/streaks
asymmetry (low-confidence reps count toward streaks but not records,
because the dropout is the system's fault, and a record is a claim of
evidence) is a defensible product position stated as a decision, not a
hedge.

## Follow Up Questions

1. If the validation had shown no correlation between confidence and
   error, what would you have done, shipped it anyway, retuned the
   weights against the error data, or cut the feature?
2. What statistics of a real BLE dropout log would you fit first, and
   which would change your design rather than your parameters?
3. Design the real-time version of the turning-point check: what do
   you emit while the gap is still open, and what do you revise when it
   closes?
4. Run this on participant B tomorrow. What breaks first, and what is
   your test for noticing?
5. The 0.4 to 0.6 confidence band holds your worst reconstruction
   error. Why, and what does that do to a hard 0.6 product threshold?
6. Why linear interpolation when the gyroscope stream is right there?
   What would cross-signal reconstruction cost you in explainability?
7. How would you measure whether the flagged-rep explanations increase
   or decrease a user's trust in the product?
