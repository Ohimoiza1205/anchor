# Founder Review

Written as a founder reviewing an intern take-home, one of dozens.
Every criticism ends with what was done about it in this session, or
why it was not fixable within a take-home.

## Reasons To Reject

**The confidence score was never tested against error until this
review forced it.** The pipeline deleted samples itself and kept the
true values, yet whether low confidence actually meant high
reconstruction error went unchecked for the whole project, and the
check cost one script. Fixed this session:
`src/validate_reconstruction.py` measures error on the 155 held-out
samples (Spearman rho of -0.392 between confidence and absolute error,
worst single error 0.9463 g sitting in the 0.4 to 0.6 band), with
results and caveats in the README Findings.

**Confidence was computed and then used for almost nothing.** As
submitted for review, the pipeline scored every sample and rep, but the
only consumers were a viewer and a text flag: instrumentation, not a
feature. Fixed this session with the first decision consumer, a
personal-record gate where reps below 0.6 confidence do not count
toward a PR, with the reason attached in the pipeline output; one
decision is a start, not a product.

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
