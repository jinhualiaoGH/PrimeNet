from __future__ import annotations

import sys

from builder.core.exceptions import PaperBuilderError

from .arguments import create_parser
from .commands import execute


def main(argv: list[str] | None = None) -> int:
    parser = create_parser()
    args = parser.parse_args(argv)
    try:
        return execute(args)
    except (PaperBuilderError, ValueError) as exc:
        parser.error(str(exc))
        return 2
    except KeyboardInterrupt:
        print("Build cancelled.", file=sys.stderr)
        return 130


if __name__ == "__main__":
    raise SystemExit(main())
