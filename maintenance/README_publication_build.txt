PrimeNet automated publication build
====================================

Place the script here:

    C:\PrimeNet\maintenance\build_publication.ps1

Normal build and verification:

    cd C:\PrimeNet
    powershell -ExecutionPolicy Bypass -File .\maintenance\build_publication.ps1

First run, including dependency installation:

    powershell -ExecutionPolicy Bypass -File .\maintenance\build_publication.ps1 -InstallDependencies

Clean generated figures/tables and rebuild:

    powershell -ExecutionPolicy Bypass -File .\maintenance\build_publication.ps1 -Clean

Clean rebuild and install/update dependencies:

    powershell -ExecutionPolicy Bypass -File .\maintenance\build_publication.ps1 -Clean -InstallDependencies

Build without the separate verification pass:

    powershell -ExecutionPolicy Bypass -File .\maintenance\build_publication.ps1 -SkipVerification

The script assumes:

    C:\PrimeNet\paper\build_publication.py
    C:\PrimeNet\paper\verify_publication.py
    C:\PrimeNet\paper\requirements.txt

It generates or refreshes:

    C:\PrimeNet\paper\figures
    C:\PrimeNet\paper\tables
    C:\PrimeNet\paper\output

Build logs are written to:

    C:\PrimeNet\maintenance\logs
