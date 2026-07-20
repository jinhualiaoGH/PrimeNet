import hashlib
import json
from pathlib import Path

from builder.evidence import EvidenceLoader, EvidenceRegistry, EvidenceValidator


def test_validator_checks_checksum(tmp_path: Path) -> None:
    package = tmp_path / "demo"
    package.mkdir()
    source = package / "value.json"
    source.write_text('{"value": 7}', encoding="utf-8")
    digest = hashlib.sha256(source.read_bytes()).hexdigest()
    (package / "package.json").write_text(
        json.dumps(
            {
                "package_id": "demo",
                "version": "1",
                "evidence": [
                    {
                        "id": "demo.value",
                        "kind": "metric",
                        "title": "Value",
                        "version": "1",
                        "source": {
                            "path": "value.json",
                            "media_type": "application/json",
                            "sha256": digest,
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    loader = EvidenceLoader(tmp_path)
    report = EvidenceValidator(loader).validate(EvidenceRegistry.from_packages(loader.discover()))
    assert report.passed
