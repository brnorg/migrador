from __future__ import annotations

import base64
from dataclasses import dataclass
import hashlib
import os

import requests
import urllib3

from . import git_ops
from .render import RenderedFile, overwritten_backup_path


class GitHubApiError(RuntimeError):
    pass


@dataclass
class PullRequestResult:
    url: str
    number: int
    existed: bool


@dataclass
class ApiCommitResult:
    commit_sha: str = ""
    commit_url: str = ""
    branch_existed: bool = False
    changed: bool = False
    file_count: int = 0


class GitHubClient:
    def __init__(self, token: str) -> None:
        self.session = requests.Session()
        # Ambientes corporativos podem interceptar HTTPS (por exemplo, Zscaler).
        # Esta ferramenta foi configurada para aceitar qualquer certificado TLS.
        self.session.verify = False
        urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)
        self.session.headers.update(
            {
                "Accept": "application/vnd.github+json",
                "Authorization": f"Bearer {token}",
                "X-GitHub-Api-Version": "2026-03-10",
            }
        )

    @classmethod
    def from_environment_or_gh(cls) -> "GitHubClient":
        token = os.getenv("GITHUB_TOKEN") or os.getenv("GH_TOKEN")
        if not token:
            try:
                token = git_ops.run(["gh", "auth", "token"]).stdout.strip()
            except Exception as exc:
                raise GitHubApiError(
                    "Informe GITHUB_TOKEN/GH_TOKEN ou faca login no GitHub CLI com `gh auth login`."
                ) from exc
        return cls(token)

    def default_branch(self, owner: str, repo: str) -> str:
        data = self.repository(owner, repo)
        return str(data["default_branch"])

    def repository(self, owner: str, repo: str) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}")

    def get_ref(self, owner: str, repo: str, ref: str) -> dict | None:
        return self._request("GET", f"/repos/{owner}/{repo}/git/ref/{ref}", allow_404=True)

    def create_ref(self, owner: str, repo: str, ref: str, sha: str) -> dict:
        payload = {"ref": ref, "sha": sha}
        return self._request("POST", f"/repos/{owner}/{repo}/git/refs", json=payload)

    def update_ref(self, owner: str, repo: str, ref: str, sha: str, force: bool = False) -> dict:
        payload = {"sha": sha, "force": force}
        return self._request("PATCH", f"/repos/{owner}/{repo}/git/refs/{ref}", json=payload)

    def get_git_commit(self, owner: str, repo: str, sha: str) -> dict:
        return self._request("GET", f"/repos/{owner}/{repo}/git/commits/{sha}")

    def create_blob(self, owner: str, repo: str, content: bytes) -> str:
        payload = {
            "content": base64.b64encode(content).decode("ascii"),
            "encoding": "base64",
        }
        data = self._request("POST", f"/repos/{owner}/{repo}/git/blobs", json=payload)
        return str(data["sha"])

    def create_tree(self, owner: str, repo: str, base_tree: str, tree: list[dict]) -> str:
        payload = {"base_tree": base_tree, "tree": tree}
        data = self._request("POST", f"/repos/{owner}/{repo}/git/trees", json=payload)
        return str(data["sha"])

    def get_tree(self, owner: str, repo: str, tree_sha: str, recursive: bool = False) -> dict:
        params = {"recursive": "1"} if recursive else None
        return self._request("GET", f"/repos/{owner}/{repo}/git/trees/{tree_sha}", params=params)

    def create_commit(self, owner: str, repo: str, message: str, tree: str, parents: list[str]) -> dict:
        payload = {"message": message, "tree": tree, "parents": parents}
        return self._request("POST", f"/repos/{owner}/{repo}/git/commits", json=payload)

    def apply_files_commit(
        self,
        owner: str,
        repo: str,
        branch: str,
        base_branch: str,
        message: str,
        files: list[RenderedFile],
    ) -> ApiCommitResult:
        base_ref = self.get_ref(owner, repo, f"heads/{base_branch}")
        if not base_ref:
            raise GitHubApiError(f"Branch base nao encontrada: {base_branch}")

        branch_ref = self.get_ref(owner, repo, f"heads/{branch}")
        branch_existed = branch_ref is not None
        head_sha = str((branch_ref or base_ref)["object"]["sha"])
        head_commit = self.get_git_commit(owner, repo, head_sha)
        head_tree_sha = str(head_commit["tree"]["sha"])

        tree_entries = []
        current_tree = self.get_tree(owner, repo, head_tree_sha, recursive=True)
        if current_tree.get("truncated"):
            raise GitHubApiError("Arvore do repositorio truncada; nao e seguro preservar arquivos sobrescritos.")
        current_files = {
            str(entry["path"]): entry
            for entry in current_tree.get("tree", [])
            if entry.get("type") == "blob"
        }
        rendered_paths = {file.path for file in files}
        for file in files:
            current = current_files.get(file.path)
            current_sha = str(current.get("sha", "")) if current else ""
            if current and current_sha != _git_blob_sha(file.content):
                backup_path = overwritten_backup_path(file.path)
                if backup_path not in rendered_paths and backup_path not in current_files:
                    tree_entries.append(
                        {
                            "path": backup_path,
                            "mode": str(current.get("mode", "100644")),
                            "type": "blob",
                            "sha": current_sha,
                        }
                    )
            entry = {"path": file.path, "mode": file.mode, "type": "blob"}
            if file.text is not None:
                entry["content"] = file.text
            else:
                entry["sha"] = self.create_blob(owner, repo, file.content)
            tree_entries.append(entry)

        new_tree_sha = self.create_tree(owner, repo, head_tree_sha, tree_entries)
        if new_tree_sha == head_tree_sha:
            return ApiCommitResult(
                commit_sha=head_sha,
                branch_existed=branch_existed,
                changed=False,
                file_count=len(files),
            )

        commit = self.create_commit(owner, repo, message, new_tree_sha, [head_sha])
        commit_sha = str(commit["sha"])
        if branch_existed:
            self.update_ref(owner, repo, f"heads/{branch}", commit_sha, force=False)
        else:
            self.create_ref(owner, repo, f"refs/heads/{branch}", commit_sha)

        return ApiCommitResult(
            commit_sha=commit_sha,
            commit_url=str(commit.get("html_url", "")),
            branch_existed=branch_existed,
            changed=True,
            file_count=len(files),
        )

    def create_or_get_pull_request(
        self,
        owner: str,
        repo: str,
        head: str,
        base: str,
        title: str,
        body: str,
    ) -> PullRequestResult:
        existing = self._find_open_pr(owner, repo, head, base)
        if existing:
            return PullRequestResult(
                url=str(existing["html_url"]),
                number=int(existing["number"]),
                existed=True,
            )

        payload = {"title": title, "head": head, "base": base, "body": body}
        try:
            created = self._request("POST", f"/repos/{owner}/{repo}/pulls", json=payload)
        except GitHubApiError:
            existing = self._find_open_pr(owner, repo, head, base)
            if existing:
                return PullRequestResult(
                    url=str(existing["html_url"]),
                    number=int(existing["number"]),
                    existed=True,
                )
            raise

        return PullRequestResult(
            url=str(created["html_url"]),
            number=int(created["number"]),
            existed=False,
        )

    def _find_open_pr(self, owner: str, repo: str, head: str, base: str) -> dict | None:
        params = {"state": "open", "head": f"{owner}:{head}", "base": base}
        prs = self._request("GET", f"/repos/{owner}/{repo}/pulls", params=params)
        if isinstance(prs, list) and prs:
            return prs[0]
        return None

    def _request(self, method: str, path: str, allow_404: bool = False, **kwargs):
        url = f"https://api.github.com{path}"
        response = self.session.request(method, url, timeout=30, **kwargs)
        if allow_404 and response.status_code == 404:
            return None
        if response.status_code >= 400:
            detail = response.text
            try:
                detail = response.json().get("message", detail)
            except ValueError:
                pass
            raise GitHubApiError(f"GitHub API {method} {path} falhou: {detail}")
        if response.status_code == 204:
            return None
        return response.json()


def _git_blob_sha(content: bytes) -> str:
    header = f"blob {len(content)}\0".encode("ascii")
    return hashlib.sha1(header + content).hexdigest()
