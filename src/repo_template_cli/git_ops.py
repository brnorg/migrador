from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path
import shutil
import subprocess


class CommandError(RuntimeError):
    def __init__(self, command: list[str], cwd: Path | None, stderr: str) -> None:
        location = f" em {cwd}" if cwd else ""
        message = f"Comando falhou{location}: {' '.join(command)}"
        if stderr.strip():
            message += f"\n{stderr.strip()}"
        super().__init__(message)
        self.command = command
        self.cwd = cwd
        self.stderr = stderr


@dataclass
class CommandResult:
    stdout: str
    stderr: str


@dataclass
class CloneInfo:
    path: Path
    branch_existed: bool


def require_command(name: str) -> None:
    run([name, "--version"])


def run(
    command: list[str],
    cwd: Path | None = None,
    input_text: str | None = None,
    timeout: int | None = 120,
) -> CommandResult:
    env = os.environ.copy()
    if command and command[0] == "git":
        env.setdefault("GIT_TERMINAL_PROMPT", "0")
        # Aceita certificados interceptados ou nao confiaveis em todas as
        # operacoes HTTPS executadas pelo Git.
        env["GIT_SSL_NO_VERIFY"] = "true"
    try:
        completed = subprocess.run(
            command,
            cwd=str(cwd) if cwd else None,
            input=input_text,
            text=True,
            capture_output=True,
            check=False,
            timeout=timeout,
            env=env,
        )
    except subprocess.TimeoutExpired as exc:
        raise CommandError(command, cwd, f"Timeout apos {timeout}s") from exc
    if completed.returncode != 0:
        raise CommandError(command, cwd, completed.stderr or completed.stdout)
    return CommandResult(stdout=completed.stdout, stderr=completed.stderr)


def prepare_clone(
    workspace: Path,
    owner: str,
    repo: str,
    clone_url: str,
    branch: str,
    base_branch: str,
) -> CloneInfo:
    workspace = workspace.resolve()
    workspace.mkdir(parents=True, exist_ok=True)
    clone_dir = (workspace / f"{owner}_{repo}").resolve()
    _remove_existing_clone(workspace, clone_dir)

    run(["git", "clone", clone_url, str(clone_dir)])
    remote_branch = remote_branch_exists(clone_dir, branch)
    if remote_branch:
        run(["git", "checkout", "-B", branch, f"origin/{branch}"], cwd=clone_dir)
    else:
        run(["git", "fetch", "origin", base_branch], cwd=clone_dir)
        run(["git", "checkout", "-B", branch, f"origin/{base_branch}"], cwd=clone_dir)
    return CloneInfo(path=clone_dir, branch_existed=remote_branch)


def commit_all(repo_dir: Path, message: str) -> bool:
    run(["git", "add", "-A"], cwd=repo_dir)
    status = run(["git", "status", "--porcelain"], cwd=repo_dir).stdout.strip()
    if not status:
        return False
    run(["git", "commit", "-m", message], cwd=repo_dir)
    return True


def push_branch(repo_dir: Path, branch: str) -> None:
    run(["git", "push", "--set-upstream", "origin", branch], cwd=repo_dir)


def remote_branch_exists(repo_dir: Path, branch: str) -> bool:
    result = run(["git", "ls-remote", "--heads", "origin", branch], cwd=repo_dir)
    return bool(result.stdout.strip())


def remote_head_exists_url(clone_url: str, branch: str) -> bool:
    result = run(["git", "ls-remote", "--heads", clone_url, branch])
    return bool(result.stdout.strip())


def _remove_existing_clone(workspace: Path, clone_dir: Path) -> None:
    if not clone_dir.exists():
        return
    try:
        clone_dir.relative_to(workspace)
    except ValueError as exc:
        raise ValueError(f"Diretorio de clone inseguro: {clone_dir}") from exc
    shutil.rmtree(clone_dir)
