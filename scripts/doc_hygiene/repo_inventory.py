"""Shared repository inventory path rules for function compiler documentation tooling."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

EXCLUDED_DIRS = {
    ".git",
    ".gradle",
    ".gradle-user-home",
    "build",
    "run",
    "logs",
    "__pycache__",
    ".idea",
    ".vscode",
    ".pytest_cache",
}

EXCLUDED_PATH_PREFIXES = {
    "run/",
    "build/",
    "logs/",
    ".gradle/",
    ".gradle-user-home/",
}

INCLUDED_ROOTS = [
    "src",
    "scripts",
    "benchmarks",
    "docs",
    "tests",
]

ROOT_DOCS = [
    "README.md",
    "CHANGELOG.md",
    "CONTRIBUTING.md",
]

INDEXED_EXTENSIONS = {
    ".java",
    ".py",
    ".json",
    ".csv",
    ".md",
    ".mcfunction",
    ".gradle",
    ".properties",
    ".sh",
}


@dataclass
class FileEntry:
    path: Path
    kind: str


def rel(repo: Path, path: Path) -> str:
    return path.relative_to(repo).as_posix()


def matches_excluded_path_prefix(path: Path, repo: Path) -> bool:
    try:
        relative_text = path.relative_to(repo).as_posix()
    except ValueError:
        return True
    return any(
        relative_text == prefix.rstrip("/") or relative_text.startswith(prefix)
        for prefix in EXCLUDED_PATH_PREFIXES
    )


def is_excluded_repo_path(path: Path, repo: Path) -> bool:
    try:
        relative = path.relative_to(repo)
    except ValueError:
        return True
    if bool(set(relative.parts) & EXCLUDED_DIRS):
        return True
    return matches_excluded_path_prefix(path, repo)


def iter_repo_files(repo: Path) -> list[FileEntry]:
    entries: list[FileEntry] = []
    for root_name in INCLUDED_ROOTS:
        root = repo / root_name
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if not path.is_file():
                continue
            if is_excluded_repo_path(path, repo):
                continue
            suffix = path.suffix.lower()
            if suffix in INDEXED_EXTENSIONS or path.name in ROOT_DOCS:
                entries.append(FileEntry(path=path, kind=suffix.lstrip(".") or "file"))

    for doc_name in ROOT_DOCS:
        doc_path = repo / doc_name
        if doc_path.is_file():
            entries.append(FileEntry(path=doc_path, kind="md"))

    return sorted(entries, key=lambda entry: rel(repo, entry.path))
