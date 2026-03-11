from flask_sqlalchemy import SQLAlchemy
from datetime import datetime, timezone

UTC = timezone.utc

db = SQLAlchemy()

IMPACT_VALUES  = {'baixo': 1, 'medio': 2, 'alto': 3}
URGENCY_VALUES = {'baixa': 1, 'media': 2, 'alta': 3}
TYPE_VALUES    = {'incidente': 3, 'requisicao': 1, 'problema': 2}

AREAS          = ['TI', 'RH', 'Financeiro', 'Operações', 'Vendas', 'Administrativo', 'Outro']
STATUS_CHOICES = ['Aberto', 'Em Progresso', 'Aguardando', 'Resolvido', 'Fechado']

class Chamado(db.Model):
    id               = db.Column(db.Integer, primary_key=True)
    titulo           = db.Column(db.String(120), nullable=False)
    descricao        = db.Column(db.Text, nullable=False)
    area             = db.Column(db.String(80), nullable=False)
    impacto          = db.Column(db.String(20), nullable=False)
    urgencia         = db.Column(db.String(20), nullable=False)
    tipo             = db.Column(db.String(20), nullable=False)
    score            = db.Column(db.Float, nullable=False, index=True)
    criticidade      = db.Column(db.String(20), nullable=False)
    status           = db.Column(db.String(20), default='Aberto', nullable=False)
    data_criacao     = db.Column(db.DateTime, default=lambda: datetime.now(UTC), nullable=False)
    data_atualizacao = db.Column(db.DateTime, default=lambda: datetime.now(UTC), onupdate=lambda: datetime.now(UTC))

    # Score = (Impacto×0.4) + (Urgência×0.4) + (Tipo×0.2)
    # Range: 1.0 (baixo/baixa/requisicao) → 3.0 (alto/alta/incidente)
    @classmethod
    def calculate_score(cls, impacto, urgencia, tipo):
        i = IMPACT_VALUES.get(impacto, 1)
        u = URGENCY_VALUES.get(urgencia, 1)
        t = TYPE_VALUES.get(tipo, 1)
        return round((i * 0.4) + (u * 0.4) + (t * 0.2), 2)

    # Thresholds calibrated so all four bands are reachable:
    # 1.0–1.39 → Baixa | 1.4–1.99 → Média | 2.0–2.59 → Alta | >=2.6 → Crítica
    @staticmethod
    def get_criticidade(score):
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
        """Returns number of days since creation, or None for closed/resolved tickets."""
        if self.status in ('Resolvido', 'Fechado'):
            return None
        criacao = self.data_criacao
        if criacao.tzinfo is None:
            criacao = criacao.replace(tzinfo=UTC)
        return (datetime.now(UTC) - criacao).days

    @classmethod
    def from_form(cls, form):
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
            status='Aberto'
        )

    def to_dict(self):
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
            'data_criacao': self.data_criacao.strftime('%d/%m/%Y %H:%M'),
            'dias_aberto': self.dias_aberto,
            'posicao': 0
        }
