from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Mapping

from builder.core.exceptions import PipelineError
from builder.evidence import EvidenceLoader, EvidenceRegistry

from .models import FigureSpec, RenderedFigure


class FigureRenderer:
    def __init__(self, registry: EvidenceRegistry, loader: EvidenceLoader) -> None:
        self.registry = registry
        self.loader = loader

    def render(self, spec: FigureSpec, output_root: Path) -> RenderedFigure:
        try:
            import matplotlib

            matplotlib.use("Agg")
            import matplotlib.pyplot as plt
        except ImportError as exc:
            raise PipelineError("Figure Engine requires matplotlib. Install the project dependencies.") from exc

        registered = self.registry.get(spec.evidence_id)
        payload = self.loader.load_payload(registered.package, registered.record)
        if not isinstance(payload, Mapping):
            raise PipelineError("Figure evidence must be a JSON object.")

        labels: list[str] = []
        values: list[float] = []
        for item in spec.series:
            if item.key not in payload:
                raise PipelineError(
                    f"Figure {spec.figure_id!r} evidence {spec.evidence_id!r} is missing key {item.key!r}."
                )
            try:
                value = float(payload[item.key])
            except (TypeError, ValueError) as exc:
                raise PipelineError(
                    f"Figure {spec.figure_id!r} key {item.key!r} must contain a numeric value."
                ) from exc
            if spec.value_scale == "log" and value <= 0:
                raise PipelineError(f"Figure {spec.figure_id!r} log-scale values must be positive.")
            labels.append(item.label)
            values.append(value)

        output_root.mkdir(parents=True, exist_ok=True)
        png_path = output_root / f"{spec.figure_id}.png"
        svg_path = output_root / f"{spec.figure_id}.svg"
        metadata_path = output_root / f"{spec.figure_id}.json"

        figure, axes = plt.subplots(figsize=(spec.width, spec.height), constrained_layout=True)
        positions = list(range(len(values)))
        if spec.kind == "bar":
            if spec.orientation == "horizontal":
                axes.barh(positions, values)
                axes.set_yticks(positions, labels=labels)
                axes.set_xscale(spec.value_scale)
                axes.set_xlabel(spec.x_label or spec.y_label)
                axes.set_ylabel(spec.y_label if spec.x_label else "")
            else:
                axes.bar(positions, values)
                axes.set_xticks(positions, labels=labels)
                axes.set_yscale(spec.value_scale)
                axes.set_xlabel(spec.x_label)
                axes.set_ylabel(spec.y_label)
        else:
            axes.plot(positions, values, marker="o")
            axes.set_xticks(positions, labels=labels)
            axes.set_yscale(spec.value_scale)
            axes.set_xlabel(spec.x_label)
            axes.set_ylabel(spec.y_label)

        axes.set_title(spec.title)
        axes.grid(True, axis="x" if spec.orientation == "horizontal" else "y", alpha=0.25)
        figure.savefig(png_path, dpi=spec.dpi)
        figure.savefig(svg_path)
        plt.close(figure)

        metadata = {
            "id": spec.figure_id,
            "title": spec.title,
            "caption": spec.caption,
            "evidence_id": spec.evidence_id,
            "kind": spec.kind,
            "orientation": spec.orientation,
            "value_scale": spec.value_scale,
            "labels": labels,
            "values": values,
            "outputs": {"png": png_path.name, "svg": svg_path.name},
        }
        metadata_path.write_text(json.dumps(metadata, indent=2), encoding="utf-8")
        return RenderedFigure(spec.figure_id, png_path, svg_path, metadata_path, len(values))
