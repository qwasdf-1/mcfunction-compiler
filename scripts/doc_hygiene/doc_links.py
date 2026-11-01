"""Documentation reference and link validation helpers."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Sequence

MD_LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")
BACKTICK_PATH = re.compile(
    r"`((?:(?:src|scripts|benchmarks|docs|tests)/|"
    r"(?:README|CHANGELOG|CONTRIBUTING)\.md)[^`\s]*)`"
)


def rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def active_doc_files(
    repo: Path,
    docs: Path,
    root_docs: Sequence[str],
    excluded_dirs: set[str],
) -> list[Path]:
    files = [repo / name for name in root_docs if (repo / name).exists()]
    for path in docs.rglob("*.md"):
        rel_parts = path.relative_to(docs).parts
        if rel_parts and rel_parts[0] in excluded_dirs:
            continue
        files.append(path)
    return sorted(files, key=lambda path: rel(repo, path))


def extract_path_refs(path: Path) -> list[tuple[int, str]]:
    refs: list[tuple[int, str]] = []
    text = path.read_text(encoding="utf-8", errors="ignore")
    for line_no, line in enumerate(text.splitlines(), start=1):
        refs.extend((line_no, match.group(1)) for match in MD_LINK.finditer(line))
        refs.extend((line_no, match.group(1)) for match in BACKTICK_PATH.finditer(line))
    return refs


def split_ref_fragment(target: str) -> tuple[str, str | None]:
    raw = target.strip("<>").strip()
    if "#" in raw:
        base, fragment = raw.split("#", 1)
        return base, fragment or None
    if ":" in raw:
        parts = raw.split(":", 1)
        if re.search(r"\.[a-zA-Z0-9]+$", parts[0]):
            return parts[0], parts[1]
    return raw, None


def is_placeholder(target: str) -> bool:
    return "<" in target or ">" in target or "*" in target


def is_forbidden_absolute_path(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith("file://")
        or lowered.startswith("file:/")
        or "/home/" in lowered
        or lowered.startswith("/home")
        or "c:/" in lowered
        or "c:\\" in lowered
    )


def is_external_link(target: str) -> bool:
    lowered = target.lower()
    return (
        lowered.startswith("http://")
        or lowered.startswith("https://")
        or lowered.startswith("mailto:")
    )


def documentation_path_check(
    repo: Path,
    docs: Path,
    root_docs: Sequence[str],
    excluded_dirs: set[str],
) -> tuple[int, list[tuple[str, int, str]]]:
    """Check all documentation files for broken local references."""
    checked = 0
    unresolved: list[tuple[str, int, str]] = []

    files = active_doc_files(repo, docs, root_docs, excluded_dirs)
    for doc_path in files:
        doc_rel = rel(repo, doc_path)
        doc_dir = doc_path.parent
        for line_no, raw_ref in extract_path_refs(doc_path):
            base_ref, _ = split_ref_fragment(raw_ref)
            if not base_ref or is_placeholder(base_ref):
                continue

            if is_forbidden_absolute_path(raw_ref):
                unresolved.append((doc_rel, line_no, f"forbidden absolute path or URI: {raw_ref}"))
                checked += 1
                continue

            if is_external_link(base_ref):
                continue

            checked += 1
            # Try relative to doc directory
            target_path = (doc_dir / base_ref).resolve()
            if target_path.exists():
                continue

            # Try relative to repo root
            root_target = (repo / base_ref.lstrip("/")).resolve()
            if root_target.exists():
                continue

            unresolved.append((doc_rel, line_no, raw_ref))

    return checked, unresolved
