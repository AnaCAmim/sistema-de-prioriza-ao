# PrioriTI — Sistema de Priorização de Chamados de TI

[![Python](https://img.shields.io/badge/Python-3.10+-3776ab?logo=python&logoColor=white)](https://python.org)
[![Flask](https://img.shields.io/badge/Flask-3.x-000?logo=flask)](https://flask.palletsprojects.com)
[![License](https://img.shields.io/badge/License-MIT-green)](LICENSE)

Aplicação web para **priorização inteligente** de chamados de TI. Calcula automaticamente um score ponderado baseado em impacto, urgência e tipo, classificando cada chamado em faixas de criticidade para otimizar o atendimento.

## Índice

- [Funcionalidades](#funcionalidades)
- [Início Rápido](#início-rápido)
- [Arquitetura](#arquitetura)
- [Regra de Priorização](#regra-de-priorização)
- [Rotas e API](#rotas-e-api)
- [Testes](#testes)
- [Estrutura do Projeto](#estrutura-do-projeto)
- [Configuração](#configuração)
- [Contribuindo](#contribuindo)

---

## Funcionalidades

| Recurso | Descrição |
|---------|-----------|
| **Dashboard gerencial** | Cards de KPIs, painel de risco, gráficos por criticidade/tipo/área |
| **Score automático** | Fórmula ponderada com preview em tempo real no formulário |
| **SLA inteligente** | Alertas visuais para chamados próximos ou acima do prazo |
| **CRUD completo** | Criar, editar, alterar status (AJAX) e excluir chamados |
| **Exportação CSV** | Download com BOM UTF-8 para compatibilidade com Excel |
| **API REST** | Endpoints JSON para estatísticas e detalhes de chamados |
| **Filtros combinados** | Área, criticidade e status simultâneamente |
| **Live reload** | Hot-reload via nodemon + livereload em desenvolvimento |

---

## Início Rápido

### Pré-requisitos

- Python 3.10+
- Node.js 18+ (para scripts npm)

### Instalação

```bash
# 1. Clone o repositório
git clone <repo-url>
cd sistema-de-prioriza-ao

# 2. Instale tudo (npm + Python)
npm run install:all

# 3. (Opcional) Popule dados de exemplo
npm run seed

# 4. Inicie o servidor
npm run dev
```

Acesse: **http://127.0.0.1:5000**

### Sem npm

```bash
python -m venv .venv
.venv\Scripts\activate       # Windows
# source .venv/bin/activate  # Linux/Mac
pip install -r requirements.txt
python app.py
```

---

## Arquitetura

```
┌─────────────┐     ┌───────────────┐     ┌──────────────┐
│   Browser   │────▶│  Flask (app)  │────▶│   SQLite DB  │
│  Bootstrap  │◀────│  Jinja2 tmpl  │◀────│  SQLAlchemy  │
│  Chart.js   │     │  WTForms      │     │  instance/   │
└─────────────┘     └───────────────┘     └──────────────┘
```

**Stack tecnológica:**
- **Backend:** Flask + Flask-SQLAlchemy + Flask-WTF
- **Frontend:** Bootstrap 5.3 + Font Awesome 6.4 + Chart.js 4.3
- **Banco:** SQLite (arquivo local em `instance/chamados.db`)
- **Dev:** nodemon + livereload para hot-reload automático

---

## Regra de Priorização

### Fórmula

```
Score = (Impacto × 0.4) + (Urgência × 0.4) + (Tipo × 0.2)
```

### Mapeamentos

| Dimensão | Valor | Peso |
|----------|-------|------|
| **Impacto**  | Baixo=1, Médio=2, Alto=3 | 40% |
| **Urgência** | Baixa=1, Média=2, Alta=3 | 40% |
| **Tipo**     | Requisição=1, Problema=2, Incidente=3 | 20% |

### Faixas de Criticidade

| Score | Criticidade | SLA (dias) |
|-------|-------------|------------|
| ≥ 2.60 | 🔴 Crítica | 1 |
| ≥ 2.00 | 🟠 Alta    | 2 |
| ≥ 1.40 | 🟡 Média   | 4 |
| < 1.40 | 🟢 Baixa   | 7 |

**Range:** 1.00 (mínimo) → 3.00 (máximo). Todas as faixas são alcançáveis.

---

## Rotas e API

### Páginas (HTML)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/` | Dashboard com ranking, KPIs e gráficos |
| GET | `/novo` | Formulário de criação de chamado |
| POST | `/novo` | Salva novo chamado |
| GET | `/editar/<id>` | Formulário de edição |
| POST | `/editar/<id>` | Salva edição (recalcula score) |
| POST | `/excluir/<id>` | Exclui chamado (com confirmação) |
| GET | `/exportar` | Download CSV com todos os chamados |

### API (JSON)

| Método | Rota | Descrição |
|--------|------|-----------|
| GET | `/api/stats` | Estatísticas agrupadas (criticidade, área, tipo, status) |
| GET | `/api/chamado/<id>` | Detalhes completos de um chamado |
| POST | `/status/<id>/<status>` | Altera status via AJAX (retorna JSON) |

### Exemplo de resposta — `/api/stats`

```json
{
  "por_criticidade": {"Crítica": 2, "Alta": 3, "Média": 1, "Baixa": 2},
  "por_area": {"TI": 3, "RH": 1, ...},
  "por_tipo": {"Incidente": 2, "Problema": 3, "Requisição": 3},
  "por_status": {"Aberto": 4, "Em Progresso": 2, ...}
}
```

---

## Testes

Suite de testes com **pytest**, cobrindo modelo, rotas, API, CSV, validação e segurança.

```bash
# Executar todos os testes
npm run test
# ou diretamente:
pytest tests/ -v
```

### Cobertura dos testes

| Categoria | Testes |
|-----------|--------|
| Cálculo de score | Parametrizado com todas as combinações |
| Faixas de criticidade | Limites exatos de cada faixa |
| Propriedade `dias_aberto` | Estados aberto/fechado/intermediário |
| `to_dict()` | Campos obrigatórios e tipos |
| Dashboard | Filtros (área, criticidade, status), ranking |
| Criação (POST /novo) | Validação, score, campos obrigatórios |
| Edição (POST /editar) | Recalcula score, atualiza campos |
| Exclusão (POST /excluir) | Remove sem afetar outros |
| Status AJAX | Todos os status válidos + inválidos |
| API /api/stats | Estrutura JSON, contagens |
| API /api/chamado | Campos, 404 |
| Exportação CSV | Headers, conteúdo, encoding |
| Constantes | Integridade de configuração |
| **Segurança** | XSS, métodos HTTP, IDs inválidos |
| **Validação** | Comprimento mínimo/máximo, campos select |
| **Integridade** | Status padrão, timestamps, from_form |

---

## Estrutura do Projeto

```
sistema-de-prioriza-ao/
├── app.py              # Aplicação Flask (rotas, KPIs, CSV)
├── models.py           # Modelo Chamado (SQLAlchemy) + constantes
├── forms.py            # Formulário WTForms com validações
├── conftest.py         # Config pytest (sys.path)
├── requirements.txt    # Dependências Python
├── package.json        # Scripts npm (dev, test, seed)
├── nodemon.json        # Config hot-reload
├── templates/
│   ├── base.html       # Layout base (navbar, CSS, JS)
│   ├── dashboard.html  # Dashboard principal
│   ├── novo.html       # Formulário de criação
│   └── editar.html     # Formulário de edição
├── scripts/
│   ├── python-runner.js # Runner Node→Python
│   └── seed_sample.py  # Dados de exemplo
├── tests/
│   └── test_suite.py   # Suite completa de testes
└── instance/
    └── chamados.db     # Banco SQLite (gerado automaticamente)
```

---

## Configuração

### Variáveis de Ambiente

| Variável | Padrão | Descrição |
|----------|--------|-----------|
| `SECRET_KEY` | `dev-secret...` | Chave secreta Flask (mude em produção!) |
| `FLASK_DEBUG` | `1` | Modo debug (`0` para produção) |
| `LIVE_RELOAD` | `0` | Ativa livereload (`1` para ativar) |
| `PORT` | `5000` | Porta do servidor |

### Scripts npm

| Comando | Ação |
|---------|------|
| `npm run setup` | Instala dependências Python |
| `npm run dev` | Servidor em modo desenvolvimento |
| `npm start` | Servidor em modo produção local |
| `npm run test` | Executa testes pytest |
| `npm run seed` | Insere dados de exemplo |
| `npm run install:all` | npm install + setup Python |

---

## Contribuindo

1. Crie uma branch a partir de `main`
2. Implemente a mudança com testes
3. Execute `pytest tests/ -v` e garanta que todos passam
4. Abra um Pull Request com descrição clara

### Convenções

- **Código:** PEP 8, docstrings em português
- **Commits:** Mensagens descritivas em português
- **Testes:** Todo novo recurso deve ter testes correspondentes

---

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
