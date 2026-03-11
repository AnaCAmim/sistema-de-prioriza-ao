const { spawn, spawnSync } = require('child_process');

const command = process.argv[2] || 'dev';

function canRun(executable, args = ['--version']) {
  const result = spawnSync(executable, args, {
    stdio: 'ignore',
    shell: false,
  });

  return result.status === 0;
}

function detectPython() {
  const envPython = process.env.PYTHON || process.env.npm_config_python;
  if (envPython && canRun(envPython)) {
    return { executable: envPython, prefixArgs: [] };
  }

  const candidates = [
    { executable: 'python', prefixArgs: [] },
    { executable: 'py', prefixArgs: ['-3'] },
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

function run(executable, args, env = process.env) {
  const child = spawn(executable, args, {
    stdio: 'inherit',
    shell: false,
    env,
  });

  child.on('exit', (code, signal) => {
    if (signal) {
      process.kill(process.pid, signal);
      return;
    }

    process.exit(code ?? 0);
  });

  child.on('error', (error) => {
    console.error(error.message);
    process.exit(1);
  });
}

const python = detectPython();

if (command === 'setup') {
  run(python.executable, [...python.prefixArgs, '-m', 'pip', 'install', '-r', 'requirements.txt']);
} else if (command === 'start') {
  const env = { ...process.env, FLASK_DEBUG: '0' };
  run(python.executable, [...python.prefixArgs, 'app.py'], env);
} else if (command === 'dev') {
  const env = { ...process.env, FLASK_DEBUG: '1' };
  run(python.executable, [...python.prefixArgs, 'app.py'], env);
} else if (command === 'watch') {
  // Chamado pelo nodemon: nodemon ja faz o restart, entao desativa o
  // reloader interno do Flask para evitar reinicializacoes duplicadas.
  const env = {
    ...process.env,
    FLASK_DEBUG: '0',
    LIVE_RELOAD: '1',
  };
  run(python.executable, [...python.prefixArgs, 'app.py'], env);
} else if (command === 'seed') {
  run(python.executable, [...python.prefixArgs, 'scripts/seed_sample.py']);
} else if (command === 'test') {
  run(python.executable, [...python.prefixArgs, '-m', 'pytest', 'tests/', '-v', '--tb=short']);
} else {
  console.error(`Comando invalido: ${command}`);
  process.exit(1);
}