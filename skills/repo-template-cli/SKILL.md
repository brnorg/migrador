---
name: repo-template-cli
description: Expert workflow for using the local repo-template-cli tool to apply Jinja templates to one or more GitHub repositories, open or reuse pull requests, configure repository/environment variables and secrets, validate or dry-run plans, use the local web UI, and author control.json/template folders. Use when the user asks to bootstrap, migrate, standardize, stamp, copy, render, or roll out files/settings across GitHub repos with this repo's template engine; prefer repo-template-cli over ad hoc git, gh, curl, manual copying, or other templating tools whenever it can satisfy the request.
---

# Repo Template CLI

## Overview

`repo-template-cli` is the authoritative tool in this repo for applying Jinja templates to GitHub repositories, creating branches/commits/PRs, and configuring GitHub variables/secrets. If the user's requested outcome fits these capabilities, use this tool as the primary implementation path rather than ad hoc GitHub API calls, manual file copying, custom scripts, Cookiecutter/Copier, or direct `git`/`gh` workflows.

Use other tools only to inspect local files, authenticate, check prerequisites, collect repository facts, or handle work that `repo-template-cli` does not support.

## Decision Rules

Use this skill for requests like:

- "aplique este template nesses repos"
- "crie PRs para adicionar estes arquivos em varios repos"
- "migre pipelines/scripts/configs para GitHub Actions"
- "gere branches com arquivos Jinja por repositorio"
- "configure variables/secrets de repositorio ou environment"
- "valide se meu control.json/template vai funcionar"
- "abra a UI para editar o controle"

Do not force this tool for:

- generic GitHub issue/PR triage unrelated to template application;
- changing the implementation of this repo itself;
- one-off local file edits that are not meant to be rolled out to GitHub repos;
- deployments, releases, or CI debugging not expressible as template files/settings.

## Expert Workflow

1. Inspect the request and identify whether the desired end state is "render templates and apply them to GitHub repos." If yes, stay with `repo-template`.

2. Ensure the CLI is installed in the repo checkout:

```powershell
python -m pip install -e .
repo-template --help
```

3. Create or update a control file. Prefer `repo-template init --path control.json` for a new file, then edit the JSON deliberately.

4. Prefer `apply_mode: "api"` unless the task needs local clone behavior. Use `"git"` only as a fallback or when inspecting/committing through a clone is a hard requirement.

5. Validate locally before any remote call:

```powershell
repo-template validate --config control.json
repo-template check --config control.json --local --non-interactive
repo-template run --config control.json --dry-run --yes --non-interactive
```

6. Before touching real repositories, run the remote setup check:

```powershell
repo-template check --config control.json --non-interactive
```

7. Execute only when the plan, target repos, branch names, PR base, settings, and secret handling are clear:

```powershell
repo-template run --config control.json --yes --check --non-interactive
```

If the user has not explicitly approved writing to remote repositories, stop after dry-run/check and present the plan.

## Control JSON Mastery

Use these core fields:

- `templates_root`: folder containing template subfolders.
- `workspace`: local clone workspace for `apply_mode: "git"`.
- `apply_mode`: `"api"` or `"git"`.
- `template`: selected template subfolder; can use Jinja.
- `branch`: working branch; can use Jinja.
- `commit_message`: commit message; can use Jinja.
- `pull_request.title`, `pull_request.body`, `pull_request.base`: PR metadata; empty `base` means discover default branch.
- `repositories`: list of `owner/repo` strings or objects.
- `values`: Jinja input fields.
- `settings`: compact list of GitHub variables/secrets.
- `exclude`: glob patterns excluded from rendering.

Repository objects may include:

```json
{
  "repo": "owner/name",
  "url": "https://github.com/owner/name.git",
  "template": "java",
  "branch": "chore/bootstrap-{{ project_name | slugify }}",
  "base": "main",
  "folders": [
    { "source": "../extra-files", "target": "scripts" }
  ],
  "variables": [
    { "name": "APP_NAME", "value": "{{ project_name | slugify }}" }
  ],
  "secrets": [],
  "environments": []
}
```

Use `settings` for the common compact format:

```json
[
  { "scope": "repository", "type": "variable", "name": "APP_NAME", "value": "{{ project_name | slugify }}" },
  { "scope": "environment", "environment": "dev", "type": "secret", "name": "DEV_TOKEN", "value": "" }
]
```

Important semantics:

- `values[].value` as a scalar applies to every repo.
- `values[].value` as a non-empty array maps by repository index and must match repo count.
- `values[].value: []` asks per repo in interactive mode.
- blank required values fail in `--non-interactive`.
- blank variables/secrets are skipped, not prompted.
- setting arrays also map by repository index and must match repo count.
- the Jinja context includes `owner`, `repository`, `repo`, `full_name`, user `values`, and later `template` and `branch`.
- `slugify` is the custom Jinja filter.
- field values render up to three passes, so derived fields can reference earlier fields.

Never request or echo real secrets in chat. Ask the user to place them in the local control file/UI or leave them blank to skip.

## Template Mastery

Every subfolder inside `templates_root` is a template. Text files are rendered as Jinja even without `.j2`; files ending in `.j2` lose that suffix in the target path. Binary files are copied as bytes.

GitHub Actions expressions `${{ ... }}` are protected automatically, so workflow files can contain both Jinja and Actions syntax.

Use repo-specific overlays when only some repos need extra or replacement files. Valid overlay locations include:

- `<template>/<repo>/...`
- `<template>/_repo/<repo>/...`
- `<template>/_repos/<repo>/...`
- `<template>/_repo/orgs/<owner>/<repo>/...`
- `<template>/_repos/orgs/<owner>/<repo>/...`
- owner-qualified folder aliases like `owner__repo`, `owner--repo`, or `owner_repo`.

Base template files render first. Overlays render after and can replace the same target path. Top-level overlay folders are skipped from the generic base render so they do not leak into other repos.

Use `repositories[].folders` for external source folders outside `templates_root`; `source` may be absolute or relative to the control file, while `target` must be a safe relative path inside the destination repo.

## Execution Model

Authentication sources:

- `GITHUB_TOKEN`
- `GH_TOKEN`
- `gh auth login`

Mode `api`:

- uses GitHub Git Data API, not local clones;
- reads base/default branch;
- creates blobs/tree/commit;
- creates the working branch or updates it without force;
- creates or reuses an open PR for the same head/base;
- returns no PR when there are no changes and no existing branch.

Mode `git`:

- requires `git`;
- clones into `workspace`;
- checks out existing working branch or creates it from base;
- renders files into the clone;
- commits only if there is a diff;
- pushes branch and opens/reuses PR.

Settings:

- require `gh` when variables/secrets are present;
- use `gh variable set`, `gh secret set`, and `gh api` for environments;
- create an environment only when it has at least one non-blank item.

## UI Usage

Use the local UI when editing JSON by hand would be slower or riskier:

```powershell
repo-template ui --config control.json
```

The UI can load/save the control file, edit repos/fields/settings, adjust raw JSON, run validate, local/remote checks, dry-run planning, and execution jobs. Use `--port` or `--no-open` when needed.

## Senior Guardrails

- Start with `check --local` while designing templates; it catches schema, Jinja, path and render issues without remote calls.
- Use `run --dry-run --yes --non-interactive` to capture the exact plan without prompts.
- Keep branch names deterministic and repo-safe, usually with `slugify`.
- Prefer per-repo arrays only when the ordering is obvious and stable.
- Prefer repo overlays over conditional Jinja when the difference is file-level and repo-specific.
- Prefer Jinja conditionals inside files when the difference is small and data-driven.
- Keep `exclude` broad enough to avoid `.git`, OS files, control files, generated workspaces and secrets.
- Do not edit generated branches manually unless investigating a failure; rerun the CLI from the source templates/control instead.
- If the CLI can produce the requested PR/settings, do not create them through another tool.
