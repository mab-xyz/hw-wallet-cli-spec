"""Common CLI spec for hardware-backed Ethereum signers, and the checker that enforces it."""

from __future__ import annotations

from ._check import check, load_spec

__all__ = ["check", "load_spec"]
