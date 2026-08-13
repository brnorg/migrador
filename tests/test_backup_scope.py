from __future__ import annotations

from pathlib import Path
import tempfile
import unittest

from repo_template_cli.github_api import GitHubClient
from repo_template_cli.render import (
    RenderedFile,
    overwritten_backup_path,
    render_template_tree,
    should_preserve_overwritten_file,
)


class RecordingGitHubClient(GitHubClient):
    def __init__(self) -> None:
        self.tree_entries: list[dict] = []

    def get_ref(self, owner: str, repo: str, ref: str) -> dict | None:
        if ref == "heads/main":
            return {"object": {"sha": "head-sha"}}
        return None

    def get_git_commit(self, owner: str, repo: str, sha: str) -> dict:
        return {"tree": {"sha": "head-tree"}}

    def get_tree(self, owner: str, repo: str, tree_sha: str, recursive: bool = False) -> dict:
        return {
            "tree": [
                {
                    "path": ".github/workflows/ci.yml",
                    "type": "blob",
                    "mode": "100644",
                    "sha": "old-workflow-sha",
                },
                {
                    "path": "config.yml",
                    "type": "blob",
                    "mode": "100644",
                    "sha": "old-config-sha",
                },
            ]
        }

    def create_tree(self, owner: str, repo: str, base_tree: str, tree: list[dict]) -> str:
        self.tree_entries = tree
        return "new-tree"

    def create_commit(self, owner: str, repo: str, message: str, tree: str, parents: list[str]) -> dict:
        return {"sha": "new-commit", "html_url": "https://example.test/commit"}

    def create_ref(self, owner: str, repo: str, ref: str, sha: str) -> dict:
        return {}


class BackupScopeTests(unittest.TestCase):
    def test_only_files_inside_github_workflows_are_selected(self) -> None:
        self.assertTrue(should_preserve_overwritten_file(".github/workflows/ci.yml"))
        self.assertTrue(should_preserve_overwritten_file(".github/workflows/nested/ci.yml"))
        self.assertTrue(should_preserve_overwritten_file(r".github\workflows\ci.yml"))
        self.assertFalse(should_preserve_overwritten_file("config.yml"))
        self.assertFalse(should_preserve_overwritten_file(".github/actions/ci.yml"))
        self.assertFalse(should_preserve_overwritten_file("other/.github/workflows/ci.yml"))
        self.assertFalse(should_preserve_overwritten_file(".github/workflows-old/ci.yml"))

    def test_backup_path_cannot_be_generated_outside_github_workflows(self) -> None:
        self.assertEqual(
            overwritten_backup_path(".github/workflows/ci.yml"),
            ".github/workflows/ci_m.yml",
        )
        self.assertIsNone(overwritten_backup_path("config.yml"))
        self.assertIsNone(overwritten_backup_path("src/config.yml"))
        self.assertIsNone(overwritten_backup_path(".github/actions/ci.yml"))
        self.assertIsNone(overwritten_backup_path("other/.github/workflows/ci.yml"))

    def test_git_render_creates_backup_only_in_github_workflows(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            root = Path(temp_dir)
            template = root / "template"
            destination = root / "destination"

            (template / ".github" / "workflows").mkdir(parents=True)
            (destination / ".github" / "workflows").mkdir(parents=True)
            (template / ".github" / "workflows" / "ci.yml").write_text("new workflow", encoding="utf-8")
            (destination / ".github" / "workflows" / "ci.yml").write_text("old workflow", encoding="utf-8")

            template.mkdir(exist_ok=True)
            destination.mkdir(exist_ok=True)
            (template / "config.yml").write_text("new config", encoding="utf-8")
            (destination / "config.yml").write_text("old config", encoding="utf-8")

            render_template_tree(template, destination, {})

            self.assertEqual(
                (destination / ".github" / "workflows" / "ci_m.yml").read_text(encoding="utf-8"),
                "old workflow",
            )
            self.assertFalse((destination / "config_m.yml").exists())

    def test_api_commit_creates_backup_only_in_github_workflows(self) -> None:
        client = RecordingGitHubClient()

        client.apply_files_commit(
            "owner",
            "repo",
            "migration",
            "main",
            "Apply template",
            [
                RenderedFile(".github/workflows/ci.yml", b"new workflow", "new workflow"),
                RenderedFile("config.yml", b"new config", "new config"),
            ],
        )

        paths = [entry["path"] for entry in client.tree_entries]
        self.assertIn(".github/workflows/ci_m.yml", paths)
        self.assertNotIn("config_m.yml", paths)


if __name__ == "__main__":
    unittest.main()
