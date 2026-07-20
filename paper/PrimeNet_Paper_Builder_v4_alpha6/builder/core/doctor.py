from __future__ import annotations

import importlib.util
import os
import platform
import sys
from dataclasses import dataclass
from pathlib import Path

from .configuration import PaperConfiguration
from .plugin_loader import PluginLoader
from .version import __version__


@dataclass(frozen=True, slots=True)
class DiagnosticCheck:
    name: str
    status: str
    detail: str
    critical: bool = False


@dataclass(frozen=True, slots=True)
class DiagnosticReport:
    checks: tuple[DiagnosticCheck, ...]

    @property
    def passed(self) -> bool:
        return not any(
            check.critical and check.status == "FAIL" for check in self.checks
        )

    def render(self) -> str:
        lines = [
            "PrimeNet Paper Builder Doctor",
            "=" * 72,
        ]
        for check in self.checks:
            lines.append(f"[{check.status:<4}] {check.name:<24} {check.detail}")
        lines.extend(
            [
                "=" * 72,
                "RESULT: " + ("READY" if self.passed else "NOT READY"),
            ]
        )
        return "\n".join(lines)


class Doctor:
    """Run non-destructive installation and project diagnostics."""

    def __init__(self, configuration: PaperConfiguration) -> None:
        self.configuration = configuration

    def run(self) -> DiagnosticReport:
        checks: list[DiagnosticCheck] = []
        checks.append(self._python_check())
        checks.append(
            DiagnosticCheck(
                "Builder version",
                "PASS",
                __version__,
            )
        )
        checks.append(
            DiagnosticCheck(
                "Operating system",
                "PASS",
                f"{platform.system()} {platform.release()}",
            )
        )
        checks.append(self._directory_check("Project root", self.configuration.project_root, True))
        checks.append(self._directory_check("Papers root", self.configuration.papers_root, True))
        checks.append(self._directory_check("Evidence root", self.configuration.evidence_root, False))
        checks.extend(self._writable_runtime_checks())
        checks.append(self._plugin_check())
        checks.append(self._dependency_check("matplotlib", required=True))
        checks.append(self._dependency_check("pytest", required=False))
        return DiagnosticReport(tuple(checks))

    @staticmethod
    def _python_check() -> DiagnosticCheck:
        current = sys.version_info[:3]
        supported = current >= (3, 11, 0)
        return DiagnosticCheck(
            "Python",
            "PASS" if supported else "FAIL",
            f"{platform.python_version()} ({sys.executable})",
            critical=True,
        )

    @staticmethod
    def _directory_check(name: str, path: Path, required: bool) -> DiagnosticCheck:
        exists = path.is_dir()
        if exists:
            return DiagnosticCheck(name, "PASS", str(path), critical=required)
        return DiagnosticCheck(
            name,
            "FAIL" if required else "WARN",
            f"directory not found: {path}",
            critical=required,
        )

    def _writable_runtime_checks(self) -> list[DiagnosticCheck]:
        checks: list[DiagnosticCheck] = []
        for name, path in (
            ("Build root", self.configuration.output_root),
            ("Release root", self.configuration.release_root),
            ("Log root", self.configuration.log_root),
        ):
            checks.append(self._writable_directory_check(name, path))
        return checks

    @staticmethod
    def _writable_directory_check(name: str, path: Path) -> DiagnosticCheck:
        try:
            path.mkdir(parents=True, exist_ok=True)
            writable = os.access(path, os.W_OK)
        except OSError as exc:
            return DiagnosticCheck(name, "FAIL", f"cannot create: {exc}", critical=True)
        return DiagnosticCheck(
            name,
            "PASS" if writable else "FAIL",
            f"{path} ({'writable' if writable else 'not writable'})",
            critical=True,
        )

    def _plugin_check(self) -> DiagnosticCheck:
        try:
            plugins = PluginLoader(self.configuration.papers_root).discover()
        except Exception as exc:  # reported as a diagnostic rather than crashing
            return DiagnosticCheck(
                "Paper plugins",
                "FAIL",
                str(exc),
                critical=True,
            )
        if not plugins:
            return DiagnosticCheck(
                "Paper plugins",
                "FAIL",
                "none discovered",
                critical=True,
            )
        return DiagnosticCheck(
            "Paper plugins",
            "PASS",
            ", ".join(sorted(plugins)),
            critical=True,
        )

    @staticmethod
    def _dependency_check(module: str, *, required: bool) -> DiagnosticCheck:
        found = importlib.util.find_spec(module) is not None
        status = "PASS" if found else ("FAIL" if required else "WARN")
        detail = "installed" if found else "not installed (install .[dev] for tests)"
        return DiagnosticCheck(
            f"Dependency: {module}",
            status,
            detail,
            critical=required,
        )
