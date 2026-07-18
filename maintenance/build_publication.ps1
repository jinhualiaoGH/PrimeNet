[CmdletBinding()]
param(
    [string]$PrimeNetRoot = "C:\PrimeNet",
    [switch]$InstallDependencies,
    [switch]$Clean,
    [switch]$SkipVerification
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$PaperRoot = Join-Path $PrimeNetRoot "publication"
$BuildScript = Join-Path $PaperRoot "build_publication.py"
$VerifyScript = Join-Path $PaperRoot "verify_publication.py"
$Requirements = Join-Path $PaperRoot "requirements.txt"
$MaintenanceRoot = Join-Path $PrimeNetRoot "maintenance"
$LogRoot = Join-Path $MaintenanceRoot "logs"
$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$LogPath = Join-Path $LogRoot "publication_build_$Timestamp.log"

function Write-Step {
    param([string]$Message)
    Write-Host ""
    Write-Host ("=" * 78)
    Write-Host $Message
    Write-Host ("=" * 78)
}

function Resolve-PythonCommand {
    if (Get-Command py -ErrorAction SilentlyContinue) {
        return @("py")
    }
    if (Get-Command python -ErrorAction SilentlyContinue) {
        return @("python")
    }
    throw "Python was not found. Install Python or make 'py'/'python' available in PATH."
}

function Invoke-LoggedCommand {
    param(
        [Parameter(Mandatory)]
        [string]$WorkingDirectory,

        [Parameter(Mandatory)]
        [string[]]$Command,

        [Parameter(Mandatory)]
        [string]$LogPath
    )

    $Executable = $Command[0]
    $Arguments = @()

    if ($Command.Count -gt 1) {
        $Arguments = $Command[1..($Command.Count - 1)]
    }

    Push-Location $WorkingDirectory

    try {
        Write-Host ""
        Write-Host "Executing: $Executable $($Arguments -join ' ')"

        $PreviousErrorActionPreference = $ErrorActionPreference
        $ErrorActionPreference = "Continue"

        try {
            & $Executable @Arguments 2>&1 |
                Tee-Object -FilePath $LogPath -Append

            $ExitCode = $LASTEXITCODE
        }
        finally {
            $ErrorActionPreference = $PreviousErrorActionPreference
        }

        if ($ExitCode -ne 0) {
            throw "Command failed with exit code ${ExitCode}: $Executable $($Arguments -join ' ')"
        }
    }
    finally {
        Pop-Location
    }
}

if (-not (Test-Path $PaperRoot -PathType Container)) {
    throw "PrimeNet paper directory was not found: $PaperRoot"
}
if (-not (Test-Path $BuildScript -PathType Leaf)) {
    throw "Publication build script was not found: $BuildScript"
}
if (-not $SkipVerification -and -not (Test-Path $VerifyScript -PathType Leaf)) {
    throw "Publication verification script was not found: $VerifyScript"
}

New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null
$Python = Resolve-PythonCommand

"PrimeNet publication maintenance build" | Set-Content -Path $LogPath -Encoding UTF8
"Started: $(Get-Date -Format o)" | Add-Content -Path $LogPath
"PrimeNet root: $PrimeNetRoot" | Add-Content -Path $LogPath
"Paper root: $PaperRoot" | Add-Content -Path $LogPath
"Python command: $($Python -join ' ')" | Add-Content -Path $LogPath

$LogRoot = Join-Path $PrimeNetRoot "maintenance\logs"
New-Item -ItemType Directory -Path $LogRoot -Force | Out-Null

$Timestamp = Get-Date -Format "yyyyMMdd_HHmmss"
$BuildLogPath = Join-Path $LogRoot "publication_build_$Timestamp.log"

Write-Step "PrimeNet Publication Build"
Write-Host "PrimeNet root : $PrimeNetRoot"
Write-Host "Paper root    : $PaperRoot"
Write-Host "Build log     : $BuildLogPath"

if ($InstallDependencies) {
    if (-not (Test-Path $Requirements -PathType Leaf)) {
        throw "Requirements file was not found: $Requirements"
    }

    Write-Step "Installing publication dependencies"
    Invoke-LoggedCommand -WorkingDirectory $PaperRoot -Command @(
        $Python[0], "-m", "pip", "install", "-r", $Requirements
    )
}

if ($Clean) {
    Write-Step "Cleaning generated publication assets"

    $GeneratedPatterns = @(
        "figures\fig*.png",
        "figures\fig*.svg",
        "tables\table*.csv",
        "tables\table*.md",
        "tables\table*.docx",
        "output\publication_manifest.json",
        "output\publication_review_report.txt"
    )

    foreach ($Pattern in $GeneratedPatterns) {
        Get-ChildItem -Path (Join-Path $PaperRoot $Pattern) -File -ErrorAction SilentlyContinue |
            Remove-Item -Force
    }

    Write-Host "Generated figures, tables, manifest, and review report were removed."
    Write-Host "Existing manuscript drafts in paper\output were preserved."
}

Write-Step "Generating figures, tables, manuscript, review report, and manifest"
Invoke-LoggedCommand `
    -WorkingDirectory $PaperRoot `
    -Command @(
        $Python
        $BuildScript
    ) `
    -LogPath $BuildLogPath

if (-not $SkipVerification) {
    Write-Step "Verifying publication outputs"
    Invoke-LoggedCommand `
    -WorkingDirectory $PaperRoot `
    -Command @(
        $Python
        $VerifyScript
    ) `
    -LogPath $BuildLogPath
}

$ManifestPath = Join-Path $PaperRoot "output\publication_manifest.json"
if (-not (Test-Path $ManifestPath -PathType Leaf)) {
    throw "Build completed, but the publication manifest was not created: $ManifestPath"
}

Write-Step "Publication build completed successfully"
Write-Host "Figures : $(Join-Path $PaperRoot 'figures')"
Write-Host "Tables  : $(Join-Path $PaperRoot 'tables')"
Write-Host "Output  : $(Join-Path $PaperRoot 'output')"
Write-Host "Manifest: $ManifestPath"
Write-Host "Log     : $LogPath"
