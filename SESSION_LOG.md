# Session log, 2026-08-16

What happened in each phase, what we were unsure about, and what was
skipped or could not be verified. Written to be read first.

## Phase 0: baseline verification

Ran `python src/build_session.py`. Output matched the expected numbers
exactly: 12 sets, 476.4s, 3.3% dropout, 89 reps, 4 flagged. The
regenerated `output/session.json` was byte-identical to the committed
one (the pipeline seeds its RNG), so the Phase 0 commit is an empty
checkpoint commit with the verification recorded in its message.

## Phase 1: analysis script

Added `src/analyze_findings.py` (written by a subagent, then rerun and
checked in the main session). It reads `output/session.json` only and
prints: gap split by location, confidence vs distance, per-exercise
stats, smooth-but-low-confidence gap examples, highest-confidence gap
examples, and the deadlift rep-gap timings at 1.0s and 1.4s minimum
peak spacing.

One planned output did not exist in the data: the script was asked for
gaps where confidence stayed at or above 0.8 throughout, and there are
none in this run. The practical per-sample ceiling is 0.814 (one grid
step of distance decay times the 0.9 monotonic edge penalty). The
script says this in its own output and reports the highest-confidence
gaps (0.775 to 0.788, all short rest-period gaps) instead. This is
reported as a finding rather than papered over.

## Phase 2: Findings section

Replaced the README's "Unexpected Findings" with a "Findings" section:
six findings, each with observation, evidence, why it surprised us, and
design impact. Every number comes from the Phase 1 script run in this
session. The old README's "20 reps in 31 seconds" phrasing became "309
samples, 30.9 seconds of lifting," which is what the data shows; we did
not carry the old number forward unverified.

## Phase 3: Why This Problem Matters

Rewritten, grounded only in pipeline output: decisions from imperfect
measurements, the deadlift count as a wrong answer formatted like a
right one, uncertainty compounding from sample to rep to aggregate
(with the bench between-reps gap as the counterexample where rep-level
numbers hide sample-level damage), and confidence as a signal
downstream features can consume. No roadmap or business claims.

## Phase 4: Product Implications

Written as decisions: records require confidence at or above 0.6;
streaks and volume totals still count low-confidence reps (the
asymmetry is stated and defended); recommendations are suppressed only
when their specific inputs are low confidence; notification happens in
post-session review only, except sustained degradation. An earlier
draft claimed the PR gate was already implemented in the pipeline; that
was false at the time of that commit (it is Phase 12 work) and the
claim was removed before committing.

## Phase 5: Limitations rewrite

Rewritten to be explicit about: one participant one day, invented
dropout distributions, no ground-truth validation of rep counts or
reconstruction error, linear interpolation only, one global peak
threshold, four barbell exercises only, research-grade sensor rather
than consumer hardware, offline rather than real-time. Ends with the
list of what must exist before any of this informs a product decision.
One item worth flagging: the held-out-samples reconstruction-error
experiment is possible with this exact codebase and was not built. That
is now stated in the README rather than hidden.

## Phase 6: README restructure

New order: Table of Contents, Problem (with Why This Problem Matters as
a subsection), Dataset (new section, from `data/SOURCE.md`), Approach
(Key Design Decisions and What the User Sees folded in as subsections,
content kept), Findings, Product Implications, Limitations, Future
Work. The old "Key Insights" section was removed: two of its three
points were already covered in Findings, and the third (confidence and
correctness are separate properties) moved into Approach.

## Phase 7: viewer redesign

`src/build_viewer.py`'s template was rewritten (by a subagent against a
written design brief) and `viewer.html` regenerated. Confidence is the
primary story: header with four plain numbers, one SVG session timeline
with reconstructed regions banded by confidence, a time-aligned
confidence track, and a plain list of the four flagged reps with their
verbatim explanations. The Chart.js CDN dependency was removed; the
file now makes no network requests.

We could not see the rendered result in this session. No browser was
opened. Verification was static only: the build runs, the embedded JSON
parses and matches `output/session.json` byte for byte, `node --check`
passes on the extracted script, and replicating the JS filtering in
Python yields 89 rep markers, 4 flagged reps, and 155 reconstructed
samples. We claim the design follows the stated principles (no
gradients, no animation, two accent hues, whitespace over borders). We
do not claim it looks good, and label collisions or spacing problems in
the rendered page would not have been caught.

## Phase 8: Q1 answer

`answers/Q1.md` written from the provided Pulse material only, first
person, matching the plain prose style of `answers/Q3.md`. The banned
words and em dashes were avoided; the load-test numbers (179,900
readings, 2,000 devices, 20 seconds, one vCPU) come from the provided
material and cannot be verified from this repository, which is why the
answer attributes them to the load test rather than stating them as
established fact.

## Unresolved uncertainties as of Phase 9

- The deadlift count of 11 is consistent with the timing structure but
  unvalidated against ground truth. Same for all 89 reps.
- The viewer's rendered appearance is unobserved.
- The README table of contents uses GitHub anchor slugs; they follow
  GitHub's standard slugging but were not clicked through.
- `answers/Q3.md` and `AI_PROCESS.md` were left untouched per
  instruction.

Phases 10 through 14 (founder review, Q2 audit, PR-gating decision
layer, design pass, submission review) happen after this log entry and
are appended below when done.
