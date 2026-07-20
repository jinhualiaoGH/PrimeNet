from __future__ import annotations

import hashlib
import json
import logging
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Callable

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
            "validate": self._validate,
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
        summary_path.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        return BuildResult(context, tuple(results), summary_path)

    @staticmethod
    def create_context(
        configuration: PaperConfiguration,
        plugin: PaperPlugin,
    ) -> BuildContext:
        timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        identity = f"{plugin.manifest.name}:{plugin.manifest.version}:{timestamp}"
        digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()[:8]
        build_id = f"{timestamp}-{digest}"
        build_dir = configuration.output_root / plugin.manifest.name / build_id
        return BuildContext(configuration, plugin, build_id, build_dir)

    @staticmethod
    def _validate(context: BuildContext) -> StageResult:
        manifest = context.plugin.manifest
        missing = []
        for item in manifest.required_evidence:
            candidate = context.configuration.evidence_root / item
            if not candidate.exists():
                missing.append(item)

        if missing and context.configuration.strict:
            raise PipelineError(
                "Missing required evidence: " + ", ".join(missing)
            )

        detail = "all required evidence present"
        if missing:
            detail = "missing optional evidence: " + ", ".join(missing)
        return StageResult("validate", "passed", detail)

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
        marker = context.build_dir / "FOUNDATION_READY.txt"
        marker.write_text(
            "PrimeNet Paper Builder v4 foundation executed successfully.\n",
            encoding="utf-8",
        )
        return StageResult("summarize", "passed", str(marker))
