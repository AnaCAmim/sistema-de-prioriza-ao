from datetime import datetime, timedelta, timezone
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from app import app, db, init_db
from models import Chamado

UTC = timezone.utc

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


def run_seed() -> None:
    with app.app_context():
        init_db()
        inserted = 0

        for item in SAMPLES:
            exists = Chamado.query.filter_by(titulo=item["titulo"]).first()
            if exists:
                continue

            score = Chamado.calculate_score(item["impacto"], item["urgencia"], item["tipo"])
            criticidade = Chamado.get_criticidade(score)
            criado_em = datetime.now(UTC) - timedelta(days=item["dias"])

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

        db.session.commit()
        total = Chamado.query.count()
        print(f"Chamados inseridos: {inserted}")
        print(f"Total no banco: {total}")


if __name__ == "__main__":
    run_seed()
