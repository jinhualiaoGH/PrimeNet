from __future__ import annotations

from argparse import Namespace
from pathlib import Path

from builder.core.application import PaperBuilderApplication
from builder.core.configuration import PaperConfiguration
from builder.core.doctor import Doctor


def configuration_from_args(args: Namespace) -> PaperConfiguration:
    root = Path(args.project_root).resolve() if args.project_root else Path.cwd()
    if args.config:
        cfg = PaperConfiguration.from_json(Path(args.config), project_root=root)
    else:
        cfg = PaperConfiguration.defaults(root)

    return cfg.with_overrides(
        paper=args.paper,
        release=args.release,
        strict=not args.no_strict,
        verbose=args.verbose,
    )


def execute(args: Namespace) -> int:
    cfg = configuration_from_args(args)

    if args.command == "doctor":
        report = Doctor(cfg).run()
        print(report.render())
        return 0 if report.passed else 1

    app = PaperBuilderApplication(cfg)

    if args.list_papers:
        papers = app.list_papers()
        if not papers:
            print("No paper plugins found.")
            return 0
        for name, title in sorted(papers.items()):
            print(f"{name}: {title}")
        return 0

    if not cfg.paper:
        raise ValueError("--paper is required unless --list-papers or doctor is used")

    result = app.build()
    print(f"Build ID: {result.context.build_id}")
    print(f"Summary:  {result.summary_path}")
    return 0
