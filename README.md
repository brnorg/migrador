# repo-template-cli

CLI Python instalavel para aplicar templates Jinja em um ou mais repositorios GitHub, abrir pull requests e configurar variables/secrets via GitHub CLI.

Por padrao, os arquivos sao enviados pela GitHub Git Data API (`apply_mode: "api"`), sem clonar o repositorio. O modo `git` continua disponivel como fallback.

## Instalar

```powershell
python -m pip install -e .
```

Depois disso o comando fica disponivel:

```powershell
repo-template --help
```

## Criar um arquivo de controle

```powershell
repo-template init --path control.json
```

Edite o `control.json` com a pasta de templates, campos Jinja, repositorios, branch, mensagem de commit, dados do PR e variables/secrets.

## Executar

```powershell
repo-template run --config control.json
```

Antes de alterar qualquer repositorio, a CLI mostra uma revisao com:

- repositorios alvo;
- template usado;
- branch de trabalho;
- base do pull request;
- valores Jinja resolvidos;
- variables/secrets que serao aplicados;
- itens em branco que serao ignorados.

Use `--dry-run` para ver a revisao sem alterar nada:

```powershell
repo-template run --config control.json --dry-run
```

Use `check` para testar o setup antes da execucao:

```powershell
repo-template check --config control.json
```

O check valida JSON, comandos necessarios para o modo escolhido, autenticacao GitHub, acesso aos repositorios, branch base remota, Jinja das mensagens/settings e renderizacao completa do template em uma pasta temporaria. Para validar apenas JSON/templates/Jinja sem consultar GitHub:

```powershell
repo-template check --config control.json --local
```

## Autenticacao

A CLI usa:

- GitHub Git Data API para criar branch/commit sem clonar quando `apply_mode` e `api`;
- `git` para clonar, criar branch, commitar e fazer push quando `apply_mode` e `git`;
- API do GitHub para descobrir a branch padrao e abrir ou reutilizar pull requests;
- `gh` para configurar variables/secrets no repositorio e nos environments.

Autentique com uma destas opcoes:

```powershell
gh auth login
```

ou defina `GITHUB_TOKEN`/`GH_TOKEN` com permissoes para repositorios, pull requests, variables e secrets.

## JSON de controle

O formato principal e simples: `repositories`, `values` e `settings`.

Campos Jinja vazios em `values` sao perguntados a cada execucao. Campos com `value` preenchido sao usados como padrao e tambem podem usar Jinja.

Quando um `value` e array, cada posicao e aplicada ao repositorio de mesmo indice: o primeiro valor vai para o primeiro repositorio, o segundo valor vai para o segundo repositorio, e assim por diante. O tamanho do array precisa bater com a quantidade de repositorios.

Quando um `value` e `[]`, a CLI pergunta um valor separado para cada repositorio.

Secrets e variables vazios nao sao perguntados: eles sao ignorados para evitar solicitar valores sensiveis fora do arquivo de controle.

`apply_mode` aceita:

- `api`: mais rapido; cria blobs/tree/commit/branch direto pela API do GitHub.
- `git`: fallback; clona o repositorio, commita e faz push.

Exemplo resumido:

```json
{
  "templates_root": "./examples/templates",
  "apply_mode": "api",
  "template": "java",
  "branch": "chore/bootstrap-{{ project_name | slugify }}",
  "commit_message": "Bootstrap {{ project_name }}",
  "pull_request": {
    "title": "Bootstrap {{ project_name }}",
    "body": "Aplica o template {{ template }} para {{ project_name }}.",
    "base": ""
  },
  "repositories": [
    "sua-org/repo-a",
    "sua-org/repo-b"
  ],
  "values": [
    { "name": "project_name", "label": "Nome do projeto", "value": ["Servico A", "Servico B"] },
    { "name": "team_name", "label": "Time responsavel", "value": [] },
    { "name": "package_name", "value": "com.example.{{ project_name | slugify | replace('-', '.') }}" },
    { "name": "runtime_version", "value": "21" }
  ],
  "settings": [
    { "scope": "repository", "type": "variable", "name": "APP_NAME", "value": "{{ project_name | slugify }}" },
    { "scope": "repository", "type": "secret", "name": "TOKEN_EXEMPLO", "value": "" },
    { "scope": "environment", "environment": "dev", "type": "variable", "name": "JAVA_VERSION", "value": "{{ runtime_version }}" },
    { "scope": "environment", "environment": "dev", "type": "secret", "name": "DEV_TOKEN", "value": "" }
  ]
}
```

## Templates

Cada subpasta dentro de `templates_root` e um template, por exemplo:

```text
examples/templates/
  java/
    .github/
      workflows/
        ci.yml.j2
    helpers/
      bootstrap.sh.j2
    repo-a/
      helpers/
        repo-info.txt
    _repos/
      orgs/
        sua-org/
          repo-b/
            helpers/
              org-repo-info.txt
    README.md.j2
    pom.xml.j2
  nodejs/
    README.md.j2
    package.json.j2
```

Arquivos `.j2` perdem o sufixo no destino. Conteudo e nomes de arquivos/pastas podem usar Jinja.

Todo arquivo de texto dentro do template e tratado como Jinja, mesmo sem terminar com `.j2`. Use `.j2` quando voce tambem quiser remover esse sufixo do nome final.

Expressoes do GitHub Actions no formato `${{ ... }}` sao preservadas automaticamente e nao entram em conflito com Jinja. Por exemplo, `echo "${{ github.ref_name }}"` continua igual no arquivo final.

Para arquivos especificos por repositorio, crie uma pasta com o nome do repo dentro do template. Esses arquivos sao aplicados apenas naquele repo e o nome da pasta nao entra no caminho final:

```text
examples/templates/java/
  README.md.j2
  repo-a/
    .github/
      workflows/
        deploy.yml
    helpers/
      repo-info.txt
```

No exemplo acima, `repo-a/helpers/repo-info.txt` vira `helpers/repo-info.txt` somente no repositorio `repo-a`. Tambem sao aceitos os formatos explicitos `_repos/repo-a/...` e `_repos/orgs/sua-org/repo-a/...`.

Para evitar ambiguidade entre organizacoes, voce pode usar `_repos/orgs/<org>/<repo>/...`, ou usar `owner__repo`, `owner--repo` ou `owner_repo` como nome da pasta. A ferramenta tambem aceita `_repo` no singular como alias de `_repos`.
