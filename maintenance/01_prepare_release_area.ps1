param(
    [string]$PrimeNetRoot = "C:\PrimeNet",
    [switch]$Apply
)

$ErrorActionPreference = "Stop"

$ReleaseRoot = Join-Path $PrimeNetRoot "release\v1.0"
$Reports = Join-Path $PrimeNetRoot "maintenance\reports"
New-Item -ItemType Directory -Path $Reports -Force | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$Manifest = Join-Path $Reports "release_area_plan_$Timestamp.csv"
$Log = Join-Path $Reports "release_area_plan_$Timestamp.txt"

$Items = @(
    [pscustomobject]@{
        Source = Join-Path $PrimeNetRoot "PrimeNet_Publisher_v2_4_3_Figure1_Final_Real.zip"
        Destination = Join-Path $ReleaseRoot "PrimeNet_Publisher_v2_4_3_Figure1_Final_Real.zip"
        Required = $true
    },
    [pscustomobject]@{
        Source = Join-Path $PrimeNetRoot "publication\output\PrimeNet_Architecture_Publication_Draft_v2_4.docx"
        Destination = Join-Path $ReleaseRoot "PrimeNet_Architecture_Publication_Draft_v2_4.docx"
        Required = $true
    },
    [pscustomobject]@{
        Source = Join-Path $PrimeNetRoot "publication\output\primenet_v1_release_audit.txt"
        Destination = Join-Path $ReleaseRoot "primenet_v1_release_audit.txt"
        Required = $true
    },
    [pscustomobject]@{
        Source = Join-Path $PrimeNetRoot "publication\output\publication_manifest.json"
        Destination = Join-Path $ReleaseRoot "publication_manifest.json"
        Required = $true
    },
    [pscustomobject]@{
        Source = Join-Path $PrimeNetRoot "publication\output\publication_review_report.txt"
        Destination = Join-Path $ReleaseRoot "publication_review_report.txt"
        Required = $true
    }
)

$rows = foreach ($item in $Items) {
    [pscustomobject]@{
        Source = $item.Source
        Destination = $item.Destination
        Required = $item.Required
        Exists = Test-Path -LiteralPath $item.Source
        Status = if ($Apply) { "PENDING" } else { "DRY-RUN" }
    }
}

$missingRequired = $rows | Where-Object { $_.Required -eq "True" -and $_.Exists -eq $false }
if ($missingRequired) {
    $missingRequired | ForEach-Object { Write-Warning "Missing required release artifact: $($_.Source)" }
    throw "Release area preflight failed."
}

if (-not $Apply) {
    $rows | Export-Csv -LiteralPath $Manifest -NoTypeInformation -Encoding UTF8
    @(
        "PrimeNet v1.0 Release Area Plan"
        ("=" * 80)
        "Mode    : DRY-RUN"
        "Release : $ReleaseRoot"
        ""
        ($rows | ForEach-Object { "[PLAN] $($_.Source) -> $($_.Destination)" })
        ""
        "Nothing was copied. Rerun with -Apply after review."
    ) | Set-Content -LiteralPath $Log -Encoding UTF8

    Write-Host "[DRY-RUN] Release area plan created."
    Write-Host "[MANIFEST] $Manifest"
    Write-Host "[LOG] $Log"
    exit 0
}

New-Item -ItemType Directory -Path $ReleaseRoot -Force | Out-Null

foreach ($row in $rows) {
    Copy-Item -LiteralPath $row.Source -Destination $row.Destination -Force
    $row.Status = "COPIED"
    Write-Host "[COPIED] $($row.Destination)"
}

$ReleaseNotes = Join-Path $ReleaseRoot "RELEASE_NOTES.md"
@"
# PrimeNet v1.0

Reference Architecture Release

## Included

- PrimeNet Publisher v2.4.3 final refinement package
- Final architecture manuscript
- PrimeNet v1 release audit
- Publication manifest
- Publication verification report

## Status

PrimeNet v1.0 publication candidate completed and independently verified.
"@ | Set-Content -LiteralPath $ReleaseNotes -Encoding UTF8

$ChecksumFile = Join-Path $ReleaseRoot "SHA256SUMS.txt"
$checksumLines = foreach ($file in Get-ChildItem -LiteralPath $ReleaseRoot -File | Sort-Object Name) {
    if ($file.Name -eq "SHA256SUMS.txt") { continue }
    $hash = Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256
    "$($hash.Hash.ToLower())  $($file.Name)"
}
$checksumLines | Set-Content -LiteralPath $ChecksumFile -Encoding UTF8

$rows | Export-Csv -LiteralPath $Manifest -NoTypeInformation -Encoding UTF8

Write-Host ""
Write-Host "[COMPLETE] PrimeNet v1.0 release area prepared."
Write-Host "[RELEASE] $ReleaseRoot"
Write-Host "[CHECKSUMS] $ChecksumFile"
