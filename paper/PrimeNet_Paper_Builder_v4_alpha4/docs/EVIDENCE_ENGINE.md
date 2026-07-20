# Evidence Engine v1

The Evidence Engine separates scientific evidence from figures, tables, prose, and publication rendering.

Each package lives under `evidence/<package>/package.json`. Every evidence record has a stable ID, kind, version, package-relative source, media type, optional SHA-256 digest, dependencies, and metadata.

Pipeline behavior:

1. discover evidence packages;
2. register globally unique evidence IDs;
3. validate source existence, checksums, dependencies, and readability;
4. emit `evidence_catalog.json` and `evidence_validation.txt`;
5. verify the paper plugin's `required_evidence` IDs.
