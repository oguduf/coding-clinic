import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT = Path(__file__).parents[1] / "scripts" / "release.py"
spec = importlib.util.spec_from_file_location("release", SCRIPT)
release = importlib.util.module_from_spec(spec)
sys.modules[spec.name] = release
spec.loader.exec_module(release)


class ReleaseTests(unittest.TestCase):
    def test_patch_minor_major_detection(self):
        self.assertEqual(release.release_type([release.Commit("a", "fix: bug", "fix", False)]), "patch")
        self.assertEqual(release.release_type([release.Commit("a", "feat: thing", "feat", False)]), "minor")
        self.assertEqual(release.release_type([release.Commit("a", "feat!: change", "feat", True)]), "major")

    def test_breaking_footer_is_major(self):
        with tempfile.TemporaryDirectory() as directory:
            self.init_repo(directory)
            self.commit(directory, "fix: adjust endpoint", "BREAKING CHANGE: clients must migrate")
            commits = self.in_repo(directory, release.read_commits, None)
            self.assertEqual(release.release_type(commits), "major")

    def test_highest_bump_wins_and_nonrelease_commits_ignored(self):
        commits = [release.Commit("a", "fix: bug", "fix", False), release.Commit("b", "feat: feature", "feat", False)]
        self.assertEqual(release.release_type(commits), "minor")
        self.assertIsNone(release.release_type([]))

    def test_first_release_uses_zero_baseline(self):
        self.assertEqual(release.next_version("0.0.0", "minor"), "0.1.0")

    def test_latest_valid_tag_detection(self):
        with tempfile.TemporaryDirectory() as directory:
            self.init_repo(directory)
            self.commit(directory, "chore: initial")
            self.in_repo(directory, release.run_git, "tag", "v1.2.0")
            self.in_repo(directory, release.run_git, "tag", "v1.10.0")
            self.in_repo(directory, release.run_git, "tag", "latest")
            self.assertEqual(self.in_repo(directory, release.latest_version_tag), "v1.10.0")

    def test_changelog_groups_commits_and_preserves_history_without_duplicates(self):
        commits = [release.Commit("a1", "feat: dashboard", "feat", False), release.Commit("b2", "fix: login", "fix", False)]
        generated = release.changelog("1.2.0", commits)
        self.assertIn("### Features", generated)
        self.assertIn("### Bug Fixes", generated)
        existing = "# Changelog\n\n## v1.1.0\n\nOld release.\n"
        updated = release.changelog("1.2.0", commits, existing)
        self.assertIn("## v1.1.0", updated)
        self.assertEqual(release.changelog("1.2.0", commits, updated), updated)

    def test_duplicate_tag_refused_and_dry_run_is_read_only(self):
        with tempfile.TemporaryDirectory() as directory:
            self.init_repo(directory)
            self.commit(directory, "fix: initial fix")
            before = self.in_repo(directory, release.run_git, "tag", "--list")
            args = type("Args", (), {"dry_run": True, "create_tag": False, "push_tag": False})()
            self.in_repo(directory, release.prepare, args)
            after = self.in_repo(directory, release.run_git, "tag", "--list")
            self.assertEqual(before, after)
            self.in_repo(directory, release.run_git, "tag", "v0.0.1")
            args.dry_run, args.create_tag = False, True
            with patch.object(release, "latest_version_tag", return_value=None):
                with self.assertRaisesRegex(RuntimeError, "Refusing to overwrite"):
                    self.in_repo(directory, release.prepare, args)

    def test_enabled_tag_creation_makes_annotated_local_tag(self):
        with tempfile.TemporaryDirectory() as directory:
            self.init_repo(directory)
            self.commit(directory, "feat: initial capability")
            args = type("Args", (), {"dry_run": False, "create_tag": True, "push_tag": False})()
            self.in_repo(directory, release.prepare, args)
            tag = self.in_repo(directory, release.run_git, "for-each-ref", "refs/tags/v0.1.0", "--format=%(object)")
            self.assertTrue(tag)

    def test_nonrelease_git_commit_produces_no_version(self):
        with tempfile.TemporaryDirectory() as directory:
            self.init_repo(directory)
            self.commit(directory, "docs: clarify setup")
            self.assertEqual(self.in_repo(directory, release.read_commits, None), [])

    def test_invalid_version_rejected(self):
        with self.assertRaises(ValueError):
            release.next_version("01.2.3", "patch")

    @staticmethod
    def init_repo(directory):
        subprocess.run(["git", "init", "-q", directory], check=True)
        subprocess.run(["git", "-C", directory, "config", "user.name", "Test"], check=True)
        subprocess.run(["git", "-C", directory, "config", "user.email", "test@example.invalid"], check=True)

    @staticmethod
    def commit(directory, subject, body=""):
        file_path = Path(directory) / "file.txt"
        file_path.write_text(subject, encoding="utf-8")
        subprocess.run(["git", "-C", directory, "add", "file.txt"], check=True)
        command = ["git", "-C", directory, "commit", "-q", "-m", subject]
        if body:
            command.extend(["-m", body])
        subprocess.run(command, check=True)

    @staticmethod
    def in_repo(directory, function, *args, **kwargs):
        def run_git(*git_args, check=True):
            result = subprocess.run(["git", "-C", directory, *git_args], text=True, capture_output=True, check=False)
            if check and result.returncode:
                raise RuntimeError(result.stderr.strip())
            return result.stdout.rstrip("\r\n")

        original_directory = os.getcwd()
        try:
            os.chdir(directory)
            with patch.object(release, "run_git", run_git):
                return function(*args, **kwargs)
        finally:
            os.chdir(original_directory)


if __name__ == "__main__":
    unittest.main()
