# Data source

Raw sensor recordings in `raw/MetaMotion/` are copied from the open
dataset in EfthimiosVlahos/SmartLift-Analysis-Project on GitHub:
https://github.com/EfthimiosVlahos/SmartLift-Analysis-Project

That project is itself a rebuild of a wearable strength-training study
from Vrije Universiteit Amsterdam. Data was recorded with an MbientLab
MetaMotion sensor worn to simulate smartwatch placement, capturing
accelerometer and gyroscope readings during barbell exercises.

Only participant A's single-day session (2019-01-11, 12 sets across
bench, overhead press, squat, and deadlift) is used here. No modification
was made to the raw files themselves; all corruption and reconstruction
happens downstream in this pipeline, not on the source data.
