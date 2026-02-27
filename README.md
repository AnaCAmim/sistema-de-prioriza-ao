# 📊 Sistema de Priorização de Chamados

Um sistema web moderno e inteligente para priorizar chamados de TI com base em análise de dados, impacto e urgência.

## 🎯 Funcionalidades

### MVP - Fase 1
✅ **Cadastro de Chamados**
- Título, descrição, área solicitante
- Classificação por impacto (baixo/médio/alto)
- Classificação por urgência (baixa/média/alta)
- Tipo de chamado (incidente/requisição/problema)

✅ **Motor de Cálculo Inteligente**
- Fórmula ponderada: **Score = (Impacto × 0,4) + (Urgência × 0,4) + (Tipo × 0,2)**
- Classificação automática de criticidade (Crítica/Alta/Média/Baixa)
- Ranking ordenado por prioridade

✅ **Dashboard Gerencial Moderno**
- Visualização em tempo real de chamados ordenados por prioridade
- Cards com estatísticas: Total, Abertos, Críticos, Altos
- Gráfico de distribuição por criticidade (Doughnut)
- Gráfico de chamados por área (Bar Chart)
- Filtros por: Área, Criticidade, Status
- Tabela interativa com ranking de posição

✅ **Gerenciamento de Chamados**
- Edição de chamados cadastrados
- Atualização de status (Aberto → Em Progresso → Aguardando → Resolvido → Fechado)
- Visualização de detalhes em modal
- Histórico de criação e atualização

✅ **APIs RESTful**
- GET `/api/stats` - Retorna estatísticas gerenciais
- GET `/api/chamado/<id>` - Detalhes de chamado específico
- POST `/status/<id>/<status>` - Atualizar status

## 🚀 Tecnologia Stack

**Backend:**
- Flask (Python Web Framework)
- SQLAlchemy (ORM)
- Flask-WTF (Validação de formulários)

**Frontend:**
- Bootstrap 5.3 (Design responsivo)
- Chart.js (Gráficos interativos)
- FontAwesome 6.4 (Ícones)

**Database:**
- SQLite (Desenvolvimento)

## 📥 Instalação

### Pré-requisitos
- Python 3.8+
- pip

### Setup
```bash
# 1. Clonar/Entrar no diretório
cd "sistema de priorizacao"

# 2. Criar ambiente virtual (opcional)
python -m venv venv
venv\Scripts\activate  # Windows
# ou: source venv/bin/activate  # Linux/Mac

# 3. Instalar dependências
pip install -r requirements.txt

# 4. Executar a aplicação
python app.py
```

A aplicação estará disponível em: **http://127.0.0.1:5000**

## 📋 Estrutura do Projeto

```
sistema de priorizacao/
├── app.py                    # Aplicação Flask principal
├── models.py                 # Modelos de dados (Chamado)
├── forms.py                  # Formulários WTForms
├── requirements.txt          # Dependências Python
├── chamados.db              # Database SQLite (criado automaticamente)
└── templates/
    ├── base.html            # Template base com navbar
    ├── dashboard.html       # Dashboard com gráficos e filtros
    ├── novo.html           # Formulário de novo chamado
    └── editar.html         # Formulário de edição
```

## 🧮 Fórmula de Cálculo

```
Score = (Impacto × 0,4) + (Urgência × 0,4) + (Tipo × 0,2)

Valores:
- Impacto: Baixo=1, Médio=2, Alto=3
- Urgência: Baixa=1, Média=2, Alta=3
- Tipo: Requisição=1, Problema=2, Incidente=3

Criticidade (baseada em Score):
- Score ≥ 2.6: CRÍTICA 🔴
- Score ≥ 1.8: ALTA 🟠
- Score ≥ 1.0: MÉDIA 🟡
- Score < 1.0: BAIXA 🟢
```

## 📊 Exemplo de Dados

| Chamado | Impacto | Urgência | Tipo | Score | Criticidade |
|---------|---------|----------|------|-------|-------------|
| Servidor Down | 3 | 3 | Incidente | 2.8 | CRÍTICA |
| Email não funciona | 2 | 2 | Incidente | 2.2 | ALTA |
| Solicitar Software | 1 | 1 | Requisição | 0.8 | BAIXA |

## 🎨 Customização

### Adicionar novas áreas
Editar `models.py`, linha com `AREAS`:
```python
AREAS = ['TI', 'RH', 'Financeiro', 'Sua Nova Área']
```

### Alterar pesos da fórmula
Editar `models.py`, método `calculate_score()`:
```python
score = (i * 0.3) + (u * 0.5) + (t * 0.2)  # Novo peso
```

### Ajustar limiares de criticidade
Editar `models.py`, método `get_criticidade()`:
```python
if score >= 3.0:
    return 'Crítica'
```

## 🔮 Roadmap (Futuras Versões)

- [ ] Autenticação e controle de acesso
- [ ] Integração com email para notificações
- [ ] Dashboard com mais KPIs (tempo médio de atendimento, SLA)
- [ ] Exportação de relatórios (PDF/Excel)
- [ ] Mobile app
- [ ] Sistema de atribuição a técnicos
- [ ] Histórico de mudanças de status
- [ ] Integração com LDAP/Active Directory
- [ ] Análise de padrões e tendências

## 📞 Suporte

Para dúvidas ou sugestões, entre em contato!

---

**Desenvolvido com ❤️ para otimizar a gestão de chamados**
