# G4F-GNPA-001: Early-warning prediction target

**Status:** Draft target specification  
**Specification version:** 1.0  
**Jurisdiction and framework:** India; Reserve Bank of India (RBI) prudential income recognition, asset classification and provisioning (IRACP) rules for commercial banks  
**Regulatory reference point:** RBI Commercial Banks – Income Recognition, Asset Classification and Provisioning Directions, 2025, updated as on 1 October 2026  
**Checked:** 19 November 2026

## 1. Purpose

Define a reproducible, time-bounded target for an early-warning model that estimates whether an eligible borrower will newly enter non-performing asset (NPA) status within a fixed prediction window. The target is a research and model-evaluation label. It does not determine a bank's regulatory classification, provisioning, lending action, or customer treatment.

This specification uses India and RBI commercial-bank rules as its concrete context because GNPA is the requested outcome. A deployment in another jurisdiction, or in a different RBI-regulated institution category, must replace the population and classification rules with the applicable local framework before labels are produced.

## 2. Prediction unit and cohort

- **Unit:** one `bank_id × borrower_id` relationship at an observation date. Use a stable pseudonymous borrower key and a stable bank key.
- **Why borrower-level:** under the cited RBI commercial-bank directions, if one exposure of a borrower is classified as NPA, the bank classifies the borrower's other exposures as NPA as well. Do not independently label each facility as if the regulatory outcome were facility-only.
- **Observation date (`t`):** a date on which the bank's end-of-day classification and exposure snapshot is complete. Store the date and the bank's applicable timezone. Feature values must have been available to the model by the documented prediction cut-off on `t`.
- **Eligible population at `t`:** active borrower-bank relationships with at least one in-scope funded credit exposure and a verified `standard` classification at `t`. A borrower with any exposure already classified NPA at `t` is ineligible for this incident-onset target. Include prior cured or restructured borrowers only if they are standard at `t`; preserve prior-NPA and restructuring indicators so these cohorts can be separately reported.
- **Out of scope for this baseline:** investments/NPI, non-bank lenders, and institution types whose RBI rules differ. Agricultural crop-season cases and other specialised products can be included only after their applicable classification logic is separately implemented and validated. The applicable bank rule may extend beyond the common 90-day examples below.

## 3. Target definition

**Primary target name:** `new_npa_within_90d`

For an eligible borrower-bank relationship observed at `t`, define the prediction interval as the 90 calendar days after the observation date, **`(t, t + 90 calendar days]`**, using the bank's date and end-of-day classification convention.

- **Positive (`1`):** the bank's authoritative classification history records the first date the borrower-bank relationship enters NPA status on any date in the prediction interval. Use the borrower's regulatory classification, including borrower-level propagation from any exposure that triggers NPA status.
- **Negative (`0`):** the relationship is continuously observed through the end of the prediction interval, the status/exposure feed is complete for the full interval, and no NPA entry occurs during it.
- **Censored / unknown (`null`):** the full interval cannot be verified, or a transfer, data-feed gap, merger, sale, or other event prevents establishing the outcome before the interval ends. Do not convert unknown to negative.
- **Already NPA at `t`:** exclude from this incident-onset cohort. Such records can be used for a separate NPA-status or recovery target, not relabelled as new NPA events.

Use the effective NPA classification date from the bank's authoritative system, not a date inferred only from a later report or from a raw days-past-due field. When the effective date is missing or disputed, mark the outcome unresolved and retain the competing evidence for review.

### Required label fields

| Field | Meaning |
|---|---|
| `bank_id`, `borrower_id` | Pseudonymous prediction-unit keys |
| `observation_date` | Date `t` for the feature snapshot |
| `prediction_horizon_days` | `90` for this specification |
| `horizon_end_date` | `observation_date + 90 calendar days` |
| `eligibility_status_at_t` | Verified classification and active-exposure eligibility at observation |
| `target_name` | `new_npa_within_90d` |
| `target_value` | `1`, `0`, or `null` for censored/unresolved |
| `first_npa_effective_date` | First authoritative NPA entry in the horizon, if any |
| `censor_date`, `censor_reason` | Required when the outcome is censored |
| `classification_rule_version` | Bank / regulatory rule version used for the label |
| `source_snapshot_id` | Trace to the classification and exposure data used |

## 4. Keep these concepts separate

- **Delinquency / overdue:** a payment amount is overdue when not paid on the contractual due date under the cited RBI directions. Days past due (DPD) is an ageing measure; it is not by itself the complete regulatory NPA rule for every product.
- **Default:** non-payment after debt becomes due and payable, as defined in the applicable framework. RBI's stressed-assets directions define default separately from NPA; for revolving facilities they also specify an over-limit default condition. A default can therefore occur before NPA classification.
- **NPA:** a prudential asset-classification status. For example, the current RBI commercial-bank directions include more-than-90-day overdue tests for term loans and bills, an `out of order` test for overdraft/cash-credit accounts, and other product-specific tests. The complete current rule set and exceptions must be applied; do not use a generic `DPD > 90` proxy for every product.
- **GNPA:** gross non-performing assets are a bank/portfolio reporting measure, not an individual prediction label. This specification predicts a borrower's entry into NPA status. GNPA reporting aggregates the relevant gross exposure of NPA accounts using the applicable reporting definition, before applicable provisions; it is not the count of positive labels and should not be used as an account-level ground truth.
- **SMA / early stress:** special mention categories and other early-warning signals may be useful predictors, but they are not the target event defined here.

## 5. Edge-case and event treatment

| Case | Primary-target treatment |
|---|---|
| Restructure or resolution plan after `t` | Keep the borrower in the cohort if standard at `t`; retain a time-stamped restructuring indicator. Label `1` if an NPA entry occurs in the horizon under the applicable RBI treatment. Do not reset the target clock or infer that restructuring itself means NPA. Some regulatory resolution paths may retain or restore standard status subject to specific conditions, so use the bank's authoritative classification and the rule version effective on the event date. |
| Restructure before `t` | Eligible only if the authoritative status is standard at `t`. Record restructuring date/type and report performance separately for this cohort. |
| Cure / upgrade during the horizon | If the borrower first entered NPA during the horizon, keep `target_value = 1` even if later upgraded before the horizon ends. This is an **incident** target. If end-of-horizon NPA status is also useful, define and name it as a separate target. |
| Previously cured NPA before `t` | Include only if standard at `t`; preserve prior-NPA history and report a separate stratum. Exclude if historical status or cure date is uncertain. |
| Technical or partial write-off | A technical write-off is an accounting action without waiver of the bank's claim; it is not a cure. Follow authoritative classification, preserve the write-off event/date/amount, and do not set the label to negative solely because the carrying amount changed. RBI directions also state that the remaining part of a partially or technically written-off NPA is not to be shown as standard. |
| Full write-off, settlement, sale, or transfer during horizon | A write-off is not automatically a cure. If an NPA entry is recorded before exit, label positive. If exposure exits before NPA and the post-exit outcome cannot be established, censor at the effective exit date unless a documented, applicable rule and complete records establish the outcome. Do not call an exposure that leaves the bank a negative merely because it disappears from the feed. |
| Payment/default but no NPA entry by horizon end | Negative for this **NPA-entry** target if follow-up is complete. A separate default target may be positive. |
| Data gap, delayed correction, disputed classification date | `null` / unresolved, with reason and source references. Never silently select the convenient date or turn a missing outcome into `0`. |
| Already NPA at observation | Exclude from new-entry cohort; use a separately specified status, recovery, or cure target if needed. |
| Multiple facilities | Determine status at borrower-bank level under applicable rules. The first authoritative borrower-level NPA effective date is the event date; keep facility-level trigger details for audit. |

## 6. Examples

These fictional cases illustrate the label logic only; dates do not assert that a particular payment pattern alone satisfies all RBI rules.

| Case | Observation and observed history | Label | Reason |
|---|---|---:|---|
| A — NPA entry | Standard on 1 Jan 2026; authoritative borrower-level NPA effective date is 15 Mar 2026; complete data through 1 Apr 2026 | `1` | First NPA entry is within `(1 Jan, 1 Apr]`. |
| B — no entry | Standard on 1 Jan 2026; no NPA entry and full status feed through 1 Apr 2026 | `0` | Complete negative follow-up over the whole horizon. |
| C — default before NPA | Standard on 1 Jan 2026; a contractual payment default is recorded on 20 Jan; no NPA entry through 1 Apr; complete feed | `0` | Default and NPA are distinct; this target only labels NPA entry. A separate default target could be `1`. |
| D — NPA then cure | Standard on 1 Jan 2026; first NPA entry on 1 Mar; upgraded to standard on 25 Mar | `1` | The target measures first entry, so a later cure does not erase the event. |
| E — incomplete follow-up | Standard on 1 Jan 2026; feed ends 10 Mar with no NPA recorded; no reliable later status | `null` | The 90-day horizon is not fully observed; censor on 10 Mar. |
| F — existing NPA | Borrower already NPA on 1 Jan 2026 | Excluded | Not eligible for a new-NPA incident target at `t`. |
| G — other facility triggers borrower status | Two facilities are standard on 1 Jan; one exposure causes borrower-level NPA classification on 20 Mar | `1` | Borrower-level classification means the relationship enters NPA even if the other facility had no missed instalment. |

## 7. Leakage controls and audit requirements

1. Build features from records available on or before the documented prediction cut-off on `t`. Do not include later collections, corrected classification outcomes, future financial statements, cure actions, or post-`t` restructuring details as features.
2. Derive labels from a separately versioned outcome/classification history. Preserve effective dates and the source-system snapshot used to assign them.
3. Record the regulatory rule version, bank policy version, timezone/day-end convention, observation date, horizon end, data extract time, and censoring decision.
4. Keep the event history, including NPA entry and any later cure, write-off, settlement, or transfer. Do not overwrite history with the latest status.
5. Report label counts for positive, negative, excluded, censored, and unresolved records. Do not count null labels as negatives.
6. Validate that each positive has a traceable authoritative classification event, and that each negative has verified complete observation over the full horizon.

## 8. Assumptions and limitations

- This is an operational early-warning target for **new borrower-level NPA entry within 90 calendar days**, not a universal definition of credit risk, default, or GNPA.
- India / RBI commercial-bank rules are the chosen reference context. RBI rules are institution-, product-, event-, and date-sensitive. The cited directions apply to the commercial-bank category described in the directions; other lender types and exclusions need their own specification.
- Product-specific NPA triggers, statutory/regulatory relief, restructuring treatment, borrower-level classification, and subsequent amendments must be mapped by the bank's compliance/risk owners before production use. This document is a research specification, not legal advice or a substitute for regulatory interpretation or institutional policy.
- The 90-day horizon is a modelling choice, not a claim that every NPA rule uses a 90-day test. It can be changed only by publishing a new target version and regenerating labels.
- A 90-day horizon gives an incident label, not the amount of GNPA, loss severity, provisioning need, or whether the borrower will remain NPA at the horizon end.
- Label quality depends on complete, correctly dated classification and exposure histories. Unknown status remains censored/unresolved.

## 9. Primary references

All sources below are official RBI publications. Accessed 19 November 2026.

1. [RBI, Commercial Banks – Income Recognition, Asset Classification and Provisioning Directions, 2025 (updated 1 October 2026)](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13146) — scope/applicability, definitions of overdue and out-of-order status, NPA triggers, borrower-level classification, upgrades, write-offs, and the GNPA reporting framework.
2. [RBI, Commercial Banks – Resolution of Stressed Assets Directions, 2025 (updated 1 October 2026)](https://www.rbi.org.in/Scripts/BS_ViewMasDirections.aspx?id=13145) — definitions of default, restructuring and technical write-off; early identification, SMA and restructuring treatment.

Re-check the official directions and amendments before using this specification for a new reporting period. The rule version that applied to each historical observation/event date must be retained when constructing labels.
