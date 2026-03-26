# =============================================================================
# forms.py — Definição do formulário de chamados com validação server-side
# =============================================================================
# Este módulo usa a biblioteca WTForms (integrada ao Flask via Flask-WTF) para
# definir os campos do formulário e suas regras de validação. A validação
# acontece no servidor — se o usuário burlar a validação do navegador,
# o backend ainda garante que os dados estejam corretos antes de salvar.
#
# O WTForms também gera automaticamente a proteção CSRF (Cross-Site Request
# Forgery) por meio do FlaskForm, que adiciona um token oculto ao formulário.
# =============================================================================

from flask_wtf import FlaskForm
# FlaskForm: classe base que integra WTForms com Flask, adicionando
# proteção CSRF automaticamente a todos os formulários.

from wtforms import StringField, TextAreaField, SelectField, SubmitField
# StringField: campo de texto simples (input type=text).
# TextAreaField: campo de texto multilinha (textarea).
# SelectField: campo de seleção (select/dropdown).
# SubmitField: botão de envio do formulário.

from wtforms.validators import DataRequired, Length
# DataRequired: garante que o campo não seja enviado vazio.
# Length: valida o número mínimo e máximo de caracteres do texto.

from models import AREAS, STATUS_CHOICES
# Importa as listas de opções do módulo de modelos para manter consistência
# entre o formulário e o banco de dados (mesmas áreas e status válidos).


class ChamadoForm(FlaskForm):
    """Formulário para criação e edição de chamados de TI.
    Cada campo define seu tipo, rótulo (label) e validações obrigatórias.
    Quando validate_on_submit() é chamado no app.py, todos os validadores
    listados aqui são executados automaticamente."""

    # Campo de título: texto curto que resume o problema
    # Validações: obrigatório, entre 3 e 120 caracteres
    titulo = StringField('Título', validators=[
        DataRequired(message='Título é obrigatório'),
        Length(min=3, max=120, message='Título deve ter entre 3 e 120 caracteres'),
    ])

    # Campo de descrição: texto longo com detalhes do problema
    # Validações: obrigatório, entre 10 e 2000 caracteres
    descricao = TextAreaField('Descrição', validators=[
        DataRequired(message='Descrição é obrigatória'),
        Length(min=10, max=2000, message='Descrição deve ter entre 10 e 2000 caracteres'),
    ])

    # Área solicitante: dropdown com as áreas da empresa
    # As opções são geradas como tuplas (valor, texto) a partir da lista AREAS
    area = SelectField('Área solicitante', choices=[(a, a) for a in AREAS], validators=[DataRequired()])

    # Impacto: quantas pessoas ou processos são afetados pelo problema
    impacto = SelectField('Impacto',
                          choices=[('baixo', 'Baixo'), ('medio', 'Médio'), ('alto', 'Alto')],
                          validators=[DataRequired()])

    # Urgência: velocidade necessária para resolver o problema
    urgencia = SelectField('Urgência',
                           choices=[('baixa', 'Baixa'), ('media', 'Média'), ('alta', 'Alta')],
                           validators=[DataRequired()])

    # Tipo do chamado:
    # - Incidente: falha que interrompe um serviço (mais urgente)
    # - Problema: investigação de causa raiz de incidentes recorrentes
    # - Requisição: solicitação de algo novo (equipamento, acesso, etc.)
    tipo = SelectField('Tipo',
                       choices=[('incidente', 'Incidente'), ('requisicao', 'Requisição'), ('problema', 'Problema')],
                       validators=[DataRequired()])

    # Status: usado apenas no formulário de edição.
    # No formulário de criação (novo.html), este campo fica oculto e o
    # status padrão é definido como 'Aberto' automaticamente no app.py.
    status = SelectField('Status', choices=[(s, s) for s in STATUS_CHOICES])

    # Botão de envio do formulário
    submit = SubmitField('Enviar')
