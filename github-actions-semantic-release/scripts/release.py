#!/usr/bin/env python3
"""Prepare a semantic release from Conventional Commits."""

from __future__ import annotations

import argparse
import os
import re
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

VERSION_RE = re.compile(r"^v?(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
TAG_RE = re.compile(r"^v(0|[1-9]\d*)\.(0|[1-9]\d*)\.(0|[1-9]\d*)$")
COMMIT_RE = re.compile(r"^(?P<type>[a-z]+)(?:\((?P<scope>[^\n()]+)\))?(?P<breaking>!)?: (?P<subject>.+)$")
LEVELS = {None: 0, "patch": 1, "minor": 2, "major": 3}


@dataclass(frozen=True)
class Commit:
    hash: str
    subject: str
    commit_type: str
    breaking: bool


def run_git(*args: str, check: bool = True) -> str:
    result = subprocess.run(["git", *args], text=True, capture_output=True, check=False)
    if check and result.returncode:
        raise RuntimeError(result.stderr.strip() or f"git {' '.join(args)} failed")
    return result.stdout.rstrip("\r\n")


def parse_version(value: str) -> tuple[int, int, int] | None:
    match = VERSION_RE.fullmatch(value)
    return tuple(map(int, match.groups())) if match else None


def latest_version_tag() -> str | None:
    tags = run_git("tag", "--list")
    versions = [(parse_version(tag[1:]), tag) for tag in tags.splitlines() if TAG_RE.fullmatch(tag)]
    valid = [(version, tag) for version, tag in versions if version is not None]
    return max(valid, key=lambda item: item[0])[1] if valid else None


def read_commits(since_tag: str | None) -> list[Commit]:
    revision = f"{since_tag}..HEAD" if since_tag else "HEAD"
    raw = run_git("log", "--format=%H%x1f%s%x1f%b%x1e", revision)
    commits: list[Commit] = []
    for record in raw.split("\x1e"):
        fields = record.strip("\n").split("\x1f", 2)
        if len(fields) != 3:
            continue
        commit_hash, subject, body = fields
        match = COMMIT_RE.fullmatch(subject)
        if not match:
            continue
        kind = match.group("type")
        breaking = bool(match.group("breaking")) or bool(
            re.search(r"(?im)^BREAKING CHANGE:\s*\S", body)
        )
        if kind not in {"feat", "fix"} and not breaking:
            continue
        commits.append(Commit(commit_hash[:7], subject, kind, breaking))
    return commits


def release_type(commits: list[Commit]) -> str | None:
    if any(commit.breaking for commit in commits):
        return "major"
    if any(commit.commit_type == "feat" for commit in commits):
        return "minor"
    if any(commit.commit_type == "fix" for commit in commits):
        return "patch"
    return None


def next_version(current: str, bump: str) -> str:
    version = parse_version(current)
    if version is None:
        raise ValueError(f"Invalid current semantic version: {current}")
    major, minor, patch = version
    if bump == "major":
        major, minor, patch = major + 1, 0, 0
    elif bump == "minor":
        minor, patch = minor + 1, 0
    elif bump == "patch":
        patch += 1
    else:
        raise ValueError(f"Invalid release type: {bump}")
    return f"{major}.{minor}.{patch}"


def changelog(version: str, commits: list[Commit], existing: str = "") -> str:
    heading = f"## v{version}"
    if heading in existing.splitlines():
        return existing
    groups = [("Features", "feat"), ("Bug Fixes", "fix")]
    lines = ["# Changelog", "", heading, ""]
    for title, kind in groups:
        matching = [c for c in commits if c.commit_type == kind]
        if matching:
            lines.extend([f"### {title}"])
            lines.extend([f"- {c.subject} ({c.hash})" for c in matching])
            lines.append("")
    section = "\n".join(lines).rstrip() + "\n"
    if not existing.strip():
        return section
    prior = existing.rstrip()
    if not prior.startswith("# Changelog"):
        prior = "# Changelog\n\n" + prior
    return prior + "\n\n" + section.split("\n", 2)[2]


def set_output(name: str, value: str) -> None:
    output = os.environ.get("GITHUB_OUTPUT")
    if not output:
        return
    delimiter = "release_output_7f3a9c"
    while delimiter in value:
        delimiter += "x"
    with open(output, "a", encoding="utf-8") as stream:
        stream.write(f"{name}<<{delimiter}\n{value}\n{delimiter}\n")


def prepare(args: argparse.Namespace) -> int:
    current_tag = latest_version_tag()
    current = current_tag[1:] if current_tag else "0.0.0"
    commits = read_commits(current_tag)
    bump = release_type(commits)
    new_version = next_version(current, bump) if bump else current
    tag = f"v{new_version}" if bump else ""
    change_text = changelog(new_version, commits, Path("CHANGELOG.md").read_text(encoding="utf-8") if Path("CHANGELOG.md").exists() else "") if bump else ""

    if tag:
        print(f"Release: {current} -> {new_version} ({bump})")
        print(f"Tag: {tag}")
        print(change_text, end="")
    else:
        print(f"No qualifying commits since {current_tag or 'repository start'}; no release needed.")

    if args.dry_run:
        print("Dry-run: repository was not modified.")
    elif tag and args.create_tag:
        if run_git("tag", "--list", tag):
            raise RuntimeError(f"Refusing to overwrite existing tag {tag}")
        run_git("tag", "-a", tag, "-m", f"Release {tag}")
        print(f"Created local annotated tag {tag}.")
    elif not args.dry_run and args.create_tag:
        print("No tag created because no release is required.")

    if args.push_tag:
        if args.dry_run or not args.create_tag:
            raise RuntimeError("Pushing requires dry-run=false and create-tag=true")
        if os.environ.get("RELEASE_PUBLISH_AUTHORIZED", "").lower() != "true":
            raise RuntimeError("Tag publishing requires RELEASE_PUBLISH_AUTHORIZED=true")
        if os.environ.get("GITHUB_REF_PROTECTED", "").lower() != "true":
            raise RuntimeError("Tag publishing requires a GitHub-protected ref")
        if not os.environ.get("GITHUB_TOKEN"):
            raise RuntimeError("Tag publishing requires GITHUB_TOKEN")
        if not tag:
            raise RuntimeError("No release tag is available to push")
        run_git("push", "origin", tag)
        print(f"Pushed tag {tag}.")

    set_output("current-version", current)
    set_output("next-version", new_version)
    set_output("release-type", bump or "none")
    set_output("tag-name", tag)
    set_output("changelog", change_text)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", choices=("true", "false"), default="true")
    parser.add_argument("--create-tag", choices=("true", "false"), default="false")
    parser.add_argument("--push-tag", choices=("true", "false"), default="false")
    args = parser.parse_args()
    args.dry_run = args.dry_run == "true"
    args.create_tag = args.create_tag == "true"
    args.push_tag = args.push_tag == "true"
    try:
        return prepare(args)
    except (RuntimeError, ValueError, OSError) as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
