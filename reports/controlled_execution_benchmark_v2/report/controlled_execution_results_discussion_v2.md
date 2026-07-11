# PrimeNet Controlled Execution Benchmark Results v2

## Campaign summary

The PrimeNet controlled production campaign completed 100 consecutive 10-billion-integer batches across the range 2,000,000,000,001 to 3,000,000,000,000. The batch-derived production runtime was 295.071 minutes (4.918 hours). The campaign produced 35,038,402,564 primes and 261.056 GB of NumPy range output.

All 100 batches completed output verification.

## Runtime baseline

The mean total runtime was 2.951 minutes per 10B batch, with median 2.895 minutes. The interquartile range was 0.300 minutes and the coefficient of variation was 0.086. The 5th to 95th percentile interval was 2.662 to 3.388 minutes, with observed minimum 2.635 and maximum 4.145 minutes.

These results support a platform-specific controlled-execution baseline of approximately three minutes per 10-billion-integer production batch.

## Runtime components

Generation was the dominant cost, averaging 2.315 minutes per batch. Saving averaged 0.603 minutes, while verification averaged 0.033 minutes. Thus, the benchmark indicates that the primary compute cost remains prime generation, with persistent output writing as the secondary cost.

## Stability and excursions

A linear trend fit to total runtime versus batch index gives a slope of 0.001818 minutes per batch, corresponding to a fitted campaign-scale change of 0.180 minutes. This should be interpreted as an engineering diagnostic rather than a mathematical law; the runtime sequence is dominated by stable baseline behavior with transient excursions.

Using the v2 IQR rule, 3 batches were flagged as runtime excursions. These excursions should be reviewed component-wise to distinguish generation, save, and verification effects. Importantly, the campaign returned to its baseline runtime regime after excursions, supporting the interpretation that there was no progressive degradation across the 1T run.

## Heartbeat evidence

The controlled execution heartbeat contained 1778 rows. The maximum heartbeat interval was 10.407 seconds, the mean interval was 10.016 seconds, and the campaign reported 0 heartbeat-gap warnings. This provides direct evidence that the campaign ran under continuous controlled execution rather than uncontrolled sleep/suspension conditions.

## Suggested paper statement

Under the integrated PrimeNet Controlled Execution Framework, the 2T to 3T production campaign completed 100 consecutive 10-billion-integer batches in 4.918 hours, producing 35,038,402,564 primes with verified outputs. The observed mean runtime was 2.951 minutes per 10B batch and the median was 2.895 minutes. The run preserved a continuous execution record with 1778 heartbeat samples, 0 heartbeat-gap warnings, and maximum heartbeat interval 10.407 seconds.

Earlier anomalous wall-clock measurements were associated with uncontrolled execution conditions and are therefore excluded from the controlled performance baseline. Under the integrated Controlled Execution Framework, the 2T–3T campaign exhibited sustained and measurable throughput with continuous heartbeat evidence and verified repository outputs.

> Observe the primes. Measure the computation. Validate the evidence. Trust the result.
