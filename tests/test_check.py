"""The checker, validated against fake CLIs: one conforming, several broken one way each."""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path
from typing import Any

import pytest

from hw_wallet_cli_spec import check, load_spec
from hw_wallet_cli_spec._check import check_golden, check_help

FAKE = '''\
import json, sys
table = json.load(open(sys.argv[1]))
cmd = sys.argv[2] if len(sys.argv) > 2 else ""
if cmd not in table or sys.argv[3:] != ["--help"]:
    print(f"unknown command {cmd}", file=sys.stderr); sys.exit(2)
style, flags = table[cmd]["style"], table[cmd]["flags"]
dash = "--" if style == "argparse" else "-"
print(f"usage: fake {cmd} (see sign-tx, verify-the-address, or - for stdin)")
for f in flags:
    print(f"  {dash}{f} VALUE   a flag")
'''


def conforming(spec: dict[str, Any], style: str = "argparse") -> dict[str, Any]:
    return {c: {"style": style, "flags": [f.lstrip("-") for f in e["flags"]]}
            for c, e in spec["commands"].items()}


def fake_cli(tmp_path: Path, table: dict[str, Any]) -> list[str]:
    (tmp_path / "fake.py").write_text(FAKE)
    (tmp_path / "table.json").write_text(json.dumps(table))
    return [sys.executable, str(tmp_path / "fake.py"), str(tmp_path / "table.json")]


@pytest.fixture
def spec() -> dict[str, Any]:
    return load_spec()


def test_known_positive_argparse_style(tmp_path: Path, spec: dict[str, Any]) -> None:
    assert check_help(fake_cli(tmp_path, conforming(spec)), spec) == []


def test_known_positive_go_single_dash_style(tmp_path: Path, spec: dict[str, Any]) -> None:
    assert check_help(fake_cli(tmp_path, conforming(spec, "go")), spec) == []


def test_missing_flag_is_reported(tmp_path: Path, spec: dict[str, Any]) -> None:
    table = conforming(spec)
    table["sign-tx"]["flags"].remove("tx")
    assert check_help(fake_cli(tmp_path, table), spec) == ["sign-tx: missing flag --tx"]


def test_missing_command_is_reported(tmp_path: Path, spec: dict[str, Any]) -> None:
    table = conforming(spec)
    del table["sign-digest"]
    gaps = check_help(fake_cli(tmp_path, table), spec)
    assert len(gaps) == 1 and gaps[0].startswith("sign-digest: `--help` exits 2, expected 0")


def test_removed_flag_is_reported(tmp_path: Path, spec: dict[str, Any]) -> None:
    table = conforming(spec)
    table["address"]["flags"].append("serial")
    assert check_help(fake_cli(tmp_path, table), spec) == ["address: removed flag --serial is still listed"]


def test_removed_command_is_reported(tmp_path: Path, spec: dict[str, Any]) -> None:
    table = conforming(spec)
    table["sign-msg"] = {"style": "argparse", "flags": ["message"]}
    assert check_help(fake_cli(tmp_path, table), spec) == ["sign-msg: removed command still exists"]


def test_hyphenated_words_in_help_text_are_not_flags(tmp_path: Path, spec: dict[str, Any]) -> None:
    """The fake's usage line contains "sign-tx" and "verify-the-address"; they must not become flags."""
    table = conforming(spec)
    table["address"]["flags"].remove("json")  # would be satisfied by a bogus "-tx"/"-the-address" match
    assert check_help(fake_cli(tmp_path, table), spec) == ["address: missing flag --json"]


def test_unreachable_cli_is_a_gap_not_a_crash(spec: dict[str, Any]) -> None:
    gaps = check_help(["/nonexistent/cli"], spec)
    assert len(gaps) == len(spec["commands"])
    assert all("exits 127" in g for g in gaps)


def write_golden(tmp_path: Path, spec: dict[str, Any], **override: Any) -> Path:
    for command, entry in spec["commands"].items():
        sample: Any = {k: "x" for k in entry["json_keys"]}
        if "kind" in sample:
            sample["kind"] = spec["kinds"][0]
        sample = override.get(command, sample)
        (tmp_path / f"{command}.json").write_text(json.dumps(sample))
    return tmp_path


def test_golden_known_positive(tmp_path: Path, spec: dict[str, Any]) -> None:
    assert check_golden(write_golden(tmp_path, spec), spec) == []


def test_golden_missing_and_extra_keys(tmp_path: Path, spec: dict[str, Any]) -> None:
    d = write_golden(tmp_path, spec, **{
        "sign-personal": {"address": "x", "digest": "x"},
        "sign-digest": {"address": "x", "digest": "x", "signature": "x", "v": 1},
    })
    gaps = check_golden(d, spec)
    assert "sign-personal: missing JSON key(s) ['signature']" in gaps
    assert "sign-digest: unexpected JSON key(s) ['v']" in gaps


def test_golden_extra_keys_allowed_where_spec_says_so(tmp_path: Path, spec: dict[str, Any]) -> None:
    d = write_golden(tmp_path, spec, attest={"kind": "tkey-self", "address": "x", "cert": "..."})
    assert check_golden(d, spec) == []


def test_golden_unknown_kind(tmp_path: Path, spec: dict[str, Any]) -> None:
    d = write_golden(tmp_path, spec, verify={"kind": "mystery", "address": "x"})
    assert any(g.startswith("verify: kind 'mystery'") for g in check_golden(d, spec))


def test_golden_not_json_and_not_object(tmp_path: Path, spec: dict[str, Any]) -> None:
    d = write_golden(tmp_path, spec)
    (d / "address.json").write_text("not json")
    (d / "sign-tx.json").write_text("[1]")
    gaps = check_golden(d, spec)
    assert any(g.startswith("address: address.json is not JSON") for g in gaps)
    assert "sign-tx: sign-tx.json is not a JSON object" in gaps


def test_golden_missing_file_is_skipped(tmp_path: Path, spec: dict[str, Any]) -> None:
    assert check_golden(tmp_path, spec) == []


def test_check_combines_help_and_golden(tmp_path: Path, spec: dict[str, Any]) -> None:
    cli = fake_cli(tmp_path, conforming(spec))
    golden = write_golden(tmp_path / "g", spec) if (tmp_path / "g").mkdir() is None else tmp_path
    assert check(cli, spec, golden) == []


def run_cli(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run([sys.executable, "-m", "hw_wallet_cli_spec.cli", *args],
                          capture_output=True, text=True, check=False)


def test_cli_is_silent_and_exits_0_when_conforming(tmp_path: Path, spec: dict[str, Any]) -> None:
    cli = fake_cli(tmp_path, conforming(spec))
    p = run_cli(" ".join(cli))
    assert (p.returncode, p.stdout, p.stderr) == (0, "", "")


def test_cli_lists_gaps_and_exits_1(tmp_path: Path, spec: dict[str, Any]) -> None:
    table = conforming(spec)
    table["sign-tx"]["flags"].remove("tx")
    p = run_cli(" ".join(fake_cli(tmp_path, table)), "--json")
    assert p.returncode == 1
    assert json.loads(p.stdout) == ["sign-tx: missing flag --tx"]


def test_cli_prints_spec() -> None:
    assert json.loads(run_cli("x", "--print-spec").stdout)["version"] == 1
