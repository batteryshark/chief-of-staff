#!/usr/bin/env python3
# /// script
# requires-python = ">=3.11"
# dependencies = []
# ///
"""Collect interface-audit evidence from a source tree.

Evidence collector, not a judge: every line is a fact with a file (and line
number where one exists). No verdicts. Each section header carries a one-line
caveat that names what the heuristic cannot see.

Sections:
  FORMS     input/select/textarea, required, and label counts per markup file
  TARGETS   literal px sizes below 24 on likely-interactive CSS selectors
  CLI FLAGS flags defined in source but absent from every help/doc surface
  STATE     storage-API call sites per file
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
MAX_BYTES = 5 * 1024 * 1024  # skip anything bigger; source files are smaller

SECTIONS = ("forms", "targets", "flags", "state")
TITLES = {"forms": "FORMS", "targets": "TARGETS", "flags": "CLI FLAGS", "state": "STATE"}
CAVEATS = {
    "forms": (
        "static tag count; cannot see runtime-generated fields, "
        "component-library inputs, or attributes set from code."
    ),
    "targets": (
        "literal px values below 24 (WCAG 2.5.8 floor) on selectors naming "
        "button/input/a/[role=]; cannot see computed styles, CSS-in-JS, "
        "relative units, or resolve SCSS nesting."
    ),
    "flags": (
        "static string match; 'in help/docs' means substring presence in a "
        "doc surface or a usage/help line, not proof the flag is explained."
    ),
    "state": (
        "counts storage-API call sites only; cannot tell what is stored or "
        "whether interface state is actually persisted."
    ),
}

# --- FORMS -----------------------------------------------------------------

FORM_EXTS = {".html", ".htm", ".jsx", ".tsx", ".vue", ".svelte"}
# [^>]* truncates at a '>' inside JSX expressions; the tag still counts once.
FIELD_RE = re.compile(r"<(?:input|select|textarea)\b([^>]*)>", re.I | re.S)
LABEL_RE = re.compile(r"<label\b", re.I)
# Lookbehind excludes aria-required and data-required; matches :required (Vue).
REQUIRED_RE = re.compile(r"(?<![\w-])required\b", re.I)


def forms_stats(text: str) -> tuple[int, int, int]:
    """Return (field count, fields carrying required, label count)."""
    fields = FIELD_RE.findall(text)
    required = sum(1 for attrs in fields if REQUIRED_RE.search(attrs))
    return len(fields), required, len(LABEL_RE.findall(text))


# --- TARGETS ----------------------------------------------------------------

STYLE_EXTS = {".css", ".scss"}
STYLE_HOST_EXTS = {".html", ".htm", ".vue", ".svelte"}
STYLE_BLOCK_RE = re.compile(r"<style\b[^>]*>(.*?)</style>", re.I | re.S)
# Flat brace pairing; nested SCSS/media blocks degrade, per the caveat.
RULE_RE = re.compile(r"([^{}]+)\{([^{}]*)\}")
# min-* before the bare names, plus a lookbehind, so min-width is not
# reported as width and max-width/border-width are not reported at all.
DECL_RE = re.compile(
    r"(?<![\w-])(min-width|min-height|width|height|font-size)"
    r"\s*:\s*(\d+(?:\.\d+)?)px",
    re.I,
)
INTERACTIVE_RE = re.compile(r"\bbutton\b|\binput\b|\[role=|(?:^|[\s,>+~(])a(?![\w-])")
CSS_COMMENT_RE = re.compile(r"/\*.*?\*/", re.S)
PX_FLOOR = 24.0


def blank_css_comments(css: str) -> str:
    """Replace /* */ comments with spaces, keeping newlines so lines hold."""
    return CSS_COMMENT_RE.sub(
        lambda m: re.sub(r"[^\n]", " ", m.group(0)), css
    )


def css_findings(css: str, line_base: int = 1) -> list[tuple[int, str, str, str]]:
    """Return (line, selector, prop, value) for sub-floor px declarations."""
    css = blank_css_comments(css)
    out: list[tuple[int, str, str, str]] = []
    for rule in RULE_RE.finditer(css):
        selector = " ".join(rule.group(1).split())
        if not INTERACTIVE_RE.search(selector):
            continue
        for decl in DECL_RE.finditer(rule.group(2)):
            if float(decl.group(2)) >= PX_FLOOR:
                continue
            pos = rule.start(2) + decl.start()
            line = line_base + css[:pos].count("\n")
            out.append((line, selector[:80], decl.group(1).lower(), decl.group(2)))
    return out


def style_chunks(rel: str, text: str) -> list[tuple[int, str]]:
    """Return (line_base, css_text) chunks for a file, or [] if not styled."""
    suffix = Path(rel).suffix.lower()
    if suffix in STYLE_EXTS:
        return [(1, text)]
    if suffix in STYLE_HOST_EXTS:
        return [
            (text[: m.start(1)].count("\n") + 1, m.group(1))
            for m in STYLE_BLOCK_RE.finditer(text)
        ]
    return []


# --- CLI FLAGS ---------------------------------------------------------------

JS_EXTS = {".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx"}
# [^)]* stops at the first ')'; flag strings come before help text, so the
# flags themselves survive the truncation.
PY_ADD_ARG_RE = re.compile(r"add_argument\(([^)]*)")
QUOTED_FLAG_RE = re.compile(r"""['"](-{1,2}[A-Za-z][\w-]*)['"]""")
JS_OPTION_RE = re.compile(r"""\.option\(\s*(['"])(.*?)\1""")
GO_FLAG_RE = re.compile(r"""flag\.\w+\(\s*(?:&[\w.\[\]]+\s*,\s*)?"([A-Za-z][\w-]*)\"""")
LONG_FLAG_RE = re.compile(r"(?<![\w-])--[a-z][a-z0-9-]+")
BARE_NAME_RE = re.compile(r"^[a-z][a-z0-9-]*$")
USAGE_LINE_RE = re.compile(r"usage|help", re.I)


def extract_flags(text: str, kind: str) -> list[tuple[int, str]]:
    """Return (line, flag) definitions. kind: py | js | go | generic."""

    def line_of(pos: int) -> int:
        return text[:pos].count("\n") + 1

    found: list[tuple[int, str]] = []
    if kind == "py":
        for m in PY_ADD_ARG_RE.finditer(text):
            for fm in QUOTED_FLAG_RE.finditer(m.group(1)):
                found.append((line_of(m.start()), fm.group(1)))
    elif kind == "js":
        for m in JS_OPTION_RE.finditer(text):
            spec = m.group(2)
            longs = LONG_FLAG_RE.findall(spec)
            if longs:
                found.extend((line_of(m.start()), flag) for flag in longs)
            elif BARE_NAME_RE.fullmatch(spec):  # yargs bare option name
                found.append((line_of(m.start()), "--" + spec))
    elif kind == "go":
        for m in GO_FLAG_RE.finditer(text):
            found.append((line_of(m.start()), "-" + m.group(1)))
    else:  # generic scan for files under bin/ and cmd/
        for m in LONG_FLAG_RE.finditer(text):
            found.append((line_of(m.start()), m.group(0)))
    return found


def flag_kinds(rel: str) -> list[str]:
    suffix = Path(rel).suffix.lower()
    kinds: list[str] = []
    if suffix == ".py":
        kinds.append("py")
    elif suffix in JS_EXTS:
        kinds.append("js")
    elif suffix == ".go":
        kinds.append("go")
    parents = Path(rel).parts[:-1]
    if "bin" in parents or "cmd" in parents:
        kinds.append("generic")
    return kinds


def is_doc_surface(rel: str) -> bool:
    path = Path(rel.lower())
    name = path.name
    return (
        "help" in name
        or name.startswith("readme")
        or name.endswith(".1")
        or "docs" in path.parts[:-1]
    )


def flag_documented(flag: str, source_text: str, doc_blob: str) -> bool:
    """True when the flag string appears in a doc surface, or on a usage/help
    line of its defining file (covers argparse help= on the same line)."""
    if flag in doc_blob:
        return True
    return any(
        flag in line and USAGE_LINE_RE.search(line)
        for line in source_text.splitlines()
    )


# --- STATE --------------------------------------------------------------------

STORAGE_RE = re.compile(
    r"\b(?:localStorage|sessionStorage|AsyncStorage|UserDefaults)\b"
)


def storage_count(text: str) -> int:
    return len(STORAGE_RE.findall(text))


# --- tree walk ------------------------------------------------------------------


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


def collect(root: Path) -> tuple[dict[str, str], list[str]]:
    """Map relative path -> text for every scannable text file.

    Whole tree held in memory; fine for source repos, revisit if it is not.
    """
    files: dict[str, str] = {}
    errors: list[str] = []
    for path in iter_files(root):
        try:
            if path.stat().st_size > MAX_BYTES:
                continue
            text = read_text(path)
        except OSError as exc:
            errors.append(f"{path}: {exc}")
            continue
        if text is not None:
            files[str(path.relative_to(root))] = text
    return files, errors


# --- section runners --------------------------------------------------------------


def run_forms(files: dict[str, str]) -> tuple[list[str], list[dict]]:
    rows, data = [], []
    for rel, text in sorted(files.items()):
        if Path(rel).suffix.lower() not in FORM_EXTS:
            continue
        inputs, required, labels = forms_stats(text)
        if inputs == 0:
            continue
        rows.append(f"{rel}: {inputs} inputs, {required} required, {labels} labels")
        data.append(
            {"file": rel, "inputs": inputs, "required": required, "labels": labels}
        )
    return rows, data


def run_targets(files: dict[str, str]) -> tuple[list[str], list[dict]]:
    rows, data = [], []
    for rel, text in sorted(files.items()):
        for line_base, css in style_chunks(rel, text):
            for line, selector, prop, value in css_findings(css, line_base):
                rows.append(f"{rel}:{line}: {selector} {{ {prop}: {value}px }}")
                data.append(
                    {
                        "file": rel,
                        "line": line,
                        "selector": selector,
                        "prop": prop,
                        "px": float(value),
                    }
                )
    return rows, data


def run_flags(files: dict[str, str]) -> tuple[list[str], list[dict], int]:
    defined: dict[str, tuple[str, int]] = {}
    for rel, text in sorted(files.items()):
        for kind in flag_kinds(rel):
            for line, flag in extract_flags(text, kind):
                defined.setdefault(flag, (rel, line))
    doc_blob = "\n".join(
        text for rel, text in sorted(files.items()) if is_doc_surface(rel)
    )
    undocumented_rows, data = [], []
    for flag, (rel, line) in sorted(defined.items()):
        if flag_documented(flag, files[rel], doc_blob):
            continue
        undocumented_rows.append(f"{flag} defined at {rel}:{line}, not found in help/docs")
        data.append({"flag": flag, "file": rel, "line": line})
    rows = [f"{len(defined)} flags defined in source"]
    rows.extend(
        undocumented_rows or ["(every defined flag appears in help/docs)"]
    )
    return rows, data, len(defined)


def run_state(files: dict[str, str]) -> tuple[list[str], list[dict]]:
    rows, data = [], []
    for rel, text in sorted(files.items()):
        count = storage_count(text)
        if count:
            rows.append(f"{rel}: {count} storage call sites")
            data.append({"file": rel, "call_sites": count})
    return rows, data


def build_report(
    files: dict[str, str], sections: list[str]
) -> tuple[list[str], dict[str, dict]]:
    plain: list[str] = []
    report: dict[str, dict] = {}
    for section in sections:
        if section == "forms":
            rows, data = run_forms(files)
            payload = {"caveat": CAVEATS[section], "files": data}
        elif section == "targets":
            rows, data = run_targets(files)
            payload = {"caveat": CAVEATS[section], "findings": data}
        elif section == "flags":
            rows, data, total = run_flags(files)
            payload = {"caveat": CAVEATS[section], "defined": total, "undocumented": data}
        else:
            rows, data = run_state(files)
            payload = {"caveat": CAVEATS[section], "files": data}
        report[section] = payload
        plain.append(f"== {TITLES[section]} ==")
        plain.append(f"caveat: {CAVEATS[section]}")
        plain.extend(rows or ["(none found)"])
        plain.append("")
    return plain, report


# --- self test -----------------------------------------------------------------------

FORMS_FIXTURE = """\
<form>
  <label for="email">Email</label>
  <input id="email" type="email" required>
  <label>Name <input name="n"></label>
  <select><option>a</option></select>
  <textarea aria-required="true"></textarea>
</form>
"""

CSS_FIXTURE = """\
.nav a { font-size: 12px; color: red }
button.icon {
  width: 20px;
  height: 20px;
}
input[type=checkbox] { min-width: 14px }
[role=tab] { height: 23.5px }
.card { width: 16px }
button.big { height: 44px }
"""

HTML_STYLE_FIXTURE = "<p>hi</p>\n<style>\nbutton { width: 10px }\n</style>\n"

PY_FLAGS_FIXTURE = (
    'parser.add_argument("--json", action="store_true", help="emit JSON")\n'
    'parser.add_argument("-q", "--quiet", action="store_true")\n'
)
JS_FLAGS_FIXTURE = (
    "program.option('-p, --port <n>', 'listen port')\n"
    "yargs.option('verbose', { describe: 'noisy' })\n"
)
GO_FLAGS_FIXTURE = (
    'port := flag.Int("port", 8080, "listen port")\n'
    'flag.StringVar(&cfg.name, "name", "", "user name")\n'
)
GENERIC_FLAGS_FIXTURE = 'exec mytool --dry-run "$@"\n'

STATE_FIXTURE = (
    'localStorage.setItem("a", 1); sessionStorage.getItem("b");\n'
    "let d = UserDefaults.standard\n"
)


def self_test() -> int:
    checks: list[tuple[str, bool]] = []

    fields, required, labels = forms_stats(FORMS_FIXTURE)
    checks.append(("forms: 4 fields", fields == 4))
    checks.append(("forms: 1 required (aria-required excluded)", required == 1))
    checks.append(("forms: 2 labels", labels == 2))
    checks.append(("forms: vue :required counts", REQUIRED_RE.search(':required="x"') is not None))

    findings = css_findings(CSS_FIXTURE)
    checks.append(("targets: 5 findings", len(findings) == 5))
    checks.append(("targets: font-size on line 1", findings[0] == (1, ".nav a", "font-size", "12")))
    checks.append(("targets: width on line 3", findings[1] == (3, "button.icon", "width", "20")))
    checks.append(("targets: height on line 4", findings[2] == (4, "button.icon", "height", "20")))
    checks.append(("targets: min-width kept distinct from width", findings[3][2] == "min-width"))
    checks.append(("targets: [role=] selector matched", findings[4][1] == "[role=tab]"))
    checks.append((
        "targets: non-interactive and >=24px excluded",
        all(f[1] not in (".card", "button.big") for f in findings),
    ))
    chunks = style_chunks("page.html", HTML_STYLE_FIXTURE)
    checks.append(("targets: style block line offset", css_findings(*reversed(chunks[0]))[0][0] == 3))
    commented = "/* note */\nbutton { width: 9px }\n"
    checks.append((
        "targets: comment kept out of selector, lines hold",
        css_findings(commented) == [(2, "button", "width", "9")],
    ))

    checks.append((
        "flags: argparse extraction",
        extract_flags(PY_FLAGS_FIXTURE, "py")
        == [(1, "--json"), (2, "-q"), (2, "--quiet")],
    ))
    checks.append((
        "flags: commander and yargs extraction",
        extract_flags(JS_FLAGS_FIXTURE, "js") == [(1, "--port"), (2, "--verbose")],
    ))
    checks.append((
        "flags: go extraction",
        extract_flags(GO_FLAGS_FIXTURE, "go") == [(1, "-port"), (2, "-name")],
    ))
    checks.append((
        "flags: generic extraction",
        extract_flags(GENERIC_FLAGS_FIXTURE, "generic") == [(1, "--dry-run")],
    ))
    checks.append((
        "flags: help= on defining line documents",
        flag_documented("--json", PY_FLAGS_FIXTURE, ""),
    ))
    checks.append((
        "flags: bare flag stays undocumented",
        not flag_documented("--quiet", PY_FLAGS_FIXTURE, ""),
    ))
    checks.append((
        "flags: doc surface blob documents",
        flag_documented("--quiet", PY_FLAGS_FIXTURE, "Use --quiet to silence."),
    ))
    checks.append((
        "flags: doc surface names",
        [is_doc_surface(p) for p in ("README.md", "docs/guide.md", "man/tool.1", "cli_help.txt", "src/app.py")]
        == [True, True, True, True, False],
    ))
    checks.append((
        "flags: kinds by path",
        flag_kinds("bin/tool.py") == ["py", "generic"] and flag_kinds("src/a.go") == ["go"],
    ))

    checks.append(("state: 3 call sites", storage_count(STATE_FIXTURE) == 3))
    checks.append(("state: no false positive", storage_count("const storage = 1\n") == 0))

    failed = 0
    for name, ok in checks:
        print(f"{'PASS' if ok else 'FAIL'}: {name}")
        failed += not ok
    print(f"{len(checks) - failed}/{len(checks)} checks passed")
    return 1 if failed else 0


def main() -> int:
    parser = argparse.ArgumentParser(
        prog="norman-audit",
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument("root", nargs="?", default=".", help="tree to audit (default: .)")
    parser.add_argument("--json", action="store_true", help="emit machine-readable JSON")
    parser.add_argument("--section", choices=SECTIONS, help="run one section only")
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

    files, errors = collect(root)
    sections = [args.section] if args.section else list(SECTIONS)
    plain, report = build_report(files, sections)
    if args.json:
        print(json.dumps(report, indent=2))
    else:
        print("\n".join(plain).rstrip())
    for error in errors:
        print(f"warning: {error}", file=sys.stderr)
    return 2 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())
