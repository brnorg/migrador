const vscode = require('vscode');
const path = require('path');
const { analyzeBladeLogicXml } = require('./analyzer/bladeLogicAnalyzer');

const TARGET_FILE_NAME = 'bladelogic.xml';
let bladeLogicTerminal;
let bladeLogicPty;

function activate(context) {
  const disposable = vscode.commands.registerCommand(
    'bladelogicRunner.analyzeFile',
    async (uri) => {
      if (!uri || uri.scheme !== 'file') {
        vscode.window.showWarningMessage('Clique com o botao direito em um arquivo bladeLogic.xml.');
        return;
      }

      const fileName = path.basename(uri.fsPath).toLowerCase();

      if (fileName !== TARGET_FILE_NAME) {
        vscode.window.showWarningMessage('Este comando funciona apenas com arquivos bladeLogic.xml.');
        return;
      }

      try {
        const fileBytes = await vscode.workspace.fs.readFile(uri);
        const fileContent = Buffer.from(fileBytes).toString('utf8');
        const report = analyzeBladeLogicXml(fileContent, uri.fsPath);
        const terminal = getBladeLogicTerminal();

        terminal.show();
        bladeLogicPty.writeReport(report);
      } catch (error) {
        const message = error instanceof Error ? error.message : String(error);
        vscode.window.showErrorMessage(`Erro ao analisar bladeLogic.xml: ${message}`);
      }
    }
  );

  const terminalCloseDisposable = vscode.window.onDidCloseTerminal((closedTerminal) => {
    if (closedTerminal === bladeLogicTerminal) {
      bladeLogicTerminal = undefined;
      bladeLogicPty = undefined;
    }
  });

  context.subscriptions.push(disposable, terminalCloseDisposable);
}

function getBladeLogicTerminal() {
  if (!bladeLogicTerminal || !bladeLogicPty) {
    bladeLogicPty = new BladeLogicTerminal();
    bladeLogicTerminal = vscode.window.createTerminal({
      name: 'BladeLogic',
      pty: bladeLogicPty
    });
  }

  return bladeLogicTerminal;
}

class BladeLogicTerminal {
  constructor() {
    this.writeEmitter = new vscode.EventEmitter();
    this.onDidWrite = this.writeEmitter.event;
    this.isOpen = false;
    this.pendingOutput = '';
  }

  open() {
    this.isOpen = true;

    if (this.pendingOutput) {
      this.writeEmitter.fire(this.pendingOutput);
      this.pendingOutput = '';
    }
  }

  writeReport(report) {
    this.write([
      '',
      '========================================',
      report,
      '========================================',
      ''
    ].join('\r\n'));
  }

  close() {
    this.isOpen = false;
    this.writeEmitter.dispose();
  }

  write(text) {
    const terminalText = text.replace(/\r?\n/g, '\r\n');

    if (this.isOpen) {
      this.writeEmitter.fire(terminalText);
      return;
    }

    this.pendingOutput += terminalText;
  }
}

function deactivate() {}

module.exports = {
  activate,
  deactivate
};
