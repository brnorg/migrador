from __future__ import annotations

from dataclasses import dataclass, field
import json
from pathlib import Path
import re
from typing import Any


def is_blank(value: Any) -> bool:
    return value is None or value == ""


@dataclass
class FieldSpec:
    name: str
    label: str
    value: Any = ""
    required: bool = True
    secret: bool = False
    render: bool = True


@dataclass
class NamedValue:
    name: str
    value: Any = ""

    @property
    def is_blank(self) -> bool:
        return is_blank(self.value)


@dataclass
class EnvironmentSpec:
    name: str
    variables: list[NamedValue] = field(default_factory=list)
    secrets: list[NamedValue] = field(default_factory=list)


@dataclass
class PullRequestSpec:
    title: str = "Apply template"
    body: str = "Template applied by repo-template."
    base: str = ""


@dataclass
class RepositoryFolderSpec:
    source: str = ""
    target: str = ""


@dataclass
class RepositorySpec:
    owner: str = ""
    name: str = ""
    url: str = ""
    template: str = ""
    branch: str = ""
    base: str = ""
    default_branch: str = ""
    folders: list[RepositoryFolderSpec] = field(default_factory=list)
    variables: list[NamedValue] = field(default_factory=list)
    secrets: list[NamedValue] = field(default_factory=list)
    environments: list[EnvironmentSpec] = field(default_factory=list)

    @property
    def full_name(self) -> str:
        if self.owner and self.name:
            return f"{self.owner}/{self.name}"
        return ""


@dataclass
class ControlConfig:
    path: Path
    templates_root: Path
    workspace: Path
    apply_mode: str = "api"
    template: str = ""
    branch: str = ""
    commit_message: str = "Apply template"
    pull_request: PullRequestSpec = field(default_factory=PullRequestSpec)
    fields: list[FieldSpec] = field(default_factory=list)
    repositories: list[RepositorySpec] = field(default_factory=list)
    repo_variables: list[NamedValue] = field(default_factory=list)
    repo_secrets: list[NamedValue] = field(default_factory=list)
    environments: list[EnvironmentSpec] = field(default_factory=list)
    exclude: list[str] = field(default_factory=list)


def load_config(path: Path) -> ControlConfig:
    path = path.expanduser().resolve()
    with path.open("r", encoding="utf-8-sig") as file:
        raw = json.load(file)

    base_dir = path.parent
    templates_root = _resolve_path(raw.get("templates_root", "templates"), base_dir)
    workspace = _resolve_path(raw.get("workspace", ".repo-template-workspace"), base_dir)

    pr_raw = raw.get("pull_request") or raw.get("pr") or {}
    pull_request = PullRequestSpec(
        title=str(pr_raw.get("title", raw.get("pr_title", "Apply template"))),
        body=str(pr_raw.get("body", raw.get("pr_body", "Template applied by repo-template."))),
        base=str(pr_raw.get("base", raw.get("base", "")) or ""),
    )

    github_raw = raw.get("github") or {}
    repositories = _parse_repositories(raw.get("repositories", []))
    if not repositories:
        repositories = [RepositorySpec()]

    settings_repo_variables, settings_repo_secrets, settings_environments = _parse_settings(
        raw.get("settings", raw.get("github_settings", github_raw.get("settings", [])))
    )
    repo_variables = [
        *_parse_named_values(
            raw.get(
                "repository_variables",
                raw.get(
                    "repo_variables",
                    raw.get(
                        "variables",
                        github_raw.get(
                            "repository_variables",
                            github_raw.get("repo_variables", github_raw.get("variables", [])),
                        ),
                    ),
                ),
            )
        ),
        *settings_repo_variables,
    ]
    repo_secrets = [
        *_parse_named_values(
            raw.get(
                "repository_secrets",
                raw.get(
                    "repo_secrets",
                    raw.get(
                        "secrets",
                        github_raw.get(
                            "repository_secrets",
                            github_raw.get("repo_secrets", github_raw.get("secrets", [])),
                        ),
                    ),
                ),
            )
        ),
        *settings_repo_secrets,
    ]
    environments = _merge_environments(
        [
            *_parse_environments(
                raw.get("environments", github_raw.get("environments", []))
            ),
            *settings_environments,
        ]
    )

    return ControlConfig(
        path=path,
        templates_root=templates_root,
        workspace=workspace,
        apply_mode=str(raw.get("apply_mode", raw.get("transport", "api")) or "api").lower(),
        template=str(raw.get("template", "") or ""),
        branch=str(raw.get("branch", raw.get("branch_name", "")) or ""),
        commit_message=str(raw.get("commit_message", "Apply template")),
        pull_request=pull_request,
        fields=_parse_fields(raw.get("values", raw.get("fields", {}))),
        repositories=repositories,
        repo_variables=repo_variables,
        repo_secrets=repo_secrets,
        environments=environments,
        exclude=list(raw.get("exclude", [])),
    )


def value_for_repository(value: Any, repo_index: int, repo_count: int, label: str) -> Any:
    if not isinstance(value, list):
        return value
    if len(value) != repo_count:
        raise ValueError(
            f"{label} tem {len(value)} valor(es), mas o JSON possui {repo_count} repositorio(s)."
        )
    return value[repo_index]


def named_value_for_repository(
    value: NamedValue,
    repo_index: int,
    repo_count: int,
    label_prefix: str = "",
) -> NamedValue:
    label = f"{label_prefix}{value.name}" if label_prefix else value.name
    return NamedValue(
        name=value.name,
        value=value_for_repository(value.value, repo_index, repo_count, label),
    )


def environment_for_repository(
    environment: EnvironmentSpec,
    repo_index: int,
    repo_count: int,
) -> EnvironmentSpec:
    return EnvironmentSpec(
        name=environment.name,
        variables=[
            named_value_for_repository(value, repo_index, repo_count, f"{environment.name}.")
            for value in environment.variables
        ],
        secrets=[
            named_value_for_repository(value, repo_index, repo_count, f"{environment.name}.")
            for value in environment.secrets
        ],
    )


def _resolve_path(value: str, base_dir: Path) -> Path:
    path = Path(value).expanduser()
    if not path.is_absolute():
        path = base_dir / path
    return path.resolve()


def _parse_fields(node: Any) -> list[FieldSpec]:
    fields: list[FieldSpec] = []
    if isinstance(node, dict):
        iterable = node.items()
    elif isinstance(node, list):
        iterable = ((_field_name(item, index), item) for index, item in enumerate(node))
    else:
        return fields

    for name, raw in iterable:
        if isinstance(raw, dict):
            field_name = str(raw.get("name", raw.get("key", name)))
            fields.append(
                FieldSpec(
                    name=field_name,
                    label=str(raw.get("label", field_name)),
                    value=raw.get("value", ""),
                    required=bool(raw.get("required", True)),
                    secret=bool(raw.get("secret", False)),
                    render=bool(raw.get("render", True)),
                )
            )
        else:
            field_name = str(name)
            fields.append(FieldSpec(name=field_name, label=field_name, value=raw))
    return fields


def _field_name(item: Any, index: int) -> str:
    if isinstance(item, dict) and (item.get("name") or item.get("key")):
        return str(item.get("name") or item["key"])
    return f"field_{index + 1}"


def _parse_named_values(node: Any) -> list[NamedValue]:
    values: list[NamedValue] = []
    if isinstance(node, dict):
        iterable = node.items()
    elif isinstance(node, list):
        iterable = ((_named_value_name(item, index), item) for index, item in enumerate(node))
    else:
        return values

    for name, raw in iterable:
        if isinstance(raw, dict):
            value_name = str(raw.get("name", raw.get("key", name)))
            values.append(NamedValue(name=value_name, value=raw.get("value", "")))
        else:
            values.append(NamedValue(name=str(name), value=raw))
    return values


def _named_value_name(item: Any, index: int) -> str:
    if isinstance(item, dict) and (item.get("name") or item.get("key")):
        return str(item.get("name") or item["key"])
    return f"value_{index + 1}"


def _parse_environments(node: Any) -> list[EnvironmentSpec]:
    environments: list[EnvironmentSpec] = []
    if isinstance(node, dict):
        iterable = node.items()
    elif isinstance(node, list):
        iterable = ((_environment_name(item, index), item) for index, item in enumerate(node))
    else:
        return environments

    for name, raw in iterable:
        if isinstance(raw, dict):
            env_name = str(raw.get("name", name))
            environments.append(
                EnvironmentSpec(
                    name=env_name,
                    variables=_parse_named_values(raw.get("variables", [])),
                    secrets=_parse_named_values(raw.get("secrets", [])),
                )
            )
        else:
            environments.append(EnvironmentSpec(name=str(name)))
    return environments


def _environment_name(item: Any, index: int) -> str:
    if isinstance(item, dict) and item.get("name"):
        return str(item["name"])
    return f"environment_{index + 1}"


def _parse_repositories(node: Any) -> list[RepositorySpec]:
    repositories: list[RepositorySpec] = []
    if isinstance(node, dict):
        node = [node]
    if not isinstance(node, list):
        return repositories

    for raw in node:
        if isinstance(raw, str):
            repositories.append(_repo_from_string(raw))
            continue
        if not isinstance(raw, dict):
            continue

        repo = str(raw.get("repo", raw.get("full_name", "")) or "")
        owner = str(raw.get("owner", "") or "")
        name = str(raw.get("name", "") or "")
        url = str(raw.get("url", raw.get("clone_url", "")) or "")

        if repo and "/" in repo and (not owner or not name):
            owner, name = repo.split("/", 1)
        if url and (not owner or not name):
            parsed = parse_github_url(url)
            if parsed:
                owner, name = parsed

        repositories.append(
            RepositorySpec(
                owner=owner,
                name=name,
                url=url,
                template=str(raw.get("template", "") or ""),
                branch=str(raw.get("branch", raw.get("branch_name", "")) or ""),
                base=str(raw.get("base", raw.get("default_branch", "")) or ""),
                default_branch=str(raw.get("default_branch", "") or ""),
                folders=_parse_repository_folders(
                    raw.get(
                        "folders",
                        raw.get(
                            "extra_folders",
                            raw.get(
                                "template_folders",
                                raw.get("source_folders", raw.get("sources", [])),
                            ),
                        ),
                    )
                ),
                variables=_parse_named_values(raw.get("repo_variables", raw.get("variables", []))),
                secrets=_parse_named_values(raw.get("repo_secrets", raw.get("secrets", []))),
                environments=_parse_environments(raw.get("environments", [])),
            )
        )
    return repositories


def _parse_repository_folders(node: Any) -> list[RepositoryFolderSpec]:
    folders: list[RepositoryFolderSpec] = []
    if isinstance(node, str):
        node = [node]
    elif isinstance(node, dict):
        keys = {"source", "path", "folder", "from"}
        if keys.intersection(node):
            node = [node]
        else:
            node = [{"source": source, "target": target} for source, target in node.items()]
    if not isinstance(node, list):
        return folders

    for raw in node:
        if isinstance(raw, str):
            folders.append(RepositoryFolderSpec(source=raw))
            continue
        if not isinstance(raw, dict):
            continue
        source = raw.get("source", raw.get("path", raw.get("folder", raw.get("from", ""))))
        target = raw.get(
            "target",
            raw.get(
                "destination",
                raw.get("dest", raw.get("repository_path", raw.get("repo_path", raw.get("to", "")))),
            ),
        )
        folders.append(
            RepositoryFolderSpec(
                source=str(source or ""),
                target=str(target or ""),
            )
        )
    return folders


def _parse_settings(node: Any) -> tuple[list[NamedValue], list[NamedValue], list[EnvironmentSpec]]:
    repo_variables: list[NamedValue] = []
    repo_secrets: list[NamedValue] = []
    environments_by_name: dict[str, EnvironmentSpec] = {}

    if isinstance(node, dict):
        node = [node]
    if not isinstance(node, list):
        return repo_variables, repo_secrets, []

    for index, raw in enumerate(node):
        if not isinstance(raw, dict):
            continue
        setting_name = str(raw.get("name", raw.get("key", "")) or "")
        if not setting_name:
            raise ValueError(f"settings[{index}] nao possui name.")

        setting_type = str(raw.get("type", raw.get("kind", "variable"))).lower()
        if setting_type in {"var", "variable", "variables"}:
            target = "variable"
        elif setting_type in {"secret", "secrets"}:
            target = "secret"
        else:
            raise ValueError(f"settings[{index}] possui type invalido: {setting_type}")

        setting = NamedValue(name=setting_name, value=raw.get("value", ""))
        scope = str(raw.get("scope", raw.get("level", "repository"))).lower()
        if scope in {"repo", "repository"}:
            if target == "variable":
                repo_variables.append(setting)
            else:
                repo_secrets.append(setting)
            continue

        if scope not in {"env", "environment"}:
            raise ValueError(f"settings[{index}] possui scope invalido: {scope}")

        env_name = str(raw.get("environment", raw.get("env", raw.get("environment_name", ""))) or "")
        if not env_name:
            raise ValueError(f"settings[{index}] de environment precisa de environment.")
        environment = environments_by_name.setdefault(env_name, EnvironmentSpec(name=env_name))
        if target == "variable":
            environment.variables.append(setting)
        else:
            environment.secrets.append(setting)

    return repo_variables, repo_secrets, list(environments_by_name.values())


def _merge_environments(environments: list[EnvironmentSpec]) -> list[EnvironmentSpec]:
    merged: dict[str, EnvironmentSpec] = {}
    for environment in environments:
        target = merged.setdefault(environment.name, EnvironmentSpec(name=environment.name))
        target.variables.extend(environment.variables)
        target.secrets.extend(environment.secrets)
    return list(merged.values())


def _repo_from_string(value: str) -> RepositorySpec:
    if "/" in value and not value.startswith(("http://", "https://", "git@")):
        owner, name = value.split("/", 1)
        return RepositorySpec(owner=owner, name=name)

    parsed = parse_github_url(value)
    if parsed:
        owner, name = parsed
        return RepositorySpec(owner=owner, name=name, url=value)

    return RepositorySpec(name=value)


def parse_github_url(url: str) -> tuple[str, str] | None:
    patterns = (
        r"github\.com[:/](?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?/?$",
        r"github\.com/(?P<owner>[^/]+)/(?P<name>[^/]+?)(?:\.git)?/?$",
    )
    for pattern in patterns:
        match = re.search(pattern, url)
        if match:
            return match.group("owner"), match.group("name")
    return None
