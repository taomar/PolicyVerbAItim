#!/usr/bin/env python3
"""Verify an exact source-lock section without modifying the target tree."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for block in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--lock", type=Path, default=Path(__file__).with_name("SOURCE_LOCK.json"))
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--section", default="base_harness")
    args = parser.parse_args()

    lock = json.loads(args.lock.read_text(encoding="utf-8"))
    expected = lock.get(args.section)
    if not isinstance(expected, dict):
        raise RuntimeError(f"unknown or invalid lock section: {args.section}")
    mismatches = []
    verified = []
    for relative, expected_hash in sorted(expected.items()):
        path = args.root / Path(relative)
        if not path.is_file():
            mismatches.append({"path": relative, "error": "missing"})
            continue
        actual_hash = sha256_file(path)
        if actual_hash != expected_hash:
            mismatches.append(
                {
                    "path": relative,
                    "expected": expected_hash,
                    "actual": actual_hash,
                }
            )
        else:
            verified.append(relative)
    print(
        json.dumps(
            {
                "status": "passed" if not mismatches else "failed",
                "section": args.section,
                "verified": verified,
                "mismatches": mismatches,
                "files_modified": False,
            },
            indent=2,
        )
    )
    return 0 if not mismatches else 2


if __name__ == "__main__":
    raise SystemExit(main())
