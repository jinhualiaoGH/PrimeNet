# First Run Steps

1. Unzip this package.
2. Open PowerShell.
3. Run:

```powershell
cd <unzipped folder>
.\scripts\install_toolkit_to_lab.ps1
```

4. Copy Platform v1 into Lab:

```powershell
.\scripts\01_copy_platform_to_lab.ps1
```

5. Analyze runtime:

```powershell
.\scripts\02_run_runtime_analysis.ps1
```

6. Run expected-file verifier:

```powershell
.\scripts\03_run_expected_file_verifier.ps1
```

7. Create regression plan:

```powershell
.\scripts\04_make_regression_plan.ps1
```
