from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

from builder.evidence import EvidenceCatalog, EvidenceLoader, EvidenceRegistry, EvidenceValidator
from builder.tables import TableCatalog, TableRenderer, TableSpecLoader

from .configuration import PaperConfiguration
from .exceptions import PipelineError
from .plugin_loader import PaperPlugin
from .version import __version__

LOGGER = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class BuildContext:
    configuration: PaperConfiguration
    plugin: PaperPlugin
    build_id: str
    build_dir: Path


@dataclass(frozen=True, slots=True)
class StageResult:
    name: str
    status: str
    detail: str


@dataclass(frozen=True, slots=True)
class BuildResult:
    context: BuildContext
    stages: tuple[StageResult, ...]
    summary_path: Path


class BuildPipeline:
    def __init__(self) -> None:
        self._stages: dict[str, Callable[[BuildContext], StageResult]] = {
            "evidence": self._evidence,
            "validate": self._validate,
            "tables": self._tables,
            "plan": self._plan,
            "summarize": self._summarize,
        }

    def run(self, context: BuildContext) -> BuildResult:
        results: list[StageResult] = []
        context.build_dir.mkdir(parents=True, exist_ok=False)
        for stage_name in context.plugin.manifest.stages:
            stage = self._stages.get(stage_name)
            if stage is None:
                raise PipelineError(f"Unknown pipeline stage: {stage_name}")
            LOGGER.info("Running stage: %s", stage_name)
            results.append(stage(context))
        summary_path = context.build_dir / "build_summary.json"
        payload = {
            "builder_version": __version__,
            "build_id": context.build_id,
            "paper": context.plugin.manifest.to_dict(),
            "release": context.configuration.release,
            "stages": [asdict(result) for result in results],
        }
        summary_path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
        return BuildResult(context, tuple(results), summary_path)

    @staticmethod
    def create_context(configuration: PaperConfiguration, plugin: PaperPlugin) -> BuildContext:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        identity = f"{plugin.manifest.name}:{plugin.manifest.version}:{timestamp}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
        build_id = f"{timestamp}-{digest}"
        return BuildContext(configuration, plugin, build_id, configuration.output_root / plugin.manifest.name / build_id)

    @staticmethod
    def _load_evidence(context: BuildContext) -> tuple[EvidenceLoader, EvidenceRegistry]:
        loader = EvidenceLoader(context.configuration.evidence_root)
        return loader, EvidenceRegistry.from_packages(loader.discover())

    @classmethod
    def _evidence(cls, context: BuildContext) -> StageResult:
        loader, registry = cls._load_evidence(context)
        report = EvidenceValidator(loader).validate(registry)
        report_path = context.build_dir / "evidence_validation.txt"
        report_path.write_text(report.render() + "\n", encoding="utf-8")
        catalog_path = EvidenceCatalog(registry, loader).write(context.build_dir / "evidence_catalog.json")
        if not report.passed and context.configuration.strict:
            raise PipelineError(f"Evidence validation failed; see {report_path}")
        return StageResult(
            "evidence",
            "passed" if report.passed else "warning",
            f"{len(registry.records())} records; catalog={catalog_path}",
        )

    @classmethod
    def _validate(cls, context: BuildContext) -> StageResult:
        _, registry = cls._load_evidence(context)
        missing = [item for item in context.plugin.manifest.required_evidence if not registry.contains(item)]
        if missing and context.configuration.strict:
            raise PipelineError("Missing required evidence IDs: " + ", ".join(missing))
        detail = "all required evidence present"
        if missing:
            detail = "missing optional evidence IDs: " + ", ".join(missing)
        return StageResult("validate", "passed" if not missing else "warning", detail)


    @classmethod
    def _tables(cls, context: BuildContext) -> StageResult:
        loader, registry = cls._load_evidence(context)
        specs = TableSpecLoader(context.plugin.root).discover()
        renderer = TableRenderer(registry, loader)
        output_root = context.build_dir / "tables"
        rendered = tuple(renderer.render(spec, output_root) for spec in specs)
        catalog = TableCatalog.write(rendered, context.build_dir / "table_catalog.json")
        return StageResult("tables", "passed", f"{len(rendered)} tables; catalog={catalog}")

    @staticmethod
    def _plan(context: BuildContext) -> StageResult:
        manifest = context.plugin.manifest
        plan_path = context.build_dir / "build_plan.json"
        plan = {
            "paper": manifest.name,
            "title": manifest.title,
            "version": manifest.version,
            "release": context.configuration.release,
            "stages": list(manifest.stages),
            "required_evidence": list(manifest.required_evidence),
        }
        plan_path.write_text(json.dumps(plan, indent=2), encoding="utf-8")
        return StageResult("plan", "passed", str(plan_path))

    @staticmethod
    def _summarize(context: BuildContext) -> StageResult:
        marker = context.build_dir / "TABLE_ENGINE_READY.txt"
        message = "PrimeNet Paper Builder v4 Table Engine executed successfully.\n"
        marker.write_text(message, encoding="utf-8")
        # Preserve the alpha.2 foundation marker for backward compatibility.
        (context.build_dir / "FOUNDATION_READY.txt").write_text(message, encoding="utf-8")
        return StageResult("summarize", "passed", str(marker))
