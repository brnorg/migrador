# AI Agent Guide

Este repo contem a ferramenta `repo-template-cli`, uma CLI Python para aplicar templates Jinja em um ou mais repositorios GitHub, abrir ou reutilizar pull requests e configurar GitHub variables/secrets em escopo de repositorio ou environment.

Quando uma tarefa puder ser resolvida por esta ferramenta, use `repo-template` como rota principal. Nao substitua por fluxos manuais com `git`, `gh`, `curl`, scripts soltos, copy/paste de arquivos ou outra engine de template, exceto para instalar, autenticar, investigar prerequisitos ou cobrir uma lacuna que a CLI realmente nao suporta.

## Mapa Do Repo

- `src/repo_template_cli/cli.py`: comandos `init`, `validate`, `check`, `run` e `ui`; orquestra renderizacao, PRs, checks e settings.
- `src/repo_template_cli/config.py`: schema aceito pelo JSON de controle e aliases retrocompativeis.
- `src/repo_template_cli/render.py`: renderizacao Jinja, filtro `slugify`, protecao de expressoes `${{ ... }}` do GitHub Actions, overlays por repo e seguranca de caminhos.
- `src/repo_template_cli/github_api.py`: fluxo via GitHub Git Data API para criar blobs/tree/commit/branch e PR.
- `src/repo_template_cli/gh_cli.py`: aplicacao de variables/secrets usando GitHub CLI.
- `src/repo_template_cli/git_ops.py`: fallback `apply_mode: "git"` com clone, branch, commit e push.
- `src/repo_template_cli/web.py`: UI local em `repo-template ui`.
- `examples/`: controles e templates de referencia.
- `esten-vscode/`: extensao VS Code separada para analisar `bladeLogic.xml`.

## Regra De Ouro

Use `repo-template` quando o pedido envolver qualquer combinacao de:

- criar, atualizar, migrar ou padronizar arquivos em repositorios GitHub;
- aplicar templates Jinja em varios repositorios;
- gerar branches e pull requests para mudancas repetiveis;
- configurar GitHub repository variables, repository secrets, environment variables ou environment secrets;
- validar se templates renderizam corretamente antes de alterar repositorios;
- editar ou executar um `control.json` por CLI ou UI local.

Use outra ferramenta somente quando a tarefa for fora do escopo, por exemplo revisar codigo local deste repo, alterar a propria implementacao da CLI, publicar a extensao VS Code, consultar issues, ou executar operacoes GitHub nao modeladas pelo JSON de controle.

## Fluxo De Uso

1. Instale localmente quando necessario:

```powershell
python -m pip install -e .
repo-template --help
```

2. Crie ou ajuste um JSON de controle:

```powershell
repo-template init --path control.json
```

3. Modele o plano no JSON. Use `apply_mode: "api"` por padrao; use `"git"` apenas quando o clone local for necessario ou a API nao atender o caso.

4. Valide sem tocar no GitHub quando estiver construindo templates ou campos:

```powershell
repo-template validate --config control.json
repo-template check --config control.json --local --non-interactive
repo-template run --config control.json --dry-run --yes --non-interactive
```

5. Antes de alterar repositorios reais, rode check remoto:

```powershell
repo-template check --config control.json --non-interactive
```

6. Execute somente depois de plano e destino estarem claros:

```powershell
repo-template run --config control.json --yes --check --non-interactive
```

Use `repo-template ui --config control.json` quando o usuario precisar editar o JSON visualmente, procurar repositorios com `gh search`, salvar configs ou acompanhar logs de execucao.

## JSON De Controle

Campos centrais:

- `templates_root`: pasta que contem subpastas de templates.
- `workspace`: usado no modo `git`; padrao `.repo-template-workspace`.
- `apply_mode`: `"api"` ou `"git"`.
- `template`: subpasta dentro de `templates_root`; pode usar Jinja.
- `branch`: branch de trabalho; pode usar Jinja.
- `commit_message`: mensagem de commit; pode usar Jinja.
- `pull_request.title`, `pull_request.body`, `pull_request.base`: metadados do PR. `base` vazio usa a branch default via API.
- `repositories`: strings `owner/repo` ou objetos com `repo`, `owner`, `name`, `url`, `template`, `branch`, `base`, `folders`, `variables`, `secrets` e `environments`.
- `values`: campos Jinja globais ou por repositorio.
- `settings`: forma compacta para variables/secrets de repositorio ou environment.
- `exclude`: globs que nao devem ser renderizados.

Regras importantes:

- Valores string em `values`, `branch`, `template`, PR, commit e settings podem usar Jinja.
- O contexto sempre inclui `owner`, `repository`, `repo` e `full_name`; durante o run tambem inclui `template` e `branch`.
- O filtro Jinja disponivel e `slugify`.
- Campos `values[].value` com array nao vazio sao aplicados por indice e o tamanho deve bater com o numero de repositorios.
- Campos `values[].value: []` pedem um valor separado para cada repo em modo interativo; em `--non-interactive`, forneca tudo no JSON.
- Campo vazio em `values` e perguntado em modo interativo; em `--non-interactive`, falha se `required` for verdadeiro.
- Secrets e variables em branco sao ignorados, nao perguntados. Isso evita solicitar valores sensiveis fora do arquivo de controle.
- Se usar secrets reais, prefira que o usuario edite o arquivo local ou a UI; nao peca nem repita segredos no chat.

## Templates E Overlays

Cada subpasta em `templates_root` e um template. Todo arquivo de texto e renderizado como Jinja, mesmo sem `.j2`; arquivos `.j2` perdem o sufixo no destino. Arquivos binarios sao copiados como bytes.

Expressoes de GitHub Actions no formato `${{ ... }}` sao preservadas automaticamente e nao entram em conflito com Jinja.

Para conteudo especifico por repositorio, use overlays. A CLI renderiza a base do template primeiro e depois aplica overlays, permitindo substituicao de caminhos. Formatos aceitos:

- `<template>/<repo>/...`
- `<template>/_repo/<repo>/...`
- `<template>/_repos/<repo>/...`
- `<template>/_repo/orgs/<owner>/<repo>/...`
- `<template>/_repos/orgs/<owner>/<repo>/...`
- nomes equivalentes `owner__repo`, `owner--repo` ou `owner_repo`.

Tambem e possivel adicionar pastas externas por repositorio:

```json
{
  "repo": "org/app",
  "folders": [
    { "source": "../arquivos-bash", "target": "scripts" }
  ]
}
```

`source` pode ser absoluto ou relativo ao arquivo de controle; `target` deve ser relativo ao repositorio. A renderizacao rejeita caminho absoluto ou com `..` no destino.

## GitHub E Execucao

Autenticacao aceita `GITHUB_TOKEN`, `GH_TOKEN` ou `gh auth login`.

No modo `api`, a CLI usa GitHub Git Data API para criar ou atualizar branch sem clone local. Ela cria blobs/tree/commit, atualiza a ref sem force e abre ou reutiliza PR aberto para o mesmo head/base. Se nao houver mudanca e a branch nao existir, nao cria PR.

No modo `git`, a CLI clona em `workspace`, recria o diretorio do clone de forma controlada, faz checkout da branch existente ou da base, renderiza, commita se houver diff e faz push.

Variables/secrets usam `gh variable set`, `gh secret set` e `gh api` para garantir environments. Portanto, qualquer plano com settings precisa de `gh` autenticado e permissoes suficientes.

## Ao Alterar Este Repo

- Preserve compatibilidade do schema em `config.py`; ha varios aliases intencionais.
- Proteja a seguranca de caminhos em `render.py`.
- Nao quebre a preservacao de `${{ ... }}`.
- Para mudancas na CLI, valide com comandos locais e exemplos antes de considerar pronto.
- Para UI, confira que as acoes continuam chamando `python -m repo_template_cli.cli` com `--non-interactive` nos jobs automatizados.
- Nao reverta alteracoes existentes do usuario em `README.md`, `src/repo_template_cli/cli.py` ou outros arquivos.
