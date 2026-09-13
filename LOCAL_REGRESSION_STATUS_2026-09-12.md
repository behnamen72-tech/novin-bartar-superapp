# Local Regression Status — 2026-09-12

## Frontend deterministic regression

Completed successfully on the current execution-ready artifact:

- B6.3: 13 assertions passed
- B6.4: 11 assertions passed
- B6.5: 18 assertions passed
- B6.6: 37 assertions passed
- B6.7: 40 assertions passed
- B6.8: 36 assertions passed
- C1: 43 assertions passed
- C2: 29 assertions passed
- C3: 19 assertions passed
- D1: 47 assertions passed
- D2: 56 assertions passed
- D3: 57 assertions passed

**Total: 406 deterministic assertions passed.**

## Backend regression attempt

The current local environment is Python 3.13 while CI is intentionally pinned to
Python 3.12. A broader per-file pytest sweep was started. Multiple files produced
clean pass results, but the overall container execution hit its timeout before the
full sweep completed. No full-regression pass is claimed from this attempt.

The dedicated D3 suite was separately rerun and completed normally: **15 passed**.
The authoritative full-backend result remains the required Python 3.12 networked CI job.
