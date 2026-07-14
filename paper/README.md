# PrimeNet Publisher v2.3

PrimeNet Publisher v2.3 is the manuscript-integration release.

## Improvements from v2.1

- Builds an integrated Draft 2 manuscript instead of only an asset scaffold.
- Places canonical figures and tables inside relevant sections.
- Keeps a canonical asset appendix for review.
- Improves publication verification with section and manuscript checks.
- Preserves live repository integration and publication manifest generation.

## Test

```powershell
cd C:\PrimeNet\paper
py -m pip install -r requirements.txt
py build_publication.py
py verify_publication.py
```

Generated paper:

```text
output\PrimeNet_Architecture_Publication_Draft_v2_2.docx
```
