// ============================================================================
// python-runner.js — Intermediário Node.js para executar comandos Python
// ============================================================================
// Este script serve como ponte entre o npm (package.json) e o Python.
// Quando rodamos "npm run dev", "npm run seed" etc., o Node.js chama este
// arquivo que detecta qual executável Python está disponível na máquina e
// repassa o comando correto.
//
// Por que usar um runner em JS?
//   - Em ambientes Windows, Linux e Mac o nome do Python pode variar
//     (python, python3, py -3). Este script tenta todos automaticamente.
//   - Permite definir variáveis de ambiente diferentes para cada modo
//     (dev, watch, start) sem complicar o package.json.
//
// Comandos disponíveis (via npm run <comando>):
//   setup  → instala dependências Python do requirements.txt
//   start  → roda o Flask em modo produção (FLASK_DEBUG=0)
//   dev    → roda o Flask em modo desenvolvimento (FLASK_DEBUG=1)
//   watch  → usado pelo nodemon — desliga reloader interno do Flask
//   seed   → executa o seed_sample.py para popular o banco
//   test   → roda a suíte de testes com pytest
// ============================================================================

const { spawn, spawnSync } = require('child_process');

// Captura o comando passado pela linha de comando (ex: "dev", "seed")
// Se nenhum for informado, assume "dev" como padrão.
const command = process.argv[2] || 'dev';

// --------------------------------------------------------------------------
// Verifica se um executável está disponível no sistema
// --------------------------------------------------------------------------
// Tenta rodar "executável --version" silenciosamente.
// Se o exit code for 0, o executável existe e funciona.
function canRun(executable, args = ['--version']) {
  const result = spawnSync(executable, args, {
    stdio: 'ignore',  // Não mostra saída no terminal
    shell: false,      // Executa diretamente, sem shell intermediário
  });

  return result.status === 0;
}

// --------------------------------------------------------------------------
// Detecta qual Python usar
// --------------------------------------------------------------------------
// Ordem de prioridade:
//   1. Variável de ambiente PYTHON ou npm_config_python (configuração manual)
//   2. Comando "python" (Linux/Mac com Python 3 como padrão)
//   3. Comando "py -3" (Windows com Python Launcher instalado)
// Se nenhum funcionar, lança erro explicativo.
function detectPython() {
  // Primeiro tenta usar a variável de ambiente, se definida
  const envPython = process.env.PYTHON || process.env.npm_config_python;
  if (envPython && canRun(envPython)) {
    return { executable: envPython, prefixArgs: [] };
  }

  // Lista de candidatos — testados na ordem
  const candidates = [
    { executable: 'python', prefixArgs: [] },
    { executable: 'py', prefixArgs: ['-3'] },  // Windows launcher
  ];

  for (const candidate of candidates) {
    if (canRun(candidate.executable, [...candidate.prefixArgs, '--version'])) {
      return candidate;
    }
  }

  throw new Error(
    'Python 3 nao encontrado. Defina a variavel PYTHON ou instale Python 3 com o launcher "py" habilitado.'
  );
}

// --------------------------------------------------------------------------
// Executa um processo filho com herança de stdio
// --------------------------------------------------------------------------
// stdio: 'inherit' faz o processo filho compartilhar o terminal do pai,
// permitindo ver a saída do Flask/pytest diretamente no console.
function run(executable, args, env = process.env) {
  const child = spawn(executable, args, {
    stdio: 'inherit',  // Saída visível no terminal
    shell: false,       // Sem shell intermediário (mais seguro)
    env,                // Variáveis de ambiente passadas ao processo
  });

  // Quando o processo filho terminar, encerra o runner com o mesmo código
  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }

    process.exit(code ?? 0);
  });

  // Se houver erro ao iniciar o processo (ex: executável não encontrado)
  child.on('error', (error) => {
    console.error(error.message);
    process.exit(1);
  });
}

// --------------------------------------------------------------------------
// Detecção do Python e execução do comando solicitado
// --------------------------------------------------------------------------
const python = detectPython();

if (command === 'setup') {
  // Instala as dependências listadas em requirements.txt
  run(python.executable, [...python.prefixArgs, '-m', 'pip', 'install', '-r', 'requirements.txt']);

} else if (command === 'start') {
  // Modo produção — sem debug, sem reloader
  const env = { ...process.env, FLASK_DEBUG: '0' };
  run(python.executable, [...python.prefixArgs, 'app.py'], env);

} else if (command === 'dev') {
  // Modo desenvolvimento — debug ativo, reloader do Flask ligado
  const env = { ...process.env, FLASK_DEBUG: '1' };
  run(python.executable, [...python.prefixArgs, 'app.py'], env);

} else if (command === 'watch') {
  // Chamado pelo nodemon: o nodemon já faz o restart automático quando
  // detecta mudanças nos arquivos, então desativamos o reloader interno
  // do Flask para evitar reinicializações duplicadas.
  // LIVE_RELOAD=1 ativa o script de livereload no browser.
  const env = {
    ...process.env,
    FLASK_DEBUG: '0',
    LIVE_RELOAD: '1',
  };
  run(python.executable, [...python.prefixArgs, 'app.py'], env);

} else if (command === 'seed') {
  // Executa o script de carga de dados de exemplo
  run(python.executable, [...python.prefixArgs, 'scripts/seed_sample.py']);

} else if (command === 'test') {
  // Roda todos os testes com saída detalhada (-v) e traceback curto
  run(python.executable, [...python.prefixArgs, '-m', 'pytest', 'tests/', '-v', '--tb=short']);

} else {
  // Comando não reconhecido — exibe erro e encerra
  console.error(`Comando invalido: ${command}`);
  process.exit(1);
}