# Submission Review

Written as if submitting tomorrow. The goal is prioritization, not a
claim of completeness.

## What feels unfinished

- The decision layer has one consumer. The PR gate is implemented; the
  streak, volume, and recommendation policies exist only as README
  prose. Fine for a prototype, but the gap between "specified" and
  "implemented" is visible.
- Set-level confidence aggregation is named in two places as the fix
  for the bench blind spot (a 0.207-confidence gap invisible at rep
  level) and was never built, despite being a small addition.
- The real-time question is raised, answered with "none of it has been
  designed," and left there. Even a one-page design sketch of what the
  confidence score emits while a gap is open would move this from a
  named hole to a considered one.
- Nothing was run on a second participant, and the source dataset
  contains them.

## What feels speculative

- The notification policy and the "measured 8, estimated 1" mental
  model in Product Implications are stated with confidence and backed
  by no user contact of any kind.
- The flag-fatigue argument (4 of 89 is tolerable) assumes a dropout
  rate we invented.
- The entire dropout model, and therefore every downstream
  distribution, remains speculation dressed in a lognormal.

## What claims need stronger evidence

- "89 reps detected": no ground truth anywhere. The strongest claim we
  can honestly make is that the timing structure is self-consistent.
- The turning-point penalty's value: flagged samples average 0.1427 g
  error vs 0.1285 g unflagged, n=40 vs 115. No significance test was
  run on that difference, and eyeballed, it is small. The finding text
  says "directionally right"; a reviewer could fairly call it noise
  until tested.
- "0.6 has some empirical support": that support is 155 samples of
  synthetic failure on one person. The README says this, but the PR
  gate still hard-codes the number.

## README sections too long or too short

- Key Design Decisions is the longest-winded part: five decisions,
  each with four labeled fields. The discipline is good; at
  submission it reads like a form. Could compress each to a short
  paragraph without losing the alternatives-rejected content.
- Future Work is four thin lines that partially duplicate the
  Limitations closer. Merge or cut.
- Findings is long and earns it. Limitations is long and earns it.
- Dataset and Problem are the right size.

## What a founder would likely ask immediately

1. "Did anyone count the actual reps?" No. Weakest single point.
2. "What does this do live, mid-set?" Nothing; offline only.
3. "Would this survive my hardware's dropout pattern?" Unknown; the
   pattern is invented.
4. "Show me the moment confidence changes something a user sees."
   Answerable: the PR gate line in the viewer. This is the one
   question with a crisp demo answer.
5. "Why didn't you run participant B?" The honest answer is time and
   scope, and it is the first thing to do next.

## If the reviewer had five minutes, what to cut

Keep, in order: Problem statement (30 seconds), the deadlift finding
(the story that shows the failure mode), the held-out validation
finding (the self-audit), the viewer (one screenshot answers what
happened / how certain / why), the PR gate (decision, not chart).
Cut without loss at five minutes: Key Design Decisions, Dataset,
Future Work, everything in docs/. The Limitations section survives as
one sentence spoken aloud: all failure here is synthetic, one person,
offline.

## Remaining improvements ranked by impact

1. Run the pipeline on a second participant from the same dataset and
   report what broke. Highest information per hour of any remaining
   task; directly answers the generalization criticism.
2. Add set-level confidence aggregation. Small, fixes a blind spot the
   findings section already documents, and turns a named weakness into
   a closed one.
3. Significance-test the turning-point error difference (a permutation
   test on the 40/115 split is a few lines in the existing validation
   script). Either the penalty earns its 0.3 weight or the finding
   gets rewritten.
4. One-page real-time design sketch: what is emitted while a gap is
   open, what gets revised at close, what the user sees in between.
5. Compress Key Design Decisions; merge Future Work into Limitations.
6. Implement a second decision consumer (streak counting is specified
   and trivial) so the decision layer is a pattern, not a special
   case.
