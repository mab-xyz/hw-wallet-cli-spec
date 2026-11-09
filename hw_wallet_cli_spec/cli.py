"""hw-wallet-cli-check: fail when a signer CLI drifts from the common spec. Silent when it conforms."""

from __future__ import annotations

import argparse
import json
import shlex
import sys
from pathlib import Path

from ._check import check, load_spec


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="hw-wallet-cli-check", description=__doc__)
    p.add_argument("cli", help='the CLI to check, e.g. "yketh" or "uv run yketh" or ".bin/tkey-eth"')
    p.add_argument("--golden", type=Path, metavar="DIR",
                   help="directory of sample outputs, <command>.json, whose keys are checked too")
    p.add_argument("--json", action="store_true", help="print the gaps as a JSON list")
    p.add_argument("--print-spec", action="store_true", help="print the spec and exit")
    return p


def main(argv: list[str] | None = None) -> None:
    args = build_parser().parse_args(argv)
    spec = load_spec()
    if args.print_spec:
        print(json.dumps(spec, indent=2))
        return
    gaps = check(shlex.split(args.cli), spec, args.golden)
    if gaps:
        print(json.dumps(gaps, indent=2) if args.json else "\n".join(gaps))
        sys.exit(1)


if __name__ == "__main__":
    main()
