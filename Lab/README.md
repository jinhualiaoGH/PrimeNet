# PrimeNet Lab Toolkit

Purpose: create a clean development environment at `C:\PrimeNet\Lab` so all experiments, fixes, regression tests, and runtime investigations stay separate from the stable `C:\PrimeNet\Platform` and the official repository at `E:\PrimeNet\Repository`.

Recommended workflow:

1. Keep `C:\PrimeNet\Platform` frozen as stable v1.
2. Run `scripts\00_create_lab_structure.ps1`.
3. Copy stable platform code into `C:\PrimeNet\Lab\Platform_v2_dev` using `scripts\01_copy_platform_to_lab.ps1`.
4. Run runtime analysis using `scripts\02_run_runtime_analysis.ps1`.
5. Run the improved manifest/config verifier using `scripts\03_run_expected_file_verifier.ps1`.
6. Use `scripts\04_make_regression_plan.ps1` to create a 10-batch plan.
7. Test fixes in Lab only.
8. Promote to Platform v2 only after all Lab tests pass.

This toolkit does not modify the official repository data unless you explicitly run promotion/copy scripts.
