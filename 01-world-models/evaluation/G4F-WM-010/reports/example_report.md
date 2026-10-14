# Scenario prediction and calibration report (G4F-WM-010)

Seed 0, 500 bootstrap resamples, 10 bins. 95% percentile intervals in brackets.
- `predictions.csv` sha256 `ed71c66e6c08887a8465bbd95acb2a7619b7aa2dadd07e21c5a71d2368448feb`
- `outcomes.csv` sha256 `006a3231cb632de1390ad0faae585674db418e4b39df420ecfb6a919f56c4e08`

> Results are computed on simulated trajectories. They say how well the predictor matches the simulator, not how it would perform on real borrowers. Real-world validity needs validation on real outcome data.

## Warnings

None. No scenario is below 100 rows, 10 events, 10 non-events or 10 observations of any next state.

## Binary event, per scenario

| scenario | n | events | observed | mean pred | Brier | log loss | ROC AUC | PR AUC |
|---|---|---|---|---|---|---|---|---|
| baseline | 1200 | 90 | 0.0750 | 0.0809 | 0.0647 [0.0543, 0.0769] | 0.2392 | 0.7404 [0.6871, 0.7979] | 0.2119 |
| normal | 1200 | 112 | 0.0933 | 0.0932 | 0.0772 [0.0655, 0.0892] | 0.2772 | 0.7382 [0.6868, 0.7797] | 0.2818 |
| stress | 800 | 198 | 0.2475 | 0.0950 | 0.1945 [0.1731, 0.2180] | 0.6176 | 0.7073 [0.6670, 0.7485] | 0.4470 |

## Calibration, per scenario

Mean pred minus observed is calibration in the large (negative means the model under-predicts). The bin count next to MCE width is the size of the bin that sets it.

| scenario | mean pred - observed | ECE width | ECE mass | MCE width | MCE mass |
|---|---|---|---|---|---|
| baseline | 0.0059 | 0.0099 [0.0057, 0.0262] | 0.0165 | 0.1998 (n=3) | 0.0361 |
| normal | -0.0002 | 0.0062 [0.0067, 0.0270] | 0.0141 | 0.3770 (n=6) | 0.0299 |
| stress | -0.1525 | 0.1531 [0.1259, 0.1835] | 0.1525 | 0.4491 (n=2) | 0.2998 |

ECE adds up absolute gaps, so sampling noise tends to push it up, and every bootstrap resample adds a second round of noise on top. The resampled values therefore sit above the point value, and for a well calibrated scenario the point value can fall below its own interval. That says the gap is within noise, not that the interval is wrong. The debiased reliability in the next table removes the noise term directly. Here the point value is outside its interval for: normal.

## Brier decomposition (equal-width bins)

| scenario | Brier | reliability | reliability debiased | resolution | uncertainty | within bin |
|---|---|---|---|---|---|---|
| baseline | 0.0647 | 0.0003 | -0.0008 | 0.0046 | 0.0694 | -0.0004 |
| normal | 0.0772 | 0.0008 | -0.0002 | 0.0072 | 0.0846 | -0.0010 |
| stress | 0.1945 | 0.0273 | 0.0259 | 0.0168 | 0.1862 | -0.0022 |

Brier = reliability - resolution + uncertainty + within bin. Reliability is the squared calibration error. The debiased version subtracts each bin's binomial sampling variance (Kumar, Liang and Ma 2019) and is not part of the sum; a value near or below 0 means the remaining calibration gap is within sampling noise.

## Binary event by horizon

| scenario | horizon | n | events | observed | mean pred | Brier | ECE width |
|---|---|---|---|---|---|---|---|
| baseline | 6 | 600 | 37 | 0.0617 | 0.0732 | 0.0543 | 0.0169 |
| baseline | 12 | 600 | 53 | 0.0883 | 0.0887 | 0.0750 | 0.0104 |
| normal | 6 | 600 | 49 | 0.0817 | 0.0833 | 0.0713 | 0.0171 |
| normal | 12 | 600 | 63 | 0.1050 | 0.1030 | 0.0832 | 0.0163 |
| stress | 6 | 400 | 78 | 0.1950 | 0.0833 | 0.1597 | 0.1131 |
| stress | 12 | 400 | 120 | 0.3000 | 0.1068 | 0.2293 | 0.1951 |

## Next-state transition, per scenario

| scenario | multi-class Brier | log loss | accuracy |
|---|---|---|---|
| baseline | 0.2940 | 0.5527 | 0.8167 |
| normal | 0.3485 | 0.6392 | 0.7800 |
| stress | 0.5850 | 1.0192 | 0.5988 |

## Next-state calibration by class (one-vs-rest)

| scenario | next state | observed n | observed share | mean pred | Brier | ECE width | MCE width |
|---|---|---|---|---|---|---|---|
| baseline | current | 981 | 0.8175 | 0.8023 | 0.1360 | 0.0162 | 0.1947 (n=17) |
| baseline | delinquent | 129 | 0.1075 | 0.1167 | 0.0933 | 0.0134 | 0.0302 (n=85) |
| baseline | default | 90 | 0.0750 | 0.0809 | 0.0647 | 0.0099 | 0.1998 (n=3) |
| normal | current | 929 | 0.7742 | 0.7847 | 0.1582 | 0.0288 | 0.3606 (n=12) |
| normal | delinquent | 159 | 0.1325 | 0.1221 | 0.1131 | 0.0104 | 0.0170 (n=446) |
| normal | default | 112 | 0.0933 | 0.0932 | 0.0772 | 0.0062 | 0.3770 (n=6) |
| stress | current | 475 | 0.5938 | 0.7809 | 0.2551 | 0.1872 | 0.2970 (n=18) |
| stress | delinquent | 127 | 0.1588 | 0.1241 | 0.1354 | 0.0347 | 0.0728 (n=281) |
| stress | default | 198 | 0.2475 | 0.0950 | 0.1945 | 0.1531 | 0.4491 (n=2) |

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
