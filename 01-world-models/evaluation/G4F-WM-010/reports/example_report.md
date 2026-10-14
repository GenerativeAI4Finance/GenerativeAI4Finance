# Scenario prediction and calibration report (G4F-WM-010)

Seed 0, 500 bootstrap resamples, 10 bins. 95% percentile intervals in brackets.
- `predictions.csv` sha256 `ed71c66e6c08887a8465bbd95acb2a7619b7aa2dadd07e21c5a71d2368448feb`
- `outcomes.csv` sha256 `006a3231cb632de1390ad0faae585674db418e4b39df420ecfb6a919f56c4e08`

> Results are computed on simulated trajectories. They say how well the predictor matches the simulator, not how it would perform on real borrowers. Real-world validity needs validation on real outcome data.

## Binary event, per scenario

| scenario | n | events | observed | mean pred | Brier | log loss | ROC AUC | PR AUC | ECE width | ECE mass |
|---|---|---|---|---|---|---|---|---|---|---|
| baseline | 1200 | 90 | 0.0750 | 0.0809 | 0.0647 [0.0543, 0.0769] | 0.2392 | 0.7404 [0.6871, 0.7979] | 0.2119 | 0.0099 [0.0057, 0.0262] | 0.0165 |
| normal | 1200 | 112 | 0.0933 | 0.0932 | 0.0772 [0.0655, 0.0892] | 0.2772 | 0.7382 [0.6868, 0.7797] | 0.2818 | 0.0062 [0.0067, 0.0270] | 0.0141 |
| stress | 800 | 198 | 0.2475 | 0.0950 | 0.1945 [0.1731, 0.2180] | 0.6176 | 0.7073 [0.6670, 0.7485] | 0.4470 | 0.1531 [0.1259, 0.1835] | 0.1525 |

## Brier decomposition

| scenario | Brier | reliability | resolution | uncertainty | within bin |
|---|---|---|---|---|---|
| baseline | 0.0647 | 0.0003 | 0.0046 | 0.0694 | -0.0004 |
| normal | 0.0772 | 0.0008 | 0.0072 | 0.0846 | -0.0010 |
| stress | 0.1945 | 0.0273 | 0.0168 | 0.1862 | -0.0022 |

## Next-state transition, per scenario

| scenario | multi-class Brier | log loss | accuracy |
|---|---|---|---|
| baseline | 0.2940 | 0.5527 | 0.8167 |
| normal | 0.3485 | 0.6392 | 0.7800 |
| stress | 0.5850 | 1.0192 | 0.5988 |

## Reliability, baseline (equal-width bins)

| bin | n | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 881 | 0.0467 | 0.0420 |
| 0.1-0.2 | 233 | 0.1384 | 0.1202 |
| 0.2-0.3 | 65 | 0.2401 | 0.2769 |
| 0.3-0.4 | 15 | 0.3468 | 0.3333 |
| 0.4-0.5 | 3 | 0.4364 | 0.3333 |
| 0.5-0.6 | 3 | 0.5331 | 0.3333 |
| 0.6-0.7 | 0 | n/a | n/a |
| 0.7-0.8 | 0 | n/a | n/a |
| 0.8-0.9 | 0 | n/a | n/a |
| 0.9-1.0 | 0 | n/a | n/a |

## Reliability, normal (equal-width bins)

| bin | n | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 804 | 0.0495 | 0.0510 |
| 0.1-0.2 | 272 | 0.1375 | 0.1360 |
| 0.2-0.3 | 88 | 0.2411 | 0.2045 |
| 0.3-0.4 | 28 | 0.3433 | 0.3571 |
| 0.4-0.5 | 6 | 0.4564 | 0.8333 |
| 0.5-0.6 | 2 | 0.5128 | 0.5000 |
| 0.6-0.7 | 0 | n/a | n/a |
| 0.7-0.8 | 0 | n/a | n/a |
| 0.8-0.9 | 0 | n/a | n/a |
| 0.9-1.0 | 0 | n/a | n/a |

## Reliability, stress (equal-width bins)

| bin | n | mean predicted | observed |
|---|---|---|---|
| 0.0-0.1 | 526 | 0.0515 | 0.1635 |
| 0.1-0.2 | 199 | 0.1388 | 0.3668 |
| 0.2-0.3 | 54 | 0.2402 | 0.4630 |
| 0.3-0.4 | 13 | 0.3270 | 0.6923 |
| 0.4-0.5 | 5 | 0.4488 | 0.4000 |
| 0.5-0.6 | 2 | 0.5509 | 1.0000 |
| 0.6-0.7 | 0 | n/a | n/a |
| 0.7-0.8 | 1 | 0.7235 | 1.0000 |
| 0.8-0.9 | 0 | n/a | n/a |
| 0.9-1.0 | 0 | n/a | n/a |
