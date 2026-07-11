# PrimeNet Lab Development Workflow

`C:\PrimeNet\Lab` is the development environment. It is intentionally separate from `C:\PrimeNet\Platform`, which remains the stable production codebase.

## Rules

1. Never test experimental builder changes directly in `C:\PrimeNet\Platform`.
2. Never write test outputs into `E:\PrimeNet\Repository\ranges`.
3. Lab tests should write to `C:\PrimeNet\Lab\outputs`.
4. Promote Lab code only after runtime analysis, expected-file verification, and regression testing pass.

## Current Lab Tasks

- LAB-001: Identify and rerun the longest-runtime batch.
- LAB-002: Improve verifier so legacy files are reported as extras, not treated as repository members.
- LAB-003: Separate per-run runtime logs from historical runtime logs.
- LAB-004: Create 10-batch regression test mode.
- LAB-005: Final v2 promotion test.
