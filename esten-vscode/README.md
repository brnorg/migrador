# BladeLogic Runner

Extensao simples para VS Code que adiciona a opcao **Analisar bladeLogic.xml** no menu de contexto do Explorer.

## Como usar em desenvolvimento

1. Abra este projeto no VS Code.
2. Rode `npm install` uma vez para instalar as ferramentas de desenvolvimento.
3. Pressione `F5` para iniciar uma janela de desenvolvimento da extensao.
4. Na nova janela, clique com o botao direito em um arquivo chamado `bladeLogic.xml`.
5. Escolha **Analisar bladeLogic.xml**.

O nome do arquivo e tratado sem diferenciar letras maiusculas e minusculas, entao `BLADElogic.XML`, `BLADELOGIC.xml` e `bladelogic.XML` tambem funcionam.

## Onde fica a analise

A logica de analise fica em:

```text
analyzer/bladeLogicAnalyzer.js
```

Esse arquivo le o XML, conta linhas, caracteres e tags, e normaliza os nomes das tags para minusculas.

## Terminal de saida

A extensao usa sempre o mesmo terminal chamado **BladeLogic** enquanto ele estiver aberto.

Se voce fechar esse terminal manualmente, a extensao cria outro terminal **BladeLogic** na proxima analise.

## Compilar

Esta extensao usa JavaScript puro, entao nao existe uma compilacao real como em projetos TypeScript.

O comando abaixo valida a sintaxe dos arquivos principais:

```powershell
npm run compile
```

Esse comando executa:

```powershell
npm run lint
```

## Empacotar para instalar localmente

1. Instale as dependencias:

```powershell
npm install
```

2. Valide a extensao:

```powershell
npm run compile
```

3. Gere o arquivo `.vsix`:

```powershell
npm run package
```

Depois disso sera criado um arquivo parecido com:

```text
bladelogic-runner-0.0.1.vsix
```

## Instalar o pacote local no VS Code

Com o arquivo `.vsix` gerado, rode:

```powershell
code --install-extension .\bladelogic-runner-0.0.1.vsix
```

Se voce mudar a versao no `package.json`, ajuste o nome do arquivo no comando acima.

Tambem da para instalar pela interface do VS Code:

1. Abra a aba **Extensions**.
2. Clique no menu `...`.
3. Escolha **Install from VSIX...**.
4. Selecione o arquivo `.vsix` gerado.

## Icone

O icone usado pela extensao fica em:

```text
resources/icon.png
```

Tambem existe uma versao editavel em SVG:

```text
resources/icon.svg
```

O arquivo `package.json` aponta para o PNG com:

```json
"icon": "resources/icon.png"
```
