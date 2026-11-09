"""Check a signer CLI against cli-spec.json: flags in `--help`, removed names, golden JSON keys."""

from __future__ import annotations

import json
import re
import subprocess
from importlib import resources
from pathlib import Path
from typing import Any

# `-x` or `--x-y`, not in the middle of a word ("sign-tx" must not yield "-tx").
FLAG_RE = re.compile(r"(?<![\w-])(--?[A-Za-z][\w-]*)")
TIMEOUT_S = 30


def load_spec() -> dict[str, Any]:
    spec = json.loads(resources.files("hw_wallet_cli_spec").joinpath("cli-spec.json").read_text())
    assert isinstance(spec, dict)
    return spec


def _name(flag: str) -> str:
    """`--tx` (argparse) and `-tx` (Go flag) are the same flag."""
    return flag.lstrip("-")


def run_help(cli: list[str], command: str) -> tuple[int, set[str]]:
    """Exit code of `cli command --help` and the flag names its output mentions."""
    try:
        p = subprocess.run([*cli, command, "--help"], capture_output=True, text=True,
                           timeout=TIMEOUT_S, check=False)
    except (OSError, subprocess.TimeoutExpired) as e:
        return 127, {str(e)}  # unreachable CLI: reported as a failed command
    text = p.stdout + p.stderr
    return p.returncode, {_name(f) for f in FLAG_RE.findall(text)}


def check_help(cli: list[str], spec: dict[str, Any]) -> list[str]:
    gaps: list[str] = []
    forbidden = {_name(f) for f in spec.get("removed_flags", [])}
    for command, entry in spec["commands"].items():
        rc, flags = run_help(cli, command)
        if rc != 0:
            gaps.append(f"{command}: `--help` exits {rc}, expected 0 (command missing, or --help is treated as an error)")
            continue
        gaps += [f"{command}: missing flag {f}" for f in entry["flags"] if _name(f) not in flags]
        gaps += [f"{command}: removed flag --{f} is still listed" for f in sorted(forbidden & flags)]
    for command in spec.get("removed_commands", []):
        rc, _ = run_help(cli, command)
        if rc == 0:
            gaps.append(f"{command}: removed command still exists")
    return gaps


def check_golden(directory: Path, spec: dict[str, Any]) -> list[str]:
    """Each `<command>.json` in `directory` is a sample output; its keys must match the spec."""
    gaps: list[str] = []
    for command, entry in spec["commands"].items():
        path = directory / f"{command}.json"
        if not path.exists():
            continue
        try:
            sample = json.loads(path.read_text())
        except ValueError as e:
            gaps.append(f"{command}: {path.name} is not JSON ({e})")
            continue
        if not isinstance(sample, dict):
            gaps.append(f"{command}: {path.name} is not a JSON object")
            continue
        want, got = set(entry["json_keys"]), set(sample)
        if want - got:
            gaps.append(f"{command}: missing JSON key(s) {sorted(want - got)}")
        if got - want and not entry.get("extra_keys", False):
            gaps.append(f"{command}: unexpected JSON key(s) {sorted(got - want)}")
        for key, pattern in spec.get("formats", {}).items():
            if key in sample and not (isinstance(sample[key], str) and re.fullmatch(pattern, sample[key])):
                gaps.append(f"{command}: {key} does not match the format {pattern}")
        kind = sample.get("kind")
        if "kind" in want and kind not in spec.get("kinds", []):
            gaps.append(f"{command}: kind {kind!r} is not one of {spec.get('kinds', [])}")
    return gaps


def check(cli: list[str], spec: dict[str, Any], golden: Path | None = None) -> list[str]:
    return check_help(cli, spec) + (check_golden(golden, spec) if golden else [])
