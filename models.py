# =============================================================================
# models.py — Modelo de dados (ORM) da aplicação
# =============================================================================
# Este módulo define a estrutura da tabela "chamado" no banco de dados usando
# SQLAlchemy como ORM (Object-Relational Mapping). O ORM permite trabalhar
# com registros do banco como se fossem objetos Python, sem escrever SQL puro.
#
# Responsabilidades deste módulo:
# - Definir os campos (colunas) de cada chamado
# - Implementar o algoritmo de cálculo do score de priorização
# - Classificar os chamados em faixas de criticidade
# - Converter registros para dicionário (serialização para JSON)
# =============================================================================

from flask_sqlalchemy import SQLAlchemy
# SQLAlchemy: biblioteca de ORM que mapeia classes Python para tabelas SQL.
# Flask-SQLAlchemy integra o SQLAlchemy com o Flask de forma simplificada.

from datetime import datetime, timezone
# datetime: manipulação de datas e horários.
# timezone: referência ao fuso UTC para padronização.

# Fuso horário UTC — usado para que todas as datas sejam consistentes,
# independente do fuso do servidor onde a aplicação está rodando.
UTC = timezone.utc

# Instância global do SQLAlchemy. Será vinculada à aplicação Flask
# no app.py por meio de db.init_app(app).
db = SQLAlchemy()

# ---------------------------------------------------------------------------
# Dicionários de mapeamento: convertem nomes textuais para valores numéricos.
# Esses valores são usados na fórmula de cálculo do score.
# ---------------------------------------------------------------------------

# Impacto: quantas pessoas/processos são afetados
# baixo=1, medio=2, alto=3
IMPACT_VALUES  = {'baixo': 1, 'medio': 2, 'alto': 3}

# Urgência: quão rápido precisa ser resolvido
# baixa=1, media=2, alta=3
URGENCY_VALUES = {'baixa': 1, 'media': 2, 'alta': 3}

# Tipo do chamado: incidente (falha, emergência) tem peso maior
# requisicao=1 (mais leve), problema=2, incidente=3 (mais grave)
TYPE_VALUES    = {'incidente': 3, 'requisicao': 1, 'problema': 2}

# Lista de áreas solicitantes disponíveis no sistema
AREAS          = ['TI', 'RH', 'Financeiro', 'Operações', 'Vendas', 'Administrativo', 'Outro']

# Lista dos status possíveis para um chamado, em ordem de fluxo
STATUS_CHOICES = ['Aberto', 'Em Progresso', 'Aguardando', 'Resolvido', 'Fechado']


# =============================================================================
# Modelo Chamado — representa a tabela principal do sistema
# =============================================================================
class Chamado(db.Model):
    """Modelo que representa um chamado de TI no banco de dados.
    Cada instância corresponde a uma linha na tabela 'chamado' do SQLite."""

    # Chave primária: identificador único auto-incrementável
    id               = db.Column(db.Integer, primary_key=True)

    # Título resumido do chamado (ex.: "Servidor de e-mail fora do ar")
    titulo           = db.Column(db.String(120), nullable=False)

    # Descrição detalhada do problema ou solicitação
    descricao        = db.Column(db.Text, nullable=False)

    # Área que abriu o chamado (ex.: TI, RH, Financeiro)
    area             = db.Column(db.String(80), nullable=False)

    # Nível de impacto: 'baixo', 'medio' ou 'alto'
    impacto          = db.Column(db.String(20), nullable=False)

    # Nível de urgência: 'baixa', 'media' ou 'alta'
    urgencia         = db.Column(db.String(20), nullable=False)

    # Tipo: 'incidente', 'requisicao' ou 'problema'
    tipo             = db.Column(db.String(20), nullable=False)

    # Score calculado pela fórmula de priorização (valor entre 1.0 e 3.0).
    # O index=True cria um índice no banco para acelerar a ordenação por score.
    score            = db.Column(db.Float, nullable=False, index=True)

    # Faixa de criticidade derivada do score: Crítica, Alta, Média ou Baixa
    criticidade      = db.Column(db.String(20), nullable=False)

    # Status atual do chamado no fluxo de atendimento
    status           = db.Column(db.String(20), default='Aberto', nullable=False)

    # Data de criação: preenchida automaticamente com o horário UTC atual
    data_criacao     = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)

    # Data da última atualização: preenchida na criação e atualizada automaticamente
    # pelo SQLAlchemy sempre que o registro é modificado (onupdate)
    data_atualizacao = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # -------------------------------------------------------------------------
    # Método de cálculo do score de priorização
    # -------------------------------------------------------------------------
    # Fórmula: Score = (Impacto × 0.4) + (Urgência × 0.4) + (Tipo × 0.2)
    #
    # O impacto e a urgência têm o mesmo peso (40% cada), pois são os fatores
    # mais relevantes para decidir a prioridade. O tipo contribui com 20%,
    # diferenciando incidentes (mais urgentes) de requisições (mais tranquilas).
    #
    # Range possível: 1.0 (baixo + baixa + requisição) até 3.0 (alto + alta + incidente)
    # -------------------------------------------------------------------------
    @classmethod
    def calculate_score(cls, impacto, urgencia, tipo):
        """Calcula o score numérico de priorização a partir dos três parâmetros.
        Valores desconhecidos recebem fallback de 1 (menor peso possível)."""
        i = IMPACT_VALUES.get(impacto, 1)    # Converte texto para número
        u = URGENCY_VALUES.get(urgencia, 1)
        t = TYPE_VALUES.get(tipo, 1)
        return round((i * 0.4) + (u * 0.4) + (t * 0.2), 2)

    # -------------------------------------------------------------------------
    # Classificação em faixas de criticidade
    # -------------------------------------------------------------------------
    # Os limites foram calibrados para que todas as quatro faixas sejam
    # alcançáveis com combinações reais dos campos:
    #   Score >= 2.60 → Crítica (atenção imediata)
    #   Score >= 2.00 → Alta    (resolver em poucas horas)
    #   Score >= 1.40 → Média   (resolver em dias)
    #   Score <  1.40 → Baixa   (pode aguardar)
    # -------------------------------------------------------------------------
    @staticmethod
    def get_criticidade(score):
        """Retorna o rótulo de criticidade correspondente ao score informado."""
        if score >= 2.6:
            return 'Crítica'
        elif score >= 2.0:
            return 'Alta'
        elif score >= 1.4:
            return 'Média'
        else:
            return 'Baixa'

    @property
    def dias_aberto(self):
        """Calcula quantos dias o chamado está aberto desde a criação.
        Retorna None para chamados já finalizados (Resolvido/Fechado),
        pois não faz sentido contar dias de um chamado encerrado."""
        if self.status in ('Resolvido', 'Fechado'):
            return None
        criacao = self.data_criacao
        # Adiciona timezone UTC caso a data esteja sem fuso (dados antigos/migrados)
        if criacao.tzinfo is None:
            criacao = criacao.replace(tzinfo=UTC)
        return (datetime.now(UTC) - criacao).days

    @classmethod
    def from_form(cls, form):
        """Cria uma nova instância de Chamado a partir dos dados de um formulário.
        Calcula automaticamente o score e a criticidade antes de retornar o objeto.
        Este método é um "factory method" — encapsula a lógica de construção."""
        score = cls.calculate_score(form.impacto.data, form.urgencia.data, form.tipo.data)
        criticidade = cls.get_criticidade(score)
        return cls(
            titulo=form.titulo.data,
            descricao=form.descricao.data,
            area=form.area.data,
            impacto=form.impacto.data,
            urgencia=form.urgencia.data,
            tipo=form.tipo.data,
            score=score,
            criticidade=criticidade,
            status='Aberto'     # Todo chamado novo nasce com status 'Aberto'
        )

    def to_dict(self):
        """Converte o chamado para dicionário Python, pronto para serialização JSON.
        É usado pela API (/api/chamado/<id>) para enviar dados ao frontend
        e pelo modal de detalhes no dashboard."""
        return {
            'id': self.id,
            'titulo': self.titulo,
            'descricao': self.descricao,
            'area': self.area,
            'impacto': self.impacto,
            'urgencia': self.urgencia,
            'tipo': self.tipo,
            'score': self.score,
            'criticidade': self.criticidade,
            'status': self.status,
            # Formata a data no padrão brasileiro (dd/mm/aaaa hh:mm)
            'data_criacao': self.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'data_atualizacao': self.data_atualizacao.strftime('%d/%m/%Y %H:%M') if self.data_atualizacao else None,
            'dias_aberto': self.dias_aberto,
        }
