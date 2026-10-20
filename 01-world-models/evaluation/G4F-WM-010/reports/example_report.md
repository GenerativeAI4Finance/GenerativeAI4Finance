# Scenario prediction and calibration report (G4F-WM-010)

Seed 0, 500 bootstrap resamples, 10 bins. 95% percentile intervals in brackets.
- `predictions.csv` sha256 `d9dd9c7e21f4df3c4506d22f2d2073a28c66d576e648093235075bbd62a320ce`
- `outcomes.csv` sha256 `1c7a8be6a119bcfe1aded3f646fe0adad9912b92f96ddce5125f30b1a29e1e2f`

> Results are computed on simulated trajectories. They say how well the predictor matches the simulator, not how it would perform on real borrowers. Real-world validity needs validation on real outcome data.

## Warnings

- baseline: events = 3 is below the minimum of 10: ROC AUC, PR AUC and the calibration metrics are unstable
- baseline: next state 'delinquent' has 9 observations, below the minimum of 10: its one-vs-rest calibration is unstable
- baseline: next state 'default' has 3 observations, below the minimum of 10: its one-vs-rest calibration is unstable
- normal: events = 8 is below the minimum of 10: ROC AUC, PR AUC and the calibration metrics are unstable
- normal: next state 'default' has 8 observations, below the minimum of 10: its one-vs-rest calibration is unstable

## Binary event, per scenario

| scenario | n | events | observed | mean pred | Brier | log loss | ROC AUC | PR AUC |
|---|---|---|---|---|---|---|---|---|
| baseline (see warnings) | 100 | 3 | 0.0300 | 0.0609 | 0.0305 [0.0055, 0.0617] | 0.1433 | 0.5945 [0.2504, 0.9899] | 0.1940 |
| normal (see warnings) | 100 | 8 | 0.0800 | 0.0881 | 0.0576 [0.0290, 0.1000] | 0.2059 | 0.9008 [0.7746, 0.9904] | 0.5801 |
| stress | 100 | 17 | 0.1700 | 0.1033 | 0.1374 [0.0918, 0.1887] | 0.4379 | 0.7300 [0.6234, 0.8446] | 0.3226 |

## Calibration, per scenario

Mean pred minus observed is calibration in the large (negative means the model under-predicts). The bin count next to MCE width is the size of the bin that sets it.

| scenario | mean pred - observed | ECE width | ECE mass | MCE width | MCE mass |
|---|---|---|---|---|---|
| baseline (see warnings) | 0.0309 | 0.0309 [0.0111, 0.0618] | 0.0546 | 0.2108 (n=1) | 0.1093 |
| normal (see warnings) | 0.0081 | 0.0591 [0.0360, 0.1079] | 0.0608 | 0.4142 (n=4) | 0.2357 |
| stress | -0.0667 | 0.0810 [0.0354, 0.1569] | 0.0819 | 0.1792 (n=4) | 0.2056 |

ECE adds up absolute gaps, so sampling noise tends to push it up, and every bootstrap resample adds a second round of noise on top. The resampled values therefore sit above the point value, and for a well calibrated scenario the point value can fall below its own interval. That says the gap is within noise, not that the interval is wrong. The debiased reliability in the next table removes the noise term directly.

## Brier decomposition (equal-width bins)

| scenario | Brier | reliability | reliability debiased | resolution | uncertainty | within bin |
|---|---|---|---|---|---|---|
| baseline (see warnings) | 0.0305 | 0.0017 | 0.0009 | 0.0002 | 0.0291 | -0.0002 |
| normal (see warnings) | 0.0576 | 0.0097 | 0.0032 | 0.0261 | 0.0736 | 0.0004 |
| stress | 0.1374 | 0.0079 | -0.0001 | 0.0075 | 0.1411 | -0.0042 |

Brier = reliability - resolution + uncertainty + within bin. Reliability is the squared calibration error. The debiased version subtracts each bin's binomial sampling variance (Kumar, Liang and Ma 2019) and is not part of the sum; a value near or below 0 means the remaining calibration gap is within sampling noise.

## Binary event by horizon

| scenario | horizon | n | events | observed | mean pred | Brier | ECE width |
|---|---|---|---|---|---|---|---|
| baseline | 6 | 50 | 0 | 0.0000 | 0.0574 | 0.0050 | 0.0574 |
| baseline | 12 | 50 | 3 | 0.0600 | 0.0644 | 0.0560 | 0.0079 |
| normal | 6 | 50 | 2 | 0.0400 | 0.0673 | 0.0249 | 0.0750 |
| normal | 12 | 50 | 6 | 0.1200 | 0.1088 | 0.0904 | 0.0431 |
| stress | 6 | 50 | 9 | 0.1800 | 0.1053 | 0.1381 | 0.0747 |
| stress | 12 | 50 | 8 | 0.1600 | 0.1014 | 0.1366 | 0.0920 |

## Next-state transition, per scenario

| scenario | multi-class Brier | log loss | accuracy |
|---|---|---|---|
| baseline | 0.2136 | 0.4246 | 0.8800 |
| normal | 0.3053 | 0.5599 | 0.8100 |
| stress | 0.4522 | 0.7999 | 0.6900 |

## Next-state calibration by class (one-vs-rest)

| scenario | next state | observed n | observed share | mean pred | Brier | ECE width | MCE width |
|---|---|---|---|---|---|---|---|
| baseline | current | 88 | 0.8800 | 0.8351 | 0.1041 | 0.0513 | 0.4010 (n=1) |
| baseline | delinquent | 9 | 0.0900 | 0.1040 | 0.0790 | 0.0500 | 0.7978 (n=1) |
| baseline | default | 3 | 0.0300 | 0.0609 | 0.0305 | 0.0309 | 0.2108 (n=1) |
| normal | current | 80 | 0.8000 | 0.7924 | 0.1413 | 0.0680 | 0.3690 (n=1) |
| normal | delinquent | 12 | 0.1200 | 0.1195 | 0.1064 | 0.0493 | 0.2140 (n=8) |
| normal | default | 8 | 0.0800 | 0.0881 | 0.0576 | 0.0591 | 0.4142 (n=4) |
| stress | current | 70 | 0.7000 | 0.7706 | 0.2012 | 0.0978 | 0.7016 (n=1) |
| stress | delinquent | 13 | 0.1300 | 0.1260 | 0.1136 | 0.0257 | 0.0565 (n=12) |
| stress | default | 17 | 0.1700 | 0.1033 | 0.1374 | 0.0810 | 0.1792 (n=4) |

## Reliability, baseline (equal-width bins)

| bin | n | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 82 | 0.0438 | 0.0244 |
| 0.1-0.2 | 17 | 0.1345 | 0.0588 |
| 0.2-0.3 | 1 | 0.2108 | 0.0000 |
| 0.3-0.4 | 0 | n/a | n/a |
| 0.4-0.5 | 0 | n/a | n/a |
| 0.5-0.6 | 0 | n/a | n/a |
| 0.6-0.7 | 0 | n/a | n/a |
| 0.7-0.8 | 0 | n/a | n/a |
| 0.8-0.9 | 0 | n/a | n/a |
| 0.9-1.0 | 0 | n/a | n/a |

## Reliability, normal (equal-width bins)

| bin | n | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 69 | 0.0500 | 0.0145 |
| 0.1-0.2 | 22 | 0.1321 | 0.0909 |
| 0.2-0.3 | 5 | 0.2213 | 0.4000 |
| 0.3-0.4 | 4 | 0.3358 | 0.7500 |
| 0.4-0.5 | 0 | n/a | n/a |
| 0.5-0.6 | 0 | n/a | n/a |
| 0.6-0.7 | 0 | n/a | n/a |
| 0.7-0.8 | 0 | n/a | n/a |
| 0.8-0.9 | 0 | n/a | n/a |
| 0.9-1.0 | 0 | n/a | n/a |

## Reliability, stress (equal-width bins)

| bin | n | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 65 | 0.0500 | 0.1077 |
| 0.1-0.2 | 22 | 0.1386 | 0.2727 |
| 0.2-0.3 | 9 | 0.2575 | 0.3333 |
| 0.3-0.4 | 0 | n/a | n/a |
| 0.4-0.5 | 4 | 0.4292 | 0.2500 |
| 0.5-0.6 | 0 | n/a | n/a |
| 0.6-0.7 | 0 | n/a | n/a |
| 0.7-0.8 | 0 | n/a | n/a |
| 0.8-0.9 | 0 | n/a | n/a |
| 0.9-1.0 | 0 | n/a | n/a |
