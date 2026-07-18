# PrimeNet v1.0 Release-Aware Cleanup

This final maintenance update preserves the certified Publisher v2.4.3 installer
as a release artifact.

## Release area

The script creates:

```text
C:\PrimeNet\release\v1.0
```

and copies:

- PrimeNet_Publisher_v2_4_3_Figure1_Final_Real.zip
- PrimeNet_Architecture_Publication_Draft_v2_4.docx
- primenet_v1_release_audit.txt
- publication_manifest.json
- publication_review_report.txt
- RELEASE_NOTES.md
- SHA256SUMS.txt

## Archive exclusions

The certified v2.4.3 installer ZIP is explicitly excluded from development-package
archiving.

## Recommended workflow

Install the updated tools:

```powershell
cd C:\PrimeNet\PrimeNet_v1_0_Maintenance_Cleanup_ReleaseAware

powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\install_release_aware_cleanup.ps1
```

Run both final dry-runs:

```powershell
cd C:\PrimeNet\maintenance

powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\01_prepare_release_area.ps1

powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\02_archive_release_artifacts.ps1
```

After reviewing the reports, apply the complete workflow:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass `
    -File .\03_apply_cleanup_release_aware.ps1
```

The final step verifies required project directories and release components before
returning success.
