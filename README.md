# Sistema de Priorizacao de Chamados de TI

Aplicacao web para priorizar chamados de TI com base em **impacto**, **urgencia** e **tipo**.

Stack principal:
- Backend: Flask + SQLAlchemy + SQLite
- Frontend: Bootstrap + Chart.js
- Execucao em desenvolvimento: `npm run dev` (nodemon + Python runner)

URL local padrao: `http://127.0.0.1:5000`

## Inicio Rapido

No diretorio do projeto, execute:

```bash
npm install
npm run setup
npm run dev
```

Opcional para popular dados de exemplo:

```bash
npm run seed
```

## Scripts Disponiveis

- `npm run setup`: instala dependencias Python de `requirements.txt`
- `npm run dev`: sobe o servidor em modo desenvolvimento
- `npm start`: sobe em modo producao local (`FLASK_DEBUG=0`)
- `npm run test`: executa testes (`pytest`)
- `npm run seed`: insere chamados de exemplo
- `npm run install:all`: `npm install` + `npm run setup`

## Funcionalidades

- Cadastro de chamado com calculo automatico de score
- Preview de score/criticidade em tempo real no formulario
- Dashboard com cards, filtros e ranking
- Graficos por criticidade, tipo e area
- Edicao e atualizacao de status
- Exclusao com confirmacao
- Exportacao CSV
- API para estatisticas e detalhes

## Regra de Priorizacao

Formula usada:

```text
Score = (Impacto * 0.4) + (Urgencia * 0.4) + (Tipo * 0.2)
```

Mapeamentos:
- Impacto: `baixo=1`, `medio=2`, `alto=3`
- Urgencia: `baixa=1`, `media=2`, `alta=3`
- Tipo: `requisicao=1`, `problema=2`, `incidente=3`

Faixas de criticidade:
- `>= 2.6`: Critica
- `>= 2.0`: Alta
- `>= 1.4`: Media
- `< 1.4`: Baixa

## Rotas Principais

Paginas:
- `GET /`: dashboard
- `GET /novo`: formulario de criacao
- `POST /novo`: cria chamado
- `GET /editar/<id>`: formulario de edicao
- `POST /editar/<id>`: salva edicao
- `POST /excluir/<id>`: exclui chamado
- `GET /exportar`: exporta CSV

API:
- `GET /api/stats`: estatisticas para os graficos
- `GET /api/chamado/<id>`: detalhes de um chamado
- `POST /status/<id>/<status>`: altera status

## Estrutura do Projeto

```text
app.py
models.py
forms.py
templates/
scripts/
tests/
instance/
requirements.txt
package.json
```

## Troubleshooting

### Erro: `ERR_CONNECTION_REFUSED` em `127.0.0.1`

Causa comum: servidor nao esta rodando.

Passos:

```powershell
Set-Location "c:\Users\anacl\sistema de priorizacao\sistema-de-prioriza-ao"
npm run dev
```

Verifique se a porta esta ouvindo:

```powershell
Get-NetTCPConnection -LocalPort 5000 -State Listen
```

### Erro de porta em uso (`WinError 10048`)

Causa comum: mais de uma instancia tentando usar a porta 5000.

Limpe processos e suba novamente:

```powershell
Get-Process python* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Get-Process node* -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue
Set-Location "c:\Users\anacl\sistema de priorizacao\sistema-de-prioriza-ao"
npm run dev
```

### Formulario de novo chamado nao cria registro

Validacao aplicada no backend para garantir `status='Aberto'` quando o campo nao vier no formulario de criacao.

## Variaveis de Ambiente

Arquivo de exemplo: `.env.example`

Principais variaveis:
- `FLASK_DEBUG=1`
- `PORT=5000`
- `SECRET_KEY=...`

## Testes

Executar suite:

```bash
npm run test
```

Ou diretamente com Python:

```bash
python -m pytest tests -q
```
