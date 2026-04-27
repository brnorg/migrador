from __future__ import annotations

import argparse
from dataclasses import dataclass
import json
from pathlib import Path
import sys
import tempfile
from typing import Any

from jinja2 import UndefinedError
from rich.console import Console
from rich.panel import Panel
from rich.progress import BarColumn, Progress, SpinnerColumn, TaskProgressColumn, TextColumn, TimeElapsedColumn
from rich.prompt import Confirm, Prompt
from rich.table import Table

from . import __version__, gh_cli, git_ops
from .config import (
    ControlConfig,
    FieldSpec,
    NamedValue,
    RepositorySpec,
    environment_for_repository,
    is_blank,
    load_config,
    named_value_for_repository,
    parse_github_url,
    value_for_repository,
)
from .github_api import GitHubClient
from .render import render_string, render_template_files, render_template_tree


console = Console()


@dataclass
class RepoRun:
    repo_index: int
    repo_count: int
    repo: RepositorySpec
    template_name: str
    template_dir: Path
    clone_url: str
    branch: str
    base: str
    commit_message: str
    pr_title: str
    pr_body: str
    context: dict[str, object]


@dataclass
class RepoResult:
    full_name: str
    branch: str
    pr_url: str = ""
    pr_existed: bool = False
    committed: bool = False
    variables_set: int = 0
    secrets_set: int = 0
    skipped_blank: int = 0


@dataclass
class CheckItem:
    status: str
    name: str
    detail: str


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if not hasattr(args, "handler"):
        parser.print_help()
        return 1

    try:
        return int(args.handler(args) or 0)
    except KeyboardInterrupt:
        console.print("\n[red]Execucao interrompida pelo usuario.[/red]")
        return 130
    except Exception as exc:
        console.print(f"[red]Erro:[/red] {exc}")
        return 1


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="repo-template",
        description="Aplica templates Jinja em repositorios GitHub e configura vars/secrets.",
    )
    parser.add_argument("--version", action="version", version=f"%(prog)s {__version__}")

    subparsers = parser.add_subparsers(dest="command")

    run_parser = subparsers.add_parser("run", help="Executa o fluxo completo.")
    run_parser.add_argument("-c", "--config", default="control.json", help="Arquivo JSON de controle.")
    run_parser.add_argument("--yes", action="store_true", help="Nao pedir confirmacao depois da revisao.")
    run_parser.add_argument("--dry-run", action="store_true", help="Mostra a revisao, mas nao altera repositorios.")
    run_parser.add_argument("--check", action="store_true", help="Executa o teste de setup antes de aplicar.")
    run_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Falha se algum valor obrigatorio precisar ser perguntado.",
    )
    run_parser.set_defaults(handler=cmd_run)

    validate_parser = subparsers.add_parser("validate", help="Valida o arquivo de controle.")
    validate_parser.add_argument("-c", "--config", default="control.json", help="Arquivo JSON de controle.")
    validate_parser.set_defaults(handler=cmd_validate)

    check_parser = subparsers.add_parser("check", help="Testa o setup sem alterar repositorios.")
    check_parser.add_argument("-c", "--config", default="control.json", help="Arquivo JSON de controle.")
    check_parser.add_argument(
        "--local",
        action="store_true",
        help="Nao consulta GitHub/remotes; valida apenas JSON, templates e Jinja.",
    )
    check_parser.add_argument(
        "--non-interactive",
        action="store_true",
        help="Falha se algum valor obrigatorio precisar ser perguntado.",
    )
    check_parser.set_defaults(handler=cmd_check)

    init_parser = subparsers.add_parser("init", help="Cria um exemplo de arquivo de controle.")
    init_parser.add_argument("-p", "--path", default="control.json", help="Destino do exemplo.")
    init_parser.add_argument("--force", action="store_true", help="Sobrescreve o arquivo se ele ja existir.")
    init_parser.set_defaults(handler=cmd_init)

    ui_parser = subparsers.add_parser("ui", help="Abre a interface web local.")
    ui_parser.add_argument("-c", "--config", default="control.json", help="Arquivo JSON de controle.")
    ui_parser.add_argument("--host", default="127.0.0.1", help="Host local da interface.")
    ui_parser.add_argument("--port", type=int, default=8765, help="Porta local da interface.")
    ui_parser.add_argument("--no-open", action="store_true", help="Nao abrir o navegador automaticamente.")
    ui_parser.set_defaults(handler=cmd_ui)

    return parser


def cmd_init(args: argparse.Namespace) -> int:
    target = Path(args.path).expanduser().resolve()
    if target.exists() and not args.force:
        raise RuntimeError(f"{target} ja existe. Use --force para sobrescrever.")
    target.write_text(json.dumps(example_config(), indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    console.print(f"Arquivo criado: [bold]{target}[/bold]")
    return 0


def cmd_ui(args: argparse.Namespace) -> int:
    from .web import serve

    return serve(
        config_path=args.config,
        host=args.host,
        port=args.port,
        open_browser=not args.no_open,
    )


def cmd_validate(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    problems = validate_static_config(config)
    if problems:
        for problem in problems:
            console.print(f"[red]-[/red] {problem}")
        return 1
    console.print("[green]Configuracao valida.[/green]")
    return 0


def cmd_check(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    problems = validate_static_config(config)
    if problems:
        print_check_results([CheckItem("FAIL", "JSON/config", "\n".join(problems))])
        return 1

    field_values = collect_field_values(config.fields, len(config.repositories), args.non_interactive)
    runs = resolve_runs(config, field_values, non_interactive=args.non_interactive)
    ok = run_setup_check(config, runs, remote=not args.local)
    return 0 if ok else 1


def cmd_run(args: argparse.Namespace) -> int:
    config = load_config(Path(args.config))
    problems = validate_static_config(config)
    if problems:
        for problem in problems:
            console.print(f"[red]-[/red] {problem}")
        return 1

    field_values = collect_field_values(config.fields, len(config.repositories), args.non_interactive)
    runs = resolve_runs(config, field_values, non_interactive=args.non_interactive)
    print_review(config, runs)

    should_check = args.check
    if not should_check and not args.yes and not args.dry_run:
        should_check = Confirm.ask("Testar setup antes de executar?", default=True)
    if should_check and not args.dry_run:
        if not run_setup_check(config, runs, remote=True):
            return 1

    if not args.yes:
        if not Confirm.ask("Executar este plano?", default=False):
            console.print("Execucao cancelada.")
            return 0

    if args.dry_run:
        console.print("[yellow]Dry-run: nenhuma alteracao foi feita.[/yellow]")
        return 0

    if config.apply_mode == "git":
        git_ops.require_command("git")
    if config_has_settings(config, runs):
        git_ops.require_command("gh")
    client = GitHubClient.from_environment_or_gh()

    results = execute_runs(config, runs, client)
    print_results(results)
    return 0


def validate_static_config(config: ControlConfig) -> list[str]:
    problems: list[str] = []
    if config.apply_mode not in {"api", "git"}:
        problems.append("apply_mode deve ser 'api' ou 'git'.")
    if not config.templates_root.exists():
        problems.append(f"templates_root nao existe: {config.templates_root}")
    elif not config.templates_root.is_dir():
        problems.append(f"templates_root nao e uma pasta: {config.templates_root}")
    return problems


def collect_field_values(
    fields: list[FieldSpec],
    repo_count: int,
    non_interactive: bool,
) -> dict[str, object]:
    raw: dict[str, object] = {}

    for field in fields:
        if isinstance(field.value, list):
            if field.value:
                value_for_repository(field.value, 0, repo_count, field.name)
            raw[field.name] = field.value
        elif is_blank(field.value):
            raw[field.name] = prompt_field(field, non_interactive)
        else:
            raw[field.name] = field.value
    return raw


def build_context_for_repo(
    fields: list[FieldSpec],
    raw_values: dict[str, object],
    repo: RepositorySpec,
    repo_index: int,
    repo_count: int,
    non_interactive: bool,
) -> dict[str, object]:
    context = context_for_repo({}, repo)

    for field in fields:
        raw_value = raw_values[field.name]
        ask_per_repo = isinstance(raw_value, list) and not raw_value
        value = "" if ask_per_repo else value_for_repository(raw_value, repo_index, repo_count, field.name)
        if ask_per_repo or is_blank(value):
            value = prompt_field_for_repo(field, repo.full_name, non_interactive)
        context[field.name] = value

    for _ in range(3):
        changed = False
        for field in fields:
            value = context[field.name]
            if not field.render or not isinstance(value, str):
                continue
            try:
                rendered = render_string(value, context)
            except UndefinedError as exc:
                raise RuntimeError(f"Campo {field.name} referencia uma chave inexistente: {exc}") from exc
            if context.get(field.name) != rendered:
                context[field.name] = rendered
                changed = True
        if not changed:
            break
    return context


def prompt_field(field: FieldSpec, non_interactive: bool) -> str:
    if non_interactive:
        if field.required:
            raise RuntimeError(f"Campo obrigatorio sem valor no JSON: {field.name}")
        return ""

    while True:
        if field.required:
            value = Prompt.ask(field.label, password=field.secret)
        else:
            value = Prompt.ask(field.label, password=field.secret, default="")
        if value or not field.required:
            return value
        console.print("[yellow]Valor obrigatorio.[/yellow]")


def prompt_field_for_repo(field: FieldSpec, full_name: str, non_interactive: bool) -> str:
    if non_interactive:
        if field.required:
            raise RuntimeError(f"Campo obrigatorio sem valor no JSON: {field.name}")
        return ""

    label = f"{field.label} ({full_name})"
    while True:
        if field.required:
            value = Prompt.ask(label, password=field.secret)
        else:
            value = Prompt.ask(label, password=field.secret, default="")
        if value or not field.required:
            return value
        console.print("[yellow]Valor obrigatorio.[/yellow]")


def resolve_runs(
    config: ControlConfig,
    field_values: dict[str, object],
    non_interactive: bool,
) -> list[RepoRun]:
    runs: list[RepoRun] = []
    repo_count = len(config.repositories)
    for index, repo in enumerate(config.repositories):
        repo = resolve_repository_identity(repo, index + 1, non_interactive)
        field_context = build_context_for_repo(
            config.fields,
            field_values,
            repo,
            index,
            repo_count,
            non_interactive,
        )
        template_name = resolve_text(
            repo.template or config.template,
            field_context,
            prompt=f"Template para {repo.full_name}",
            non_interactive=non_interactive,
            required=True,
        )
        template_dir = (config.templates_root / template_name).resolve()
        if not template_dir.exists():
            raise RuntimeError(f"Template nao encontrado para {repo.full_name}: {template_dir}")

        branch_context = dict(field_context)
        branch_context["template"] = template_name
        branch = resolve_text(
            repo.branch or config.branch,
            branch_context,
            prompt=f"Branch de trabalho para {repo.full_name}",
            non_interactive=non_interactive,
            required=True,
        )

        run_context = dict(field_context)
        run_context.update({"template": template_name, "branch": branch})

        base = render_optional(repo.base or config.pull_request.base, run_context)
        commit_message = render_string(config.commit_message, run_context)
        pr_title = render_string(config.pull_request.title, run_context)
        pr_body = render_string(config.pull_request.body, run_context)

        runs.append(
            RepoRun(
                repo_index=index,
                repo_count=repo_count,
                repo=repo,
                template_name=template_name,
                template_dir=template_dir,
                clone_url=repo.url or f"https://github.com/{repo.full_name}.git",
                branch=branch,
                base=base,
                commit_message=commit_message,
                pr_title=pr_title,
                pr_body=pr_body,
                context=run_context,
            )
        )
    return runs


def resolve_repository_identity(
    repo: RepositorySpec,
    index: int,
    non_interactive: bool,
) -> RepositorySpec:
    if repo.url and (not repo.owner or not repo.name):
        parsed = parse_github_url(repo.url)
        if parsed:
            repo.owner, repo.name = parsed

    if not repo.owner or not repo.name:
        full_name = prompt_required(
            f"Repositorio #{index} (owner/name)",
            non_interactive=non_interactive,
            missing_label="repositorio sem owner/name",
        )
        if "/" not in full_name:
            raise RuntimeError(f"Repositorio invalido: {full_name}. Use owner/name.")
        repo.owner, repo.name = full_name.split("/", 1)

    if not repo.url:
        repo.url = f"https://github.com/{repo.full_name}.git"
    return repo


def prompt_required(prompt: str, non_interactive: bool, missing_label: str) -> str:
    if non_interactive:
        raise RuntimeError(f"Valor obrigatorio ausente: {missing_label}")
    while True:
        value = Prompt.ask(prompt)
        if value:
            return value
        console.print("[yellow]Valor obrigatorio.[/yellow]")


def resolve_text(
    value: str,
    context: dict[str, object],
    prompt: str,
    non_interactive: bool,
    required: bool,
) -> str:
    if is_blank(value):
        if non_interactive:
            if required:
                raise RuntimeError(f"Valor obrigatorio ausente: {prompt}")
            return ""
        if required:
            while True:
                answer = Prompt.ask(prompt)
                if answer:
                    return answer
                console.print("[yellow]Valor obrigatorio.[/yellow]")
        return Prompt.ask(prompt, default="")
    return render_string(str(value), context)


def render_optional(value: str, context: dict[str, object]) -> str:
    if is_blank(value):
        return ""
    return render_string(str(value), context)


def context_for_repo(context: dict[str, object], repo: RepositorySpec) -> dict[str, object]:
    repo_context = dict(context)
    repo_context.update(
        {
            "owner": repo.owner,
            "repository": repo.name,
            "repo": repo.name,
            "full_name": repo.full_name,
        }
    )
    return repo_context


def print_review(config: ControlConfig, runs: list[RepoRun]) -> None:
    console.print(
        Panel.fit(
            f"Revise o plano antes de executar. Templates nunca sao alterados. Modo de envio: {config.apply_mode}.",
            title="Revisao",
        )
    )

    repo_table = Table(title="Repositorios")
    repo_table.add_column("Repositorio")
    repo_table.add_column("Template")
    repo_table.add_column("Overlay")
    repo_table.add_column("Branch")
    repo_table.add_column("Base do PR")
    repo_table.add_column("PR")
    for run in runs:
        repo_table.add_row(
            run.repo.full_name,
            run.template_name,
            str(len(existing_repo_overlay_dirs(run))),
            run.branch,
            run.base or "branch padrao via API",
            run.pr_title,
        )
    console.print(repo_table)

    if config.fields:
        field_table = Table(title="Campos Jinja")
        field_table.add_column("Repositorio")
        field_table.add_column("Chave")
        field_table.add_column("Valor")
        secret_names = {field.name for field in config.fields if field.secret}
        for run in runs:
            for field in config.fields:
                value = run.context.get(field.name, "")
                display = "***" if field.name in secret_names else str(value)
                field_table.add_row(run.repo.full_name, field.name, display)
        console.print(field_table)

    settings_table = Table(title="GitHub vars/secrets")
    settings_table.add_column("Escopo")
    settings_table.add_column("Vars")
    settings_table.add_column("Secrets")
    settings_table.add_column("Em branco")
    for run in runs:
        variables = selected_named_values([*config.repo_variables, *run.repo.variables], run)
        secrets = selected_named_values([*config.repo_secrets, *run.repo.secrets], run)
        environments = selected_environments([*config.environments, *run.repo.environments], run)
        env_vars = sum(count_non_blank(env.variables) for env in environments)
        env_secrets = sum(count_non_blank(env.secrets) for env in environments)
        blanks = count_blanks(variables) + count_blanks(secrets)
        blanks += sum(count_blanks(env.variables) + count_blanks(env.secrets) for env in environments)
        settings_table.add_row(
            run.repo.full_name,
            str(count_non_blank(variables) + env_vars),
            str(count_non_blank(secrets) + env_secrets),
            f"{blanks} ignorado(s)",
        )
    console.print(settings_table)


def count_blanks(values: list[NamedValue]) -> int:
    return sum(1 for value in values if value.is_blank)


def count_non_blank(values: list[NamedValue]) -> int:
    return sum(1 for value in values if not value.is_blank)


def selected_named_values(values: list[NamedValue], run: RepoRun) -> list[NamedValue]:
    return [
        named_value_for_repository(value, run.repo_index, run.repo_count)
        for value in values
    ]


def selected_environments(environments: list, run: RepoRun) -> list:
    return [
        environment_for_repository(environment, run.repo_index, run.repo_count)
        for environment in environments
    ]


def run_setup_check(config: ControlConfig, runs: list[RepoRun], remote: bool) -> bool:
    items: list[CheckItem] = []
    overlays = all_repo_overlay_names(runs)
    add_check_item(
        items,
        "OK" if config.templates_root.is_dir() else "FAIL",
        "Pasta de templates",
        str(config.templates_root),
    )

    for run in runs:
        check_template_render(config, run, items, overlays)
        check_rendered_text(run, items)
        check_settings_render(config, run, items)

    if remote:
        check_remote_setup(runs, config, items)
    else:
        add_check_item(items, "WARN", "GitHub/remotes", "Validacao remota ignorada por --local.")

    print_check_results(items)
    return not any(item.status == "FAIL" for item in items)


def check_template_render(
    config: ControlConfig,
    run: RepoRun,
    items: list[CheckItem],
    all_overlays: set[str],
) -> None:
    files = [path for path in run.template_dir.rglob("*") if path.is_file()]
    overlays = existing_repo_overlay_dirs(run)
    add_check_item(
        items,
        "OK" if files else "WARN",
        f"{run.repo.full_name}: template",
        f"{run.template_dir} ({len(files)} arquivo(s), {len(overlays)} overlay(s) do repo)",
    )
    try:
        api_files = render_template_files(
            run.template_dir,
            run.context,
            config.exclude,
            repo_overlay_names=repo_overlay_names(run),
            all_repo_overlay_names=all_overlays,
        )
        with tempfile.TemporaryDirectory(prefix="repo-template-check-") as tmp_dir:
            written = render_template_tree(
                run.template_dir,
                Path(tmp_dir),
                run.context,
                config.exclude,
                repo_overlay_names=repo_overlay_names(run),
                all_repo_overlay_names=all_overlays,
            )
    except Exception as exc:
        add_check_item(items, "FAIL", f"{run.repo.full_name}: renderizacao", str(exc))
        return

    add_check_item(
        items,
        "OK",
        f"{run.repo.full_name}: renderizacao",
        f"{len(written)} arquivo(s) em disco e {len(api_files)} arquivo(s) prontos para API.",
    )


def check_rendered_text(run: RepoRun, items: list[CheckItem]) -> None:
    values = {
        "branch": run.branch,
        "commit_message": run.commit_message,
        "pull_request.title": run.pr_title,
        "pull_request.body": run.pr_body,
    }
    for name, value in values.items():
        if is_blank(value):
            add_check_item(items, "FAIL", f"{run.repo.full_name}: {name}", "Valor vazio.")
        else:
            add_check_item(items, "OK", f"{run.repo.full_name}: {name}", str(value))


def check_settings_render(config: ControlConfig, run: RepoRun, items: list[CheckItem]) -> None:
    try:
        variables = selected_named_values([*config.repo_variables, *run.repo.variables], run)
        secrets = selected_named_values([*config.repo_secrets, *run.repo.secrets], run)
        environments = selected_environments([*config.environments, *run.repo.environments], run)
        for value in [*variables, *secrets]:
            render_named_setting(value, run)
        for environment in environments:
            for value in [*environment.variables, *environment.secrets]:
                render_named_setting(value, run)
    except Exception as exc:
        add_check_item(items, "FAIL", f"{run.repo.full_name}: vars/secrets", str(exc))
        return

    blanks = count_blanks(variables) + count_blanks(secrets)
    blanks += sum(count_blanks(env.variables) + count_blanks(env.secrets) for env in environments)
    total = len(variables) + len(secrets) + sum(
        len(env.variables) + len(env.secrets) for env in environments
    )
    add_check_item(
        items,
        "OK",
        f"{run.repo.full_name}: vars/secrets",
        f"{total - blanks} item(ns) aplicavel(is), {blanks} em branco ignorado(s).",
    )


def render_named_setting(value: NamedValue, run: RepoRun) -> None:
    if is_blank(value.value):
        return
    if isinstance(value.value, str):
        render_string(value.value, run.context)


def check_remote_setup(runs: list[RepoRun], config: ControlConfig, items: list[CheckItem]) -> None:
    commands_ok = True
    commands = []
    if config.apply_mode == "git":
        commands.append("git")
    if config_has_settings(config, runs):
        commands.append("gh")

    for command in commands:
        try:
            git_ops.require_command(command)
        except Exception as exc:
            add_check_item(items, "FAIL", f"Comando {command}", str(exc))
            commands_ok = False
        else:
            add_check_item(items, "OK", f"Comando {command}", "Disponivel no PATH.")

    if not commands_ok:
        return

    try:
        client = GitHubClient.from_environment_or_gh()
    except Exception as exc:
        add_check_item(items, "FAIL", "Autenticacao GitHub", str(exc))
        return
    add_check_item(items, "OK", "Autenticacao GitHub", "Token encontrado via env ou GitHub CLI.")

    for run in runs:
        try:
            repo_data = client.repository(run.repo.owner, run.repo.name)
        except Exception as exc:
            add_check_item(items, "FAIL", f"{run.repo.full_name}: API", str(exc))
            continue

        permissions = repo_data.get("permissions") or {}
        can_push = bool(
            permissions.get("push") or permissions.get("maintain") or permissions.get("admin")
        )
        add_check_item(
            items,
            "OK" if can_push else "FAIL",
            f"{run.repo.full_name}: permissao de push",
            "Permissao suficiente." if can_push else "Token atual nao informa permissao de push.",
        )

        if has_settings(config, run) and not (permissions.get("maintain") or permissions.get("admin")):
            add_check_item(
                items,
                "WARN",
                f"{run.repo.full_name}: secrets/variables",
                "O setup nao consegue garantir permissao de escrita em vars/secrets sem alterar o repositorio.",
            )

        base = run.base or str(repo_data["default_branch"])
        if config.apply_mode == "git":
            try:
                exists = git_ops.remote_head_exists_url(run.clone_url, base)
            except Exception as exc:
                add_check_item(items, "FAIL", f"{run.repo.full_name}: git remoto", str(exc))
                continue
            detail = f"{base} encontrada via git ls-remote."
            fail_detail = f"{base} nao encontrada via git ls-remote."
        else:
            exists = client.get_ref(run.repo.owner, run.repo.name, f"heads/{base}") is not None
            detail = f"{base} encontrada via API."
            fail_detail = f"{base} nao encontrada via API."
        add_check_item(
            items,
            "OK" if exists else "FAIL",
            f"{run.repo.full_name}: branch base",
            detail if exists else fail_detail,
        )


def has_settings(config: ControlConfig, run: RepoRun) -> bool:
    return bool(
        config.repo_variables
        or config.repo_secrets
        or config.environments
        or run.repo.variables
        or run.repo.secrets
        or run.repo.environments
    )


def config_has_settings(config: ControlConfig, runs: list[RepoRun]) -> bool:
    return any(has_settings(config, run) for run in runs)


def repo_overlay_names(run: RepoRun) -> list[str]:
    candidates = [
        run.repo.name,
        run.repo.full_name.replace("/", "__"),
        run.repo.full_name.replace("/", "--"),
        run.repo.full_name.replace("/", "_"),
    ]
    names: list[str] = []
    for candidate in candidates:
        if candidate and candidate not in names:
            names.append(candidate)
    return names


def all_repo_overlay_names(runs: list[RepoRun]) -> set[str]:
    names: set[str] = set()
    for run in runs:
        names.update(repo_overlay_names(run))
    return names


def existing_repo_overlay_dirs(run: RepoRun) -> list[Path]:
    dirs: list[Path] = []
    seen: set[Path] = set()
    for name in repo_overlay_names(run):
        candidates = [run.template_dir / name]
        for repo_root in ("_repo", "_repos"):
            candidates.append(run.template_dir / repo_root / name)
            candidates.append(run.template_dir / repo_root / "orgs" / run.repo.owner / run.repo.name)
        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate.is_dir() and candidate not in seen:
                dirs.append(candidate)
                seen.add(candidate)
    return dirs


def add_check_item(items: list[CheckItem], status: str, name: str, detail: str) -> None:
    items.append(CheckItem(status=status, name=name, detail=detail))


def print_check_results(items: list[CheckItem]) -> None:
    table = Table(title="Setup check")
    table.add_column("Status")
    table.add_column("Verificacao")
    table.add_column("Detalhe")
    for item in items:
        style = {"OK": "green", "WARN": "yellow", "FAIL": "red"}.get(item.status, "white")
        table.add_row(f"[{style}]{item.status}[/{style}]", item.name, item.detail)
    console.print(table)


def execute_runs(config: ControlConfig, runs: list[RepoRun], client: GitHubClient) -> list[RepoResult]:
    if config.apply_mode == "git":
        return execute_runs_git(config, runs, client)
    return execute_runs_api(config, runs, client)


def execute_runs_api(config: ControlConfig, runs: list[RepoRun], client: GitHubClient) -> list[RepoResult]:
    results: list[RepoResult] = []
    total_steps = 5
    overlays = all_repo_overlay_names(runs)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        for run in runs:
            task = progress.add_task(f"{run.repo.full_name}: preparando", total=total_steps)
            base = run.base or client.default_branch(run.repo.owner, run.repo.name)
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: renderizando")
            files = render_template_files(
                run.template_dir,
                run.context,
                config.exclude,
                repo_overlay_names=repo_overlay_names(run),
                all_repo_overlay_names=overlays,
            )
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: commit via API")
            api_commit = client.apply_files_commit(
                run.repo.owner,
                run.repo.name,
                run.branch,
                base,
                run.commit_message,
                files,
            )
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: pull request")
            pr = None
            if api_commit.changed or api_commit.branch_existed:
                pr = client.create_or_get_pull_request(
                    run.repo.owner,
                    run.repo.name,
                    run.branch,
                    base,
                    run.pr_title,
                    run.pr_body,
                )
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: vars/secrets")
            gh_summary = gh_cli.apply_repository_settings(
                run.repo,
                run.context,
                config.repo_variables,
                config.repo_secrets,
                config.environments,
                run.repo_index,
                run.repo_count,
            )
            progress.advance(task)
            progress.update(task, description=f"{run.repo.full_name}: concluido")

            results.append(
                RepoResult(
                    full_name=run.repo.full_name,
                    branch=run.branch,
                    pr_url=pr.url if pr else "sem mudancas",
                    pr_existed=pr.existed if pr else False,
                    committed=api_commit.changed,
                    variables_set=gh_summary.variables_set,
                    secrets_set=gh_summary.secrets_set,
                    skipped_blank=len(gh_summary.blank_skipped or []),
                )
            )
    return results


def execute_runs_git(config: ControlConfig, runs: list[RepoRun], client: GitHubClient) -> list[RepoResult]:
    results: list[RepoResult] = []
    total_steps = 7
    overlays = all_repo_overlay_names(runs)
    with Progress(
        SpinnerColumn(),
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        TaskProgressColumn(),
        TimeElapsedColumn(),
        console=console,
    ) as progress:
        for run in runs:
            task = progress.add_task(f"{run.repo.full_name}: preparando", total=total_steps)
            base = run.base or client.default_branch(run.repo.owner, run.repo.name)
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: clonando")
            clone = git_ops.prepare_clone(
                config.workspace,
                run.repo.owner,
                run.repo.name,
                run.clone_url,
                run.branch,
                base,
            )
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: renderizando")
            render_template_tree(
                run.template_dir,
                clone.path,
                run.context,
                config.exclude,
                repo_overlay_names=repo_overlay_names(run),
                all_repo_overlay_names=overlays,
            )
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: commit")
            committed = git_ops.commit_all(clone.path, run.commit_message)
            progress.advance(task)

            if committed:
                progress.update(task, description=f"{run.repo.full_name}: push")
                git_ops.push_branch(clone.path, run.branch)
            elif clone.branch_existed:
                progress.update(task, description=f"{run.repo.full_name}: branch existente sem mudancas")
            else:
                progress.update(task, description=f"{run.repo.full_name}: sem mudancas para PR")
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: pull request")
            pr = None
            if committed or clone.branch_existed:
                pr = client.create_or_get_pull_request(
                    run.repo.owner,
                    run.repo.name,
                    run.branch,
                    base,
                    run.pr_title,
                    run.pr_body,
                )
            progress.advance(task)

            progress.update(task, description=f"{run.repo.full_name}: vars/secrets")
            gh_summary = gh_cli.apply_repository_settings(
                run.repo,
                run.context,
                config.repo_variables,
                config.repo_secrets,
                config.environments,
                run.repo_index,
                run.repo_count,
            )
            progress.advance(task)
            progress.update(task, description=f"{run.repo.full_name}: concluido")

            results.append(
                RepoResult(
                    full_name=run.repo.full_name,
                    branch=run.branch,
                    pr_url=pr.url if pr else "sem mudancas",
                    pr_existed=pr.existed if pr else False,
                    committed=committed,
                    variables_set=gh_summary.variables_set,
                    secrets_set=gh_summary.secrets_set,
                    skipped_blank=len(gh_summary.blank_skipped or []),
                )
            )
    return results


def print_results(results: list[RepoResult]) -> None:
    table = Table(title="Resultado")
    table.add_column("Repositorio")
    table.add_column("Branch")
    table.add_column("PR")
    table.add_column("Commit")
    table.add_column("Vars")
    table.add_column("Secrets")
    table.add_column("Ignorados")
    for result in results:
        table.add_row(
            result.full_name,
            result.branch,
            result.pr_url,
            "sim" if result.committed else "sem mudancas",
            str(result.variables_set),
            str(result.secrets_set),
            str(result.skipped_blank),
        )
    console.print(table)


def example_config() -> dict[str, Any]:
    return {
        "templates_root": "./examples/templates",
        "workspace": "./.repo-template-workspace",
        "apply_mode": "api",
        "template": "java",
        "branch": "chore/bootstrap-{{ project_name | slugify }}",
        "commit_message": "Bootstrap {{ project_name }}",
        "pull_request": {
            "title": "Bootstrap {{ project_name }}",
            "body": "Aplica o template {{ template }} para {{ project_name }}.",
            "base": "",
        },
        "repositories": [
            "sua-org/repo-a",
            "sua-org/repo-b",
        ],
        "values": [
            {
                "name": "project_name",
                "label": "Nome do projeto",
                "value": ["Servico A", "Servico B"],
            },
            {
                "name": "package_name",
                "label": "Package/base namespace",
                "value": "com.example.{{ project_name | slugify | replace('-', '.') }}",
            },
            {
                "name": "runtime_version",
                "label": "Versao da runtime",
                "value": "21",
            },
        ],
        "settings": [
            {
                "scope": "repository",
                "type": "variable",
                "name": "APP_NAME",
                "value": "{{ project_name | slugify }}",
            },
            {
                "scope": "repository",
                "type": "secret",
                "name": "TOKEN_EXEMPLO",
                "value": "",
            },
            {
                "scope": "environment",
                "environment": "dev",
                "type": "variable",
                "name": "JAVA_VERSION",
                "value": "{{ runtime_version }}",
            },
            {
                "scope": "environment",
                "environment": "dev",
                "type": "secret",
                "name": "DEV_TOKEN",
                "value": "",
            },
        ],
        "exclude": [".git/**", "**/.DS_Store"],
    }


if __name__ == "__main__":
    sys.exit(main())
