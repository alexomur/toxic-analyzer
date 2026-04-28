# Model Evolution

This document keeps only the high-level history of the baseline. Detailed experiment logs, mismatch reports, and one-off review notes do not need to stay in the main documentation flow.

## Goal

The model solves binary toxicity classification for Russian-language mixed UGC:

- input: comment text
- output: `label` and `toxic_probability`

The working definition of toxicity is based on directed verbal aggression, not on general negativity.

## V1

First reproducible baseline:

- word and character `TF-IDF`
- `LogisticRegression`
- calibration and thresholding

Why it existed:

- easy to reproduce
- easy to explain
- strong enough as a real starting point

Main weakness:

- weak on short, implicit, and context-sensitive attacks

## V2

Strengthened baseline without changing the overall class of the model.

Added:

- sparse expert features
- hard-case evaluation slice
- seed examples for underrepresented toxic patterns

Main result:

- better handling of targeted and disguised toxicity
- still limited by data quality and annotation consistency

## V3 series

The main focus moved from feature tweaks to data quality.

What changed:

- systematic mismatch analysis
- manual review of noisy slices
- retraining on cleaner data
- versioned artifacts and reports

### V3.1

Stabilized the runtime and artifact versioning after the first large cleanup pass.

### V3.2

Improved precision on reviewed Habr-like slices after a deeper label cleanup.

### V3.3

Improved overall quality and especially `dvach`-related performance after a full mismatch review and retraining pass. This is the current baseline line referenced by the runtime and default artifact names.

## Main takeaway

The strongest improvements so far came from improving labels and review workflow, not from replacing the baseline architecture. The next useful iteration should start from fresh mismatch analysis on top of the current baseline rather than from ad hoc feature growth.
