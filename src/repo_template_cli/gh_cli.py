from __future__ import annotations

from dataclasses import dataclass

from . import git_ops
from .config import (
    EnvironmentSpec,
    NamedValue,
    RepositorySpec,
    environment_for_repository,
    is_blank,
    named_value_for_repository,
)
from .render import render_value


@dataclass
class GhApplySummary:
    variables_set: int = 0
    secrets_set: int = 0
    blank_skipped: list[str] | None = None

    def __post_init__(self) -> None:
        if self.blank_skipped is None:
            self.blank_skipped = []


def apply_repository_settings(
    repo: RepositorySpec,
    context: dict[str, object],
    global_variables: list[NamedValue],
    global_secrets: list[NamedValue],
    global_environments: list[EnvironmentSpec],
    repo_index: int,
    repo_count: int,
) -> GhApplySummary:
    full_name = repo.full_name
    summary = GhApplySummary()

    for variable in _selected_named_values([*global_variables, *repo.variables], repo_index, repo_count):
        _set_variable(full_name, variable, context, summary)

    for secret in _selected_named_values([*global_secrets, *repo.secrets], repo_index, repo_count):
        _set_secret(full_name, secret, context, summary)

    for environment in _selected_environments(
        [*global_environments, *repo.environments],
        repo_index,
        repo_count,
    ):
        if not _has_non_blank_items(environment):
            for variable in environment.variables:
                summary.blank_skipped.append(_label("variable", variable.name, environment.name))
            for secret in environment.secrets:
                summary.blank_skipped.append(_label("secret", secret.name, environment.name))
            continue

        _ensure_environment(full_name, environment.name)
        for variable in environment.variables:
            _set_variable(full_name, variable, context, summary, env_name=environment.name)
        for secret in environment.secrets:
            _set_secret(full_name, secret, context, summary, env_name=environment.name)

    return summary


def _set_variable(
    full_name: str,
    variable: NamedValue,
    context: dict[str, object],
    summary: GhApplySummary,
    env_name: str | None = None,
) -> None:
    if is_blank(variable.value):
        summary.blank_skipped.append(_label("variable", variable.name, env_name))
        return

    value = str(render_value(variable.value, context))
    command = ["gh", "variable", "set", variable.name, "--repo", full_name, "--body", value]
    if env_name:
        command.extend(["--env", env_name])
    git_ops.run(command)
    summary.variables_set += 1


def _set_secret(
    full_name: str,
    secret: NamedValue,
    context: dict[str, object],
    summary: GhApplySummary,
    env_name: str | None = None,
) -> None:
    if is_blank(secret.value):
        summary.blank_skipped.append(_label("secret", secret.name, env_name))
        return

    value = str(render_value(secret.value, context))
    command = ["gh", "secret", "set", secret.name, "--repo", full_name]
    if env_name:
        command.extend(["--env", env_name])
    git_ops.run(command, input_text=value)
    summary.secrets_set += 1


def _ensure_environment(full_name: str, env_name: str) -> None:
    git_ops.run(
        ["gh", "api", "--method", "PUT", f"/repos/{full_name}/environments/{env_name}"]
    )


def _has_non_blank_items(environment: EnvironmentSpec) -> bool:
    return any(not is_blank(item.value) for item in [*environment.variables, *environment.secrets])


def _selected_named_values(
    values: list[NamedValue],
    repo_index: int,
    repo_count: int,
) -> list[NamedValue]:
    return [
        named_value_for_repository(value, repo_index, repo_count)
        for value in values
    ]


def _selected_environments(
    environments: list[EnvironmentSpec],
    repo_index: int,
    repo_count: int,
) -> list[EnvironmentSpec]:
    return [
        environment_for_repository(environment, repo_index, repo_count)
        for environment in environments
    ]


def _label(kind: str, name: str, env_name: str | None) -> str:
    scope = f"environment:{env_name}" if env_name else "repository"
    return f"{scope} {kind} {name}"
