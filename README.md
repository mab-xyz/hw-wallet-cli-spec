# hw-wallet-cli-spec

One command line for hardware-backed Ethereum signers, and a checker that fails when a tool drifts from it. Tools that follow it so far: `yketh` (YubiKey 5, OpenPGP applet) and `tkey-eth` (Tillitis TKey).

The spec is [`hw_wallet_cli_spec/cli-spec.json`](hw_wallet_cli_spec/cli-spec.json). A tool conforms when:

- `<command> --help` exits 0 and lists the command's required flags (a Go `flag` program must treat `flag.ErrHelp` as success);
- the sign commands print one JSON object with exactly the listed keys (`attest` and `verify` may add keys);
- the removed command names (`sign-msg`, `verify-attestation`) and flags (`--serial`, `--port`) are gone.

Extra flags and commands are allowed (`--path` and `--uss-file` on `tkey-eth`, `generate` and `touch` on `yketh`).

## Commands

| command | required flags | JSON keys |
|---|---|---|
| `address` | `--device --json` | `address pubkey` |
| `sign-digest` | `--device --digest HEX` | `address digest signature` |
| `sign-tx` | `--device --tx FILE\|-` | `address digest signature raw_transaction tx_hash` |
| `sign-personal` | `--device` and one of `--message --message-hex --message-file` | `address digest signature` |
| `sign-typed-data` | `--device --typed-data FILE\|-` | `address digest signature encoded` |
| `attest` | `--device --out` | `kind address` (+ tool-specific) |
| `verify` | `--cert` | `kind address` (+ tool-specific) |

- `--device` selects the device: a YubiKey serial number, or a TKey serial port.
- The `sign-*` commands always print JSON. On failure nothing goes to stdout, the message goes to stderr, and the exit code is 1.
- Formats (checked on golden samples): `address` and `tx_hash` as in Ethereum; `pubkey` is `0x` + X‖Y, 64 bytes, no `0x04` prefix; `digest` is `0x` + 32 bytes; `signature` is `0x` + r‖s‖v, 65 bytes, low s, **v = 27 or 28** (what `ecrecover` and OpenZeppelin expect, not go-ethereum's raw 0/1), also for `sign-tx`, whose `raw_transaction` carries the transaction's own v; `encoded` is `0x1901` ‖ domainSeparator ‖ hashStruct(message) as hex. Hex is lowercase.
- `kind` is `yubico-opgp` (Yubico PKI chain) or `tkey-self` (self-asserted certificate). The two proofs differ in strength, so a verifier must read `kind`.

## Check a CLI

```
uv venv && uv pip install -e '.[dev]'
hw-wallet-cli-check yketh                         # silent and exit 0 when it conforms
hw-wallet-cli-check ".bin/tkey-eth" --json        # gaps as a JSON list, exit 1
hw-wallet-cli-check yketh --golden tests/golden   # also check sample outputs, <command>.json
hw-wallet-cli-check x --print-spec                # print the spec
```

`--help` flags are read from the output of `<cli> <command> --help`; `--tx` (argparse) and `-tx` (Go `flag`) are the same flag.

## Tests

```
pytest      # the checker against fake CLIs: one conforming (both flag styles), one broken each way
```

## License

MIT
