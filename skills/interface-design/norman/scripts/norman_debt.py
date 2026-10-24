#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Report `norman:` interface-debt markers in a source tree.

A marker is a comment of the form `norman: <ceiling>[, <upgrade trigger>]`.
Recognized comment prefixes: #, //, <!--, {/*, /*, -- (SQL/Lua), ; (Lisp/INI).

This tool is a report, not a gate: exit is 0 whenever the scan completes.
Exceptions: bad arguments or I/O errors exit 2, and --fail-on-no-trigger
exits 1 when markers without an upgrade trigger exist (for CI use).
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path

SKIP_DIRS = {
    "node_modules", ".git", "dist", "build", "out", "vendor",
    "target", "__pycache__", ".venv", "coverage",
}

# Longest prefixes first so `<!--` wins over `--` and `{/*` wins over `/*`.
MARKER_RE = re.compile(r"(?:<!--|\{/\*|/\*|//|--|#|;)\s*norman:\s*(?P<body>.+)")
# Comment closers stripped from the marker body; `*/}` before `*/`.
CLOSERS = ("*/}", "*/", "-->")


def parse_body(body: str) -> tuple[str, str]:
    """Split a marker body into (ceiling, trigger). trigger is '' when absent."""
    body = body.strip()
    for closer in CLOSERS:
        if body.endswith(closer):
            body = body[: -len(closer)].rstrip()
            break
    ceiling, _, trigger = body.partition(",")
    return ceiling.strip().rstrip("."), trigger.strip().rstrip(".")


def scan_text(text: str) -> list[tuple[int, str, str]]:
    """Return (line, ceiling, trigger) for each marker in text.

    Line-based heuristic: the marker must directly follow a comment prefix.
    Markers inside string literals are indistinguishable from comments here.
    """
    found: list[tuple[int, str, str]] = []
    for lineno, line in enumerate(text.splitlines(), 1):
        match = MARKER_RE.search(line)
        if match:
            ceiling, trigger = parse_body(match.group("body"))
            if ceiling:
                found.append((lineno, ceiling, trigger))
    return found


def iter_files(root: Path):
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = sorted(d for d in dirnames if d not in SKIP_DIRS)
        for name in sorted(filenames):
            yield Path(dirpath) / name


def read_text(path: Path) -> str | None:
    """Return file text, or None for binary files (NUL byte in first 8 KiB)."""
    data = path.read_bytes()
    if b"\x00" in data[:8192]:
        return None
    return data.decode("utf-8", errors="replace")


def scan_tree(root: Path) -> tuple[list[dict], list[str]]:
    markers: list[dict] = []
    errors: list[str] = []
    for path in iter_files(root):
        try:
            text = read_text(path)
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue
        if text is None:
            continue
        rel = str(path.relative_to(root))
        for lineno, ceiling, trigger in scan_text(text):
            markers.append(
                {"file": rel, "line": lineno, "ceiling": ceiling, "trigger": trigger}
            )
    markers.sort(key=lambda m: (m["file"], m["line"]))
    return markers, errors


def render_plain(markers: list[dict]) -> str:
    if not markers:
        return "No norman: debt. Every door is marked."
    lines = []
    for marker in markers:
        row = f"{marker['file']}:{marker['line']}, {marker['ceiling']}."
        if marker["trigger"]:
            row += f" upgrade: {marker['trigger']}."
        else:
            row += " [no-trigger]"
        lines.append(row)
    no_trigger = sum(1 for m in markers if not m["trigger"])
    lines.append(f"{len(markers)} markers, {no_trigger} with no trigger.")
    return "\n".join(lines)


def render_json(markers: list[dict]) -> str:
    summary = {
        "total": len(markers),
        "no_trigger": sum(1 for m in markers if not m["trigger"]),
    }
    return json.dumps({"markers": markers, "summary": summary}, indent=2)


FIXTURE = """\
x = 1  # norman: three-flag ceiling, upgrade when a fourth flag lands
// norman: single undo level, add history stack when users ask
<!-- norman: static nav -->
{/* norman: prop drilling, lift to context at 3 levels */}
/* norman: fixed 320px sidebar, make resizable when content overflows */
-- norman: no index on email, add when table passes 100k rows
; norman: hardcoded palette
plain line, no marker
# not a norman marker: nope
"""


def self_test() -> int:
    markers = scan_text(FIXTURE)
    checks = [
        ("marker count is 7", len(markers) == 7),
        ("hash ceiling", markers[0][1] == "three-flag ceiling"),
        ("hash trigger", markers[0][2] == "upgrade when a fourth flag lands"),
        ("slash-slash marker on line 2", markers[1][0] == 2),
        ("html closer stripped", markers[2][1] == "static nav"),
        ("html marker has no trigger", markers[2][2] == ""),
        ("jsx closer stripped", markers[3][2] == "lift to context at 3 levels"),
        ("c-style ceiling", markers[4][1] == "fixed 320px sidebar"),
        ("sql-style ceiling", markers[5][1] == "no index on email"),
        ("semicolon marker no trigger", markers[6][2] == ""),
        ("no-trigger count is 2", sum(1 for m in markers if not m[2]) == 2),
        ("prose mention not matched", all("nope" != m[1] for m in markers)),
        ("empty text yields no markers", scan_text("just code\n") == []),
        (
            "zero-marker message",
            render_plain([]) == "No norman: debt. Every door is marked.",
        ),
        (
            "plain row format",
            render_plain(
                [{"file": "a.py", "line": 3, "ceiling": "x", "trigger": "y"}]
            ).splitlines()[0]
            == "a.py:3, x. upgrade: y.",
        ),
        (
            "no-trigger row flag",
            "[no-trigger]"
            in render_plain(
                [{"file": "a.py", "line": 3, "ceiling": "x", "trigger": ""}]
            ).splitlines()[0],
        ),
    ]
    failed = 0
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}: {name}")
        failed += not ok
    print(f"{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="norman",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("root", nargs="?", default=".", help="tree to scan (default: .)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument(
        "--fail-on-no-trigger",
        action="store_true",
        help="exit 1 when markers without an upgrade trigger exist (CI gate)",
    )
    parser.add_argument(
        "--self-test",
        action="store_true",
        help="run embedded fixture checks and exit",
    )
    args = parser.parse_args()
    if args.self_test:
        return self_test()

    root = Path(args.root).expanduser()
    if not root.is_dir():
        print(f"error: not a directory: {root}", file=sys.stderr)
        return 2

    markers, errors = scan_tree(root)
    print(render_json(markers) if args.json else render_plain(markers))
    for error in errors:
        print(f"warning: {error}", file=sys.stderr)
    if errors:
        return 2
    if args.fail_on_no_trigger and any(not m["trigger"] for m in markers):
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
