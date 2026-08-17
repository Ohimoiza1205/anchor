# AI process notes

Fort's prompt asks for a copy of some or all of the AI sessions used to build
this. This is a straight account of what that process looked like, not a
cleaned-up version of it.

## How the direction was chosen

The starting idea, a "data confidence" feature for wearable sensor gaps,
came out of a planning conversation with Claude before any code existed. Two
independent framings of the same idea got compared against each other and
against Fort's own prompt wording before committing to it: an early version
leaned toward an LLM generating narrative insights from workout stats
("compared to your last six deadlift sessions..."). That direction was
rejected during the planning conversation itself, on the grounds that it was
a prompt-engineering trick any candidate could produce, not something that
demonstrated engineering judgment. The confidence-scoring direction was kept
because it extended real prior work (a backpressure-handling telemetry
service) into a new failure mode, rather than starting from a feature idea
with no technical backbone.

## Dataset

Claude was asked to find an open dataset of wrist-worn motion sensor data
during actual training. It searched, found a candidate that only pointed to
an external archive rather than hosting the data directly, kept searching,
and located SmartLift-Analysis-Project, which had the raw sensor files
checked into the repository itself. That one was verified by cloning it and
inspecting the raw CSVs directly before committing to it as the data
source.

## Building the pipeline

The stitching, dropout injection, interpolation, and confidence scoring
were built and run iteratively, not written once and trusted. Two rounds of
tuning happened because the first version's numbers were checked and found
uninformative: the first dropout rate was too low to produce more than one
gap in the entire session, and the first confidence formula scored nearly
every reconstructed point close to zero regardless of context. Both were
adjusted and rerun until the output showed a real, checkable pattern
(confidence during rest-period gaps averaging meaningfully higher than
confidence during mid-rep gaps).

## The deadlift bug

The rep counter's first run reported twenty reps on a thirty-one second
deadlift set. That number was not accepted at face value. Checking the
spacing between detected reps showed it alternating between roughly one
second and two seconds, not a consistent tempo, which led to the actual
cause: a deadlift has two acceleration peaks per repetition, and the peak
detector, tuned against bench and overhead press, was counting both as
separate reps. The fix was a wider minimum spacing between detected peaks.
This is documented in the README as a finding, not smoothed over.

## Writing the README

The README went through two full rewrites at increasingly strict
constraints: first to remove hedging and inflated language, then a second
pass to strip out anything that read as performing expertise rather than
reporting it, rhetorical closers, aphoristic sentences, self-referential
commentary on how interesting the findings were. The instruction that
shaped the final version most was direct: the work should make the case,
the commentary about how good the work is should not.

## The viewer

Built as a single self-contained HTML file with the session data embedded
directly, so it opens without a server. One real bug was caught before
delivery: the first version of the confidence-based line coloring used an
undocumented Chart.js property that would likely have silently failed
(rendered the whole line in one color with no error). It was caught by
checking Chart.js's own documentation for the correct API rather than
assuming the first attempt was correct, and fixed before the file was
shared.

## What Claude could not verify

Claude does not have a browser in its working environment and could not
visually confirm the chart renders correctly, only that the embedded data
parses and the JavaScript is syntactically valid. That gap was stated
directly rather than implied to be covered. Confirming the actual render
was left as a manual step.

## A delivery mistake worth including

An early version of the packaged project was re-downloaded by mistake
because a zip file was reused under an identical filename and the browser
served a cached copy instead of the updated one. The fix was a fresh
filename and a size check to confirm the right file had actually been
retrieved. Included here because it is a real example of a plausible-looking
result (a completed download) being wrong for a boring, non-obvious reason,
which is the same category of failure this whole project is about.
