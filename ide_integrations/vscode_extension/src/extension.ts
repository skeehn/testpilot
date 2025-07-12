import * as vscode from 'vscode';
import { spawn, exec } from 'child_process';
import { promisify } from 'util';
import * as path from 'path';
import * as fs from 'fs';

const execPromise = promisify(exec);

export function activate(context: vscode.ExtensionContext) {
    console.log('TestPilot extension is now active!');

    // Register all commands
    const commands = [
        vscode.commands.registerCommand('testpilot.generateTests', generateTests),
        vscode.commands.registerCommand('testpilot.generateTestsEnhanced', generateTestsEnhanced),
        vscode.commands.registerCommand('testpilot.generateIntegrationTests', generateIntegrationTests),
        vscode.commands.registerCommand('testpilot.runTests', runTests),
        vscode.commands.registerCommand('testpilot.runTestsWithCoverage', runTestsWithCoverage),
        vscode.commands.registerCommand('testpilot.triageTests', triageTests),
        vscode.commands.registerCommand('testpilot.interactive', interactiveMode),
        vscode.commands.registerCommand('testpilot.configure', configure),
        vscode.commands.registerCommand('testpilot.viewProviders', viewProviders),
    ];

    commands.forEach(command => context.subscriptions.push(command));

    // Register status bar item
    const statusBarItem = vscode.window.createStatusBarItem(vscode.StatusBarAlignment.Left, 100);
    statusBarItem.text = "$(rocket) TestPilot";
    statusBarItem.tooltip = "TestPilot - AI Test Generation";
    statusBarItem.command = "testpilot.interactive";
    statusBarItem.show();
    context.subscriptions.push(statusBarItem);

    // Show welcome message on first activation
    showWelcomeMessage();
}

async function generateTests(uri?: vscode.Uri) {
    const filePath = await getTargetFilePath(uri);
    if (!filePath) return;

    await executeTestPilotCommand('generate', filePath, {
        enhanced: false,
        showProgress: true,
        successMessage: 'Tests generated successfully! 🎉'
    });
}

async function generateTestsEnhanced(uri?: vscode.Uri) {
    const filePath = await getTargetFilePath(uri);
    if (!filePath) return;

    await executeTestPilotCommand('generate', filePath, {
        enhanced: true,
        showProgress: true,
        successMessage: 'Enhanced tests generated successfully! 🚀'
    });
}

async function generateIntegrationTests(uri?: vscode.Uri) {
    const filePath = await getTargetFilePath(uri);
    if (!filePath) return;

    await executeTestPilotCommand('generate', filePath, {
        integration: true,
        showProgress: true,
        successMessage: 'Integration tests generated successfully! 🔄'
    });
}

async function runTests(uri?: vscode.Uri) {
    const filePath = await getTargetFilePath(uri, true);
    if (!filePath) return;

    await executeTestPilotCommand('run', filePath, {
        showProgress: true,
        successMessage: 'Tests completed! 🏃'
    });
}

async function runTestsWithCoverage(uri?: vscode.Uri) {
    const filePath = await getTargetFilePath(uri, true);
    if (!filePath) return;

    await executeTestPilotCommand('run', filePath, {
        coverage: true,
        showProgress: true,
        successMessage: 'Tests with coverage completed! 📊'
    });
}

async function triageTests(uri?: vscode.Uri) {
    const filePath = await getTargetFilePath(uri, true);
    if (!filePath) return;

    const config = vscode.workspace.getConfiguration('testpilot');
    const defaultRepo = config.get<string>('githubRepo', '');
    
    const repo = await vscode.window.showInputBox({
        prompt: 'Enter GitHub repository (owner/repo)',
        value: defaultRepo,
        placeHolder: 'e.g., microsoft/vscode'
    });

    if (!repo) return;

    await executeTestPilotCommand('triage', filePath, {
        repo,
        showProgress: true,
        successMessage: 'Test triage completed! 🐛'
    });
}

async function interactiveMode() {
    const panel = vscode.window.createWebviewPanel(
        'testpilotInteractive',
        'TestPilot Interactive Mode',
        vscode.ViewColumn.Two,
        {
            enableScripts: true,
            retainContextWhenHidden: true
        }
    );

    panel.webview.html = getInteractiveWebviewContent();
    
    panel.webview.onDidReceiveMessage(
        async (message) => {
            switch (message.command) {
                case 'generateTests':
                    await handleInteractiveGeneration(message.data);
                    break;
            }
        },
        undefined,
        []
    );
}

async function configure() {
    const config = vscode.workspace.getConfiguration('testpilot');
    
    const provider = await vscode.window.showQuickPick(
        ['openai', 'anthropic', 'ollama'],
        {
            placeHolder: 'Select AI Provider',
            title: 'TestPilot Configuration'
        }
    );

    if (provider) {
        await config.update('defaultProvider', provider, vscode.ConfigurationTarget.Global);
        
        let model = 'gpt-4o';
        if (provider === 'anthropic') {
            model = 'claude-3-sonnet-20240229';
        } else if (provider === 'ollama') {
            model = 'llama2';
        }
        
        const customModel = await vscode.window.showInputBox({
            prompt: `Enter model name for ${provider}`,
            value: model,
            placeHolder: 'Model name'
        });

        if (customModel) {
            await config.update('defaultModel', customModel, vscode.ConfigurationTarget.Global);
        }

        vscode.window.showInformationMessage(`TestPilot configured with ${provider} (${customModel || model})`);
    }
}

async function viewProviders() {
    const terminal = vscode.window.createTerminal('TestPilot Providers');
    terminal.show();
    terminal.sendText('testpilot providers');
}

async function getTargetFilePath(uri?: vscode.Uri, isTestFile = false): Promise<string | undefined> {
    if (uri) {
        return uri.fsPath;
    }

    const activeEditor = vscode.window.activeTextEditor;
    if (activeEditor) {
        const filePath = activeEditor.document.fileName;
        if (isTestFile && !path.basename(filePath).startsWith('test_')) {
            vscode.window.showWarningMessage('This command should be used on test files (test_*.py)');
            return undefined;
        }
        return filePath;
    }

    const files = await vscode.window.showOpenDialog({
        canSelectFiles: true,
        canSelectFolders: false,
        canSelectMany: false,
        filters: {
            'Python Files': ['py']
        }
    });

    return files?.[0]?.fsPath;
}

async function executeTestPilotCommand(
    command: string,
    filePath: string,
    options: {
        enhanced?: boolean;
        integration?: boolean;
        coverage?: boolean;
        repo?: string;
        showProgress?: boolean;
        successMessage?: string;
    } = {}
) {
    const config = vscode.workspace.getConfiguration('testpilot');
    const provider = config.get<string>('defaultProvider', 'openai');
    const model = config.get<string>('defaultModel', 'gpt-4o');
    const pythonPath = config.get<string>('pythonPath', 'python');

    let cmdArgs = ['-m', 'testpilot.cli', command, filePath];

    if (command === 'generate') {
        cmdArgs.push('--provider', provider);
        cmdArgs.push('--model', model);
        
        if (options.enhanced) {
            cmdArgs.push('--enhanced');
        }
        
        if (options.integration) {
            cmdArgs.push('--integration');
        }
    } else if (command === 'run') {
        if (options.coverage) {
            cmdArgs.push('--coverage');
        }
    } else if (command === 'triage' && options.repo) {
        cmdArgs.push('--repo', options.repo);
    }

    if (options.showProgress) {
        return vscode.window.withProgress({
            location: vscode.ProgressLocation.Notification,
            title: `TestPilot: ${command}`,
            cancellable: true
        }, async (progress, token) => {
            progress.report({ message: 'Starting...' });

            return new Promise<void>((resolve, reject) => {
                const process = spawn(pythonPath, cmdArgs, {
                    cwd: vscode.workspace.workspaceFolders?.[0]?.uri.fsPath
                });

                let output = '';
                let errorOutput = '';

                process.stdout.on('data', (data) => {
                    const chunk = data.toString();
                    output += chunk;
                    
                    // Parse progress from output
                    const lines = chunk.split('\n');
                    for (const line of lines) {
                        if (line.includes('[')) {
                            const match = line.match(/\[(.*?)\]/);
                            if (match) {
                                progress.report({ message: match[1] });
                            }
                        }
                    }
                });

                process.stderr.on('data', (data) => {
                    errorOutput += data.toString();
                });

                process.on('close', (code) => {
                    if (code === 0) {
                        if (options.successMessage) {
                            vscode.window.showInformationMessage(options.successMessage);
                        }
                        
                        // Show output in a new document
                        if (output) {
                            showOutputInNewDocument(output, `TestPilot ${command} Output`);
                        }
                        
                        resolve();
                    } else {
                        vscode.window.showErrorMessage(`TestPilot ${command} failed: ${errorOutput}`);
                        reject(new Error(errorOutput));
                    }
                });

                token.onCancellationRequested(() => {
                    process.kill();
                    reject(new Error('Operation cancelled'));
                });
            });
        });
    }
}

async function showOutputInNewDocument(content: string, title: string) {
    const document = await vscode.workspace.openTextDocument({
        content: content,
        language: 'plaintext'
    });
    
    const editor = await vscode.window.showTextDocument(document, vscode.ViewColumn.Two);
    
    // Set the title
    await vscode.commands.executeCommand('workbench.action.keepEditor');
}

function getInteractiveWebviewContent(): string {
    return `
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <meta name="viewport" content="width=device-width, initial-scale=1.0">
        <title>TestPilot Interactive Mode</title>
        <style>
            body {
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
                padding: 20px;
                line-height: 1.6;
                background: var(--vscode-editor-background);
                color: var(--vscode-editor-foreground);
            }
            .container {
                max-width: 600px;
                margin: 0 auto;
            }
            .header {
                text-align: center;
                margin-bottom: 30px;
            }
            .header h1 {
                color: var(--vscode-textLink-foreground);
                margin-bottom: 10px;
            }
            .form-group {
                margin-bottom: 20px;
            }
            label {
                display: block;
                margin-bottom: 5px;
                font-weight: 600;
                color: var(--vscode-input-foreground);
            }
            select, input[type="text"], input[type="file"] {
                width: 100%;
                padding: 8px 12px;
                border: 1px solid var(--vscode-input-border);
                background: var(--vscode-input-background);
                color: var(--vscode-input-foreground);
                border-radius: 4px;
            }
            .checkbox-group {
                display: flex;
                align-items: center;
                gap: 10px;
            }
            .checkbox-group input[type="checkbox"] {
                width: auto;
            }
            .button {
                background: var(--vscode-button-background);
                color: var(--vscode-button-foreground);
                border: none;
                padding: 12px 24px;
                border-radius: 4px;
                cursor: pointer;
                font-size: 14px;
                font-weight: 600;
                transition: background 0.2s;
            }
            .button:hover {
                background: var(--vscode-button-hoverBackground);
            }
            .button-primary {
                background: var(--vscode-textLink-foreground);
                color: white;
            }
            .actions {
                text-align: center;
                margin-top: 30px;
            }
            .feature-list {
                background: var(--vscode-textBlockQuote-background);
                padding: 20px;
                border-radius: 8px;
                margin-bottom: 20px;
            }
            .feature-list h3 {
                margin-top: 0;
                color: var(--vscode-textLink-foreground);
            }
            .feature-list ul {
                margin: 0;
                padding-left: 20px;
            }
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <h1>🚀 TestPilot Interactive Mode</h1>
                <p>Generate comprehensive, AI-powered tests with ease</p>
            </div>
            
            <div class="feature-list">
                <h3>✨ What makes TestPilot special:</h3>
                <ul>
                    <li>🧠 Advanced AI models with smart context understanding</li>
                    <li>🔄 Automatic test verification and quality assurance</li>
                    <li>🎯 Both unit and integration test generation</li>
                    <li>📊 Coverage analysis and insights</li>
                    <li>🐛 Smart GitHub issue creation for failures</li>
                </ul>
            </div>

            <form id="testGenerationForm">
                <div class="form-group">
                    <label for="sourceFile">Python Source File:</label>
                    <input type="file" id="sourceFile" accept=".py" required>
                </div>

                <div class="form-group">
                    <label for="provider">AI Provider:</label>
                    <select id="provider" required>
                        <option value="openai">OpenAI GPT</option>
                        <option value="anthropic">Anthropic Claude</option>
                        <option value="ollama">Ollama (Local)</option>
                    </select>
                </div>

                <div class="form-group">
                    <label for="model">Model:</label>
                    <input type="text" id="model" value="gpt-4o" required>
                </div>

                <div class="form-group">
                    <label for="testType">Test Type:</label>
                    <select id="testType" required>
                        <option value="unit">Unit Tests</option>
                        <option value="integration">Integration Tests</option>
                        <option value="both">Both Unit & Integration</option>
                    </select>
                </div>

                <div class="form-group">
                    <div class="checkbox-group">
                        <input type="checkbox" id="enhanced" checked>
                        <label for="enhanced">Enhanced Mode (Code analysis & verification)</label>
                    </div>
                </div>

                <div class="form-group">
                    <div class="checkbox-group">
                        <input type="checkbox" id="autoRun">
                        <label for="autoRun">Auto-run tests after generation</label>
                    </div>
                </div>

                <div class="actions">
                    <button type="submit" class="button button-primary">
                        🚀 Generate Tests
                    </button>
                </div>
            </form>
        </div>

        <script>
            const vscode = acquireVsCodeApi();
            
            document.getElementById('provider').addEventListener('change', function() {
                const modelInput = document.getElementById('model');
                switch(this.value) {
                    case 'openai':
                        modelInput.value = 'gpt-4o';
                        break;
                    case 'anthropic':
                        modelInput.value = 'claude-3-sonnet-20240229';
                        break;
                    case 'ollama':
                        modelInput.value = 'llama2';
                        break;
                }
            });

            document.getElementById('testGenerationForm').addEventListener('submit', function(e) {
                e.preventDefault();
                
                const formData = {
                    sourceFile: document.getElementById('sourceFile').files[0]?.name,
                    provider: document.getElementById('provider').value,
                    model: document.getElementById('model').value,
                    testType: document.getElementById('testType').value,
                    enhanced: document.getElementById('enhanced').checked,
                    autoRun: document.getElementById('autoRun').checked
                };
                
                if (!formData.sourceFile) {
                    alert('Please select a Python source file');
                    return;
                }
                
                vscode.postMessage({
                    command: 'generateTests',
                    data: formData
                });
            });
        </script>
    </body>
    </html>
    `;
}

async function handleInteractiveGeneration(data: any) {
    // This would handle the interactive generation from the webview
    // For now, we'll show a message
    vscode.window.showInformationMessage(`Interactive generation initiated for ${data.sourceFile} with ${data.provider}`);
}

function showWelcomeMessage() {
    const config = vscode.workspace.getConfiguration('testpilot');
    const hasShownWelcome = config.get('hasShownWelcome', false);
    
    if (!hasShownWelcome) {
        vscode.window.showInformationMessage(
            '🚀 Welcome to TestPilot! Your AI testing co-pilot is ready.',
            'Get Started',
            'Configure'
        ).then(selection => {
            if (selection === 'Get Started') {
                vscode.commands.executeCommand('testpilot.interactive');
            } else if (selection === 'Configure') {
                vscode.commands.executeCommand('testpilot.configure');
            }
        });
        
        config.update('hasShownWelcome', true, vscode.ConfigurationTarget.Global);
    }
}

export function deactivate() {}