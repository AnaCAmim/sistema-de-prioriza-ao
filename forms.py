from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField, SubmitField
from wtforms.validators import DataRequired
from models import AREAS, STATUS_CHOICES

class ChamadoForm(FlaskForm):
    titulo = StringField('Título', validators=[DataRequired(message='Título é obrigatório')])
    descricao = TextAreaField('Descrição', validators=[DataRequired(message='Descrição é obrigatória')])
    area = SelectField('Área solicitante', choices=[(a, a) for a in AREAS], validators=[DataRequired()])
    impacto = SelectField('Impacto',
                          choices=[('baixo', 'Baixo'), ('medio', 'Médio'), ('alto', 'Alto')],
                          validators=[DataRequired()])
    urgencia = SelectField('Urgência',
                           choices=[('baixa', 'Baixa'), ('media', 'Média'), ('alta', 'Alta')],
                           validators=[DataRequired()])
    tipo = SelectField('Tipo',
                       choices=[('incidente', 'Incidente'), ('requisicao', 'Requisição'), ('problema', 'Problema')],
                       validators=[DataRequired()])
    # Only used in edit form; novo.html hides it (defaults to 'Aberto')
    status = SelectField('Status', choices=[(s, s) for s in STATUS_CHOICES])
    submit = SubmitField('Enviar')
