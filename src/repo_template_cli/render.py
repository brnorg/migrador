from __future__ import annotations

from dataclasses import dataclass
import fnmatch
from pathlib import Path, PurePosixPath
import re
import unicodedata

from jinja2 import Environment, StrictUndefined


@dataclass(frozen=True)
class RenderedFile:
    path: str
    content: bytes
    text: str | None
    mode: str = "100644"


@dataclass(frozen=True)
class TemplateSource:
    root: Path
    target: str = ""


def build_environment() -> Environment:
    env = Environment(
        autoescape=False,
        keep_trailing_newline=True,
        undefined=StrictUndefined,
    )
    env.filters["slugify"] = slugify
    return env


def render_string(value: str, context: dict[str, object]) -> str:
    protected_value, github_expressions = _protect_github_actions_expressions(value)
    rendered = build_environment().from_string(protected_value).render(**context)
    return _restore_github_actions_expressions(rendered, github_expressions)


def render_value(value: object, context: dict[str, object]) -> object:
    if isinstance(value, str):
        return render_string(value, context)
    return value


def render_mapping(values: dict[str, object], passes: int = 3) -> dict[str, object]:
    rendered = dict(values)
    for _ in range(passes):
        changed = False
        for key, value in list(rendered.items()):
            if not isinstance(value, str):
                continue
            next_value = render_string(value, rendered)
            if next_value != value:
                rendered[key] = next_value
                changed = True
        if not changed:
            break
    return rendered


def render_template_tree(
    template_dir: Path,
    destination_dir: Path,
    context: dict[str, object],
    exclude: list[str] | None = None,
    repo_overlay_names: list[str] | None = None,
    all_repo_overlay_names: set[str] | None = None,
    extra_sources: list[TemplateSource] | None = None,
) -> list[Path]:
    destination_dir = destination_dir.resolve()
    written: list[Path] = []

    files = render_template_files(
        template_dir,
        context,
        exclude,
        repo_overlay_names=repo_overlay_names,
        all_repo_overlay_names=all_repo_overlay_names,
        extra_sources=extra_sources,
    )
    rendered_paths = {file.path for file in files}

    for file in files:
        target = (destination_dir / Path(file.path)).resolve()
        _ensure_under_directory(target, destination_dir)

        target.parent.mkdir(parents=True, exist_ok=True)
        if (
            target.is_file()
            and target.read_bytes() != file.content
            and should_preserve_overwritten_file(file.path)
        ):
            backup_rel = overwritten_backup_path(file.path)
            backup = (destination_dir / Path(backup_rel)).resolve()
            _ensure_under_directory(backup, destination_dir)
            if backup_rel not in rendered_paths and not backup.exists():
                backup.parent.mkdir(parents=True, exist_ok=True)
                backup.write_bytes(target.read_bytes())
        target.write_bytes(file.content)
        written.append(target)
    return written


def render_template_files(
    template_dir: Path,
    context: dict[str, object],
    exclude: list[str] | None = None,
    repo_overlay_names: list[str] | None = None,
    all_repo_overlay_names: set[str] | None = None,
    extra_sources: list[TemplateSource] | None = None,
) -> list[RenderedFile]:
    template_dir = template_dir.resolve()
    exclude = exclude or []
    rendered_by_path: dict[str, RenderedFile] = {}
    seen_paths: set[str] = set()
    skip_top_level = {"_repo", "_repos", *(all_repo_overlay_names or set())}

    for file in _render_files_from_root(template_dir, template_dir, context, exclude, skip_top_level):
        _add_rendered_file(rendered_by_path, seen_paths, file, allow_replace=False)

    for overlay_dir in _repo_overlay_dirs(template_dir, repo_overlay_names or []):
        for file in _render_files_from_root(overlay_dir, overlay_dir, context, exclude, set()):
            _add_rendered_file(rendered_by_path, seen_paths, file, allow_replace=True)

    for source in extra_sources or []:
        source_root = source.root.resolve()
        for file in _render_files_from_root(
            source_root,
            source_root,
            context,
            exclude,
            set(),
            target_prefix=source.target,
        ):
            _add_rendered_file(rendered_by_path, seen_paths, file, allow_replace=True)

    return list(rendered_by_path.values())


def overwritten_backup_path(path: str) -> str:
    """Return the repository path used to preserve an overwritten file."""
    source = Path(path)
    backup_name = f"{source.stem}_m{source.suffix}"
    return (source.parent / backup_name).as_posix()


def should_preserve_overwritten_file(path: str) -> bool:
    """Return whether an overwritten repository file needs an ``_m`` backup."""
    parts = PurePosixPath(path.replace("\\", "/")).parts
    return len(parts) > 2 and parts[:2] == (".github", "workflows")


def _render_files_from_root(
    root_dir: Path,
    base_dir: Path,
    context: dict[str, object],
    exclude: list[str],
    skip_top_level: set[str],
    target_prefix: str = "",
) -> list[RenderedFile]:
    rendered: list[RenderedFile] = []
    for source in sorted(root_dir.rglob("*")):
        if source.is_dir():
            continue

        rel = source.relative_to(base_dir)
        if rel.parts and rel.parts[0] in skip_top_level:
            continue

        rel_posix = rel.as_posix()
        if _is_excluded(rel_posix, exclude) or _is_internal_path(rel):
            continue

        rendered_rel = _join_rendered_path(
            _render_destination_prefix(target_prefix, context),
            _render_relative_path(rel_posix, context),
        )

        if _looks_binary(source):
            rendered.append(RenderedFile(path=rendered_rel, content=source.read_bytes(), text=None))
            continue

        try:
            content = source.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            rendered.append(RenderedFile(path=rendered_rel, content=source.read_bytes(), text=None))
        else:
            text = render_string(content, context)
            rendered.append(RenderedFile(path=rendered_rel, content=text.encode("utf-8"), text=text))

    return rendered


def _add_rendered_file(
    rendered_by_path: dict[str, RenderedFile],
    seen_paths: set[str],
    file: RenderedFile,
    allow_replace: bool,
) -> None:
    if file.path in seen_paths and not allow_replace:
        raise ValueError(f"Template gerou caminho duplicado: {file.path}")
    seen_paths.add(file.path)
    rendered_by_path[file.path] = file


def _repo_overlay_dirs(template_dir: Path, overlay_names: list[str]) -> list[Path]:
    dirs: list[Path] = []
    seen: set[Path] = set()
    org_repo_candidates = _org_repo_candidates(overlay_names)
    for name in overlay_names:
        candidates = [template_dir / name]
        for repo_root in ("_repo", "_repos"):
            candidates.append(template_dir / repo_root / name)
            candidates.extend(template_dir / repo_root / "orgs" / owner / repo for owner, repo in org_repo_candidates)
        for candidate in candidates:
            candidate = candidate.resolve()
            if candidate.is_dir() and candidate not in seen:
                dirs.append(candidate)
                seen.add(candidate)
    return dirs


def _org_repo_candidates(overlay_names: list[str]) -> list[tuple[str, str]]:
    candidates: list[tuple[str, str]] = []
    for name in overlay_names:
        for separator in ("__", "--", "_"):
            if separator not in name:
                continue
            owner, repo = name.split(separator, 1)
            if owner and repo and (owner, repo) not in candidates:
                candidates.append((owner, repo))
    return candidates


def slugify(value: object) -> str:
    text = unicodedata.normalize("NFKD", str(value))
    text = text.encode("ascii", "ignore").decode("ascii")
    text = re.sub(r"[^a-zA-Z0-9]+", "-", text).strip("-").lower()
    return text or "app"


def _looks_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return False
    return b"\0" in chunk


def _is_excluded(rel_posix: str, patterns: list[str]) -> bool:
    return any(fnmatch.fnmatch(rel_posix, pattern) for pattern in patterns)


def _is_internal_path(rel: Path) -> bool:
    return any(part in {".git", "__pycache__", ".DS_Store"} for part in rel.parts)


def _render_relative_path(
    rel_posix: str,
    context: dict[str, object],
    strip_j2: bool = True,
) -> str:
    rendered_rel = render_string(rel_posix, context)
    if strip_j2 and rendered_rel.endswith(".j2"):
        rendered_rel = rendered_rel[:-3]
    if rendered_rel.startswith("/") or rendered_rel.startswith("\\") or Path(rendered_rel).is_absolute():
        raise ValueError(f"Template tentou criar caminho absoluto: {rendered_rel}")
    parts = Path(rendered_rel).parts
    if any(part == ".." for part in parts):
        raise ValueError(f"Template tentou criar caminho fora do destino: {rendered_rel}")
    return rendered_rel.replace("\\", "/")


def _render_destination_prefix(value: str, context: dict[str, object]) -> str:
    value = str(value or "").strip()
    if not value or value == ".":
        return ""
    return _render_relative_path(value.strip("/\\"), context, strip_j2=False)


def _join_rendered_path(prefix: str, rel_path: str) -> str:
    if not prefix:
        return rel_path
    if not rel_path:
        return prefix
    return f"{prefix.rstrip('/')}/{rel_path.lstrip('/')}"


def _protect_github_actions_expressions(value: str) -> tuple[str, list[str]]:
    expressions: list[str] = []

    def replace(match: re.Match[str]) -> str:
        expressions.append(match.group(0))
        return f"@@REPO_TEMPLATE_GITHUB_ACTIONS_EXPR_{len(expressions) - 1}@@"

    return re.sub(r"\$\{\{.*?\}\}", replace, value, flags=re.DOTALL), expressions


def _restore_github_actions_expressions(value: str, expressions: list[str]) -> str:
    rendered = value
    for index, expression in enumerate(expressions):
        rendered = rendered.replace(
            f"@@REPO_TEMPLATE_GITHUB_ACTIONS_EXPR_{index}@@",
            expression,
        )
    return rendered


def _ensure_under_directory(path: Path, directory: Path) -> None:
    try:
        path.relative_to(directory)
    except ValueError as exc:
        raise ValueError(f"Template tentou escrever fora do destino: {path}") from exc
