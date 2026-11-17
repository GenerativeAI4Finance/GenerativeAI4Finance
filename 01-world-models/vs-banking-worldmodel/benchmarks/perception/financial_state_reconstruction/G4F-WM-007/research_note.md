# Research Note: Interventions in a Synthetic Credit-State Simulator

## Question and scope

This exercise asks how outcomes change when one policy variable is changed in
a fictional financial environment while the same synthetic entity profile and
exogenous shock are held fixed. It demonstrates controlled counterfactual
simulation. It does not estimate how real borrowers would respond.

## Scenario design

The fixed-seed cohort contains 40 synthetic accounts. Baseline policies are
assigned from the generated risk index: higher risk receives a higher rate, a
shorter term, a lower credit limit, and earlier collections. For each entity,
the simulator generates one potential outcome under that baseline policy and
one under each isolated intervention: a 2 percentage-point rate reduction, a
12-month term extension, a 20% limit increase, or a 15-day collections delay.
Each outcome uses the same baseline features and uniform exogenous shock for
that entity across all arms.

The outcomes are modeled monthly payment, projected net cash flow, cumulative
12-month default probability, and a simulated binary default indicator.
Configuration values and equations are documented in
`config/causal_scenarios.json` and `data_dictionary.md`.

## Estimand

For each intervention arm and outcome, the reported contrast is the average
within-entity potential outcome under that arm minus the potential outcome
under the `observed_policy` control. Because every entity is evaluated under
each arm, it is a paired contrast in the simulator's defined counterfactual
world. It describes the simulator only.

## Confounding and identification limits

The synthetic observational policy is assigned using risk covariates that also
enter the outcome equation. Thus, a naive cross-sectional comparison of
entities with different assigned rates, terms, limits, or collections timing
would mix policy differences with baseline risk differences. The paired design
holds generated observed covariates and a shared shock fixed across arms to
isolate the changes specified in the equations. The data are not randomized
real-world treatment data and the generator does not provide empirical
identification.

The model includes only the listed covariates and a shared exogenous shock.
It omits unobserved borrower behavior, lender selection processes beyond the
configured risk-index assignment, macroeconomic dynamics, competing risks,
repeated payment histories, treatment adherence, and feedback from prior
outcomes. The model does not establish that the listed variables are sufficient
to remove confounding in any real setting.

## Counterfactual assumptions

Interpretation depends on all of the following simulator choices:

1. The configured risk index and risk-based policy assignment represent the
   synthetic observational process.
2. Each intervention changes exactly the configured policy dimension. The
   specified balance take-up after a limit increase is fixed at 10% of added
   capacity.
3. The annuity formula describes payment response to interest rates and terms.
4. Expense share, stress coefficients, collections-delay effect, and logistic
   hazard are correctly implemented as configured.
5. Monthly default hazard is treated as constant over the selected horizon for
   cumulative-probability conversion.
6. A single shared uniform shock supplies comparable binary potential outcomes
   across the arms for an entity.
7. No interference occurs between entities, and no policy adaptation occurs
   beyond the encoded rules.

Changing these assumptions can change both the sign and size of the modelled
contrasts. The results are not invariant causal effects.

## Reporting guidance

Use terms such as “simulator-implied paired difference” or “modeled
counterfactual contrast.” Avoid unqualified claims that an intervention causes
an outcome in real borrowers. Report the configuration version, seed, model
assumptions, and limitations with any result. The small synthetic cohort is a
software and research-method illustration, not a basis for policy, lending,
collections, or customer treatment decisions.
