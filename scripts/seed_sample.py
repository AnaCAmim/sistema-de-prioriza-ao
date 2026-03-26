# ============================================================================
# seed_sample.py — Script de carga inicial (seed) do banco de dados
# ============================================================================
# Este script popula o banco SQLite com chamados de exemplo, permitindo
# demonstrar o sistema já com dados reais na apresentação.
#
# Como funciona:
#   1. Ajusta o sys.path para encontrar o módulo 'app' (que está um nível
#      acima da pasta scripts/).
#   2. Importa a aplicação Flask e o modelo Chamado.
#   3. Define uma lista SAMPLES com 8 chamados variados — cobrindo
#      diferentes áreas, níveis de impacto/urgência e status.
#   4. Para cada amostra, calcula score e criticidade usando os métodos
#      do próprio modelo, evitando duplicatas pelo título.
#
# Uso:
#   python scripts/seed_sample.py      (direto)
#   npm run seed                        (via package.json + python-runner)
# ============================================================================

from datetime import datetime, timedelta, timezone
import os
import sys

# --------------------------------------------------------------------------
# Configuração do caminho de importação
# --------------------------------------------------------------------------
# Como este arquivo fica dentro de scripts/, precisamos subir um nível
# para que o Python encontre app.py e models.py.
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

# Importações do projeto: a instância Flask, o banco de dados e o modelo
from app import app, db, init_db
from models import Chamado

# Fuso horário UTC — usado para preencher as datas de criação
UTC = timezone.utc

# --------------------------------------------------------------------------
# Dados de exemplo
# --------------------------------------------------------------------------
# Cada dicionário representa um chamado que será inserido no banco.
# O campo "dias" define quantos dias atrás o chamado foi "aberto",
# simulando dados com datas variadas para os gráficos ficarem mais
# interessantes na demonstração.
SAMPLES = [
    {
        "titulo": "Servidor de arquivos indisponivel",
        "descricao": "Usuarios do financeiro sem acesso a pasta compartilhada.",
        "area": "Financeiro",
        "impacto": "alto",
        "urgencia": "alta",
        "tipo": "incidente",
        "status": "Em Progresso",
        "dias": 3,
    },
    {
        "titulo": "VPN intermitente para equipe comercial",
        "descricao": "Conexao cai a cada 10 minutos durante visitas externas.",
        "area": "Vendas",
        "impacto": "alto",
        "urgencia": "media",
        "tipo": "problema",
        "status": "Aberto",
        "dias": 2,
    },
    {
        "titulo": "Notebook novo para analista de RH",
        "descricao": "Solicitacao de equipamento para nova contratacao.",
        "area": "RH",
        "impacto": "baixo",
        "urgencia": "baixa",
        "tipo": "requisicao",
        "status": "Aguardando",
        "dias": 1,
    },
    {
        "titulo": "Falha no envio de e-mails corporativos",
        "descricao": "Mensagens retornando com erro SMTP para todo o dominio.",
        "area": "Administrativo",
        "impacto": "alto",
        "urgencia": "alta",
        "tipo": "incidente",
        "status": "Aberto",
        "dias": 1,
    },
    {
        "titulo": "Lentidao no ERP em horario de pico",
        "descricao": "Tela de faturamento demora mais de 20 segundos para abrir.",
        "area": "Operações",
        "impacto": "medio",
        "urgencia": "alta",
        "tipo": "problema",
        "status": "Em Progresso",
        "dias": 5,
    },
    {
        "titulo": "Criacao de acesso para estagiario",
        "descricao": "Conta no AD, e-mail e permissao no sistema interno.",
        "area": "Administrativo",
        "impacto": "baixo",
        "urgencia": "media",
        "tipo": "requisicao",
        "status": "Resolvido",
        "dias": 0,
    },
    {
        "titulo": "Queda de link secundario da filial",
        "descricao": "Filial operando sem redundancia de internet.",
        "area": "TI",
        "impacto": "medio",
        "urgencia": "media",
        "tipo": "incidente",
        "status": "Fechado",
        "dias": 0,
    },
    {
        "titulo": "Impressoras da recepcao sem fila",
        "descricao": "Fila de impressao travada para documentos de atendimento.",
        "area": "Administrativo",
        "impacto": "medio",
        "urgencia": "baixa",
        "tipo": "problema",
        "status": "Aberto",
        "dias": 4,
    },
]


# --------------------------------------------------------------------------
# Função principal de seed
# --------------------------------------------------------------------------
def run_seed() -> None:
    """Insere os chamados de exemplo no banco, sem duplicar registros."""

    # Abre o contexto da aplicação Flask — necessário para usar db.session
    with app.app_context():
        # Garante que a tabela existe antes de tentar inserir
        init_db()
        inserted = 0

        for item in SAMPLES:
            # Verifica se já existe um chamado com o mesmo título para
            # evitar duplicatas caso o seed seja rodado mais de uma vez.
            exists = Chamado.query.filter_by(titulo=item["titulo"]).first()
            if exists:
                continue

            # Calcula score e criticidade usando os métodos estáticos
            # do modelo — mesma lógica usada nas rotas web.
            score = Chamado.calculate_score(item["impacto"], item["urgencia"], item["tipo"])
            criticidade = Chamado.get_criticidade(score)

            # Simula uma data de criação no passado, usando o campo "dias".
            # Exemplo: dias=3 → criado 3 dias atrás.
            criado_em = datetime.now(UTC) - timedelta(days=item["dias"])

            # Cria a instância do modelo com todos os campos preenchidos
            chamado = Chamado(
                titulo=item["titulo"],
                descricao=item["descricao"],
                area=item["area"],
                impacto=item["impacto"],
                urgencia=item["urgencia"],
                tipo=item["tipo"],
                score=score,
                criticidade=criticidade,
                status=item["status"],
                data_criacao=criado_em,
                data_atualizacao=criado_em,
            )
            db.session.add(chamado)
            inserted += 1

        # Salva tudo no banco de uma vez (mais eficiente)
        db.session.commit()

        # Exibe resumo no terminal para confirmar que funcionou
        total = Chamado.query.count()
        print(f"Chamados inseridos: {inserted}")
        print(f"Total no banco: {total}")


# --------------------------------------------------------------------------
# Ponto de entrada — permite rodar diretamente: python seed_sample.py
# --------------------------------------------------------------------------
if __name__ == "__main__":
    run_seed()
