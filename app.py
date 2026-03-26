# =============================================================================
# app.py — Arquivo principal da aplicação Flask
# =============================================================================
# Este módulo concentra todas as rotas (endpoints) do sistema de priorização
# de chamados de TI. Ele funciona como o "controlador" do padrão MVC:
# recebe as requisições HTTP, interage com o banco de dados por meio do
# modelo (models.py) e devolve páginas HTML renderizadas pelos templates.
# =============================================================================

# ---------------------------------------------------------------------------
# Importações de bibliotecas e módulos internos
# ---------------------------------------------------------------------------
from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, Response
# Flask: microframework web que gerencia rotas, templates e sessões.
# render_template: renderiza arquivos HTML usando o motor Jinja2.
# redirect / url_for: redireciona o navegador para outra rota.
# request: objeto que encapsula os dados da requisição HTTP (query string, form).
# jsonify: converte dicionários Python em respostas JSON para o frontend.
# flash: exibe mensagens temporárias entre requisições (ex.: "Chamado criado!").
# Response: permite construir respostas HTTP personalizadas (usada no CSV).

from flask_wtf.csrf import generate_csrf
# generate_csrf: gera o token CSRF que protege formulários contra ataques
# de falsificação de requisição entre sites (Cross-Site Request Forgery).

from models import db, Chamado, AREAS, STATUS_CHOICES
# db: instância do SQLAlchemy que gerencia a conexão com o banco de dados.
# Chamado: modelo ORM que representa a tabela de chamados no banco.
# AREAS: lista de áreas disponíveis (TI, RH, Financeiro, etc.).
# STATUS_CHOICES: lista dos status possíveis de um chamado.

from forms import ChamadoForm
# ChamadoForm: formulário WTForms com validação server-side para criação/edição.

from datetime import datetime, timezone
import csv      # Módulo padrão para leitura/escrita de arquivos CSV.
import io       # Módulo para manipular streams em memória (StringIO).
import os       # Módulo para interagir com o sistema operacional (caminhos, variáveis de ambiente).

# Fuso horário UTC, utilizado para padronizar datas e evitar problemas com fuso local.
UTC = timezone.utc

# ---------------------------------------------------------------------------
# Configuração de caminhos e criação da aplicação Flask
# ---------------------------------------------------------------------------
# Resolve o caminho absoluto baseado na localização deste arquivo,
# garantindo que o banco SQLite seja sempre encontrado corretamente,
# independentemente do diretório de trabalho usado ao executar o projeto.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH  = os.path.join(_BASE_DIR, 'instance', 'chamados.db')
os.makedirs(os.path.join(_BASE_DIR, 'instance'), exist_ok=True)

# Cria a instância da aplicação Flask.
# O Flask usa o __name__ para localizar os diretórios de templates e static.
app = Flask(__name__)

# URI de conexão com o banco de dados SQLite.
# O SQLAlchemy interpreta esse endereço para saber qual driver e arquivo usar.
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{_DB_PATH}'

# Chave secreta usada para assinar cookies de sessão e tokens CSRF.
# Em produção, essa chave deve ser definida como variável de ambiente.
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-secret-change-in-production')

# Desativa o rastreamento de modificações do SQLAlchemy, que consumiria memória
# desnecessária. A funcionalidade de "event system" não é usada neste projeto.
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# Inicializa a extensão SQLAlchemy vinculando-a à aplicação Flask.
db.init_app(app)

# Flag interna que controla se as tabelas do banco já foram criadas nesta execução.
app.config['_DB_READY'] = False


@app.context_processor
def inject_csrf_token():
    """Injeta a função geradora de token CSRF em todos os templates.
    Isso permite usar {{ csrf_token() }} em qualquer formulário HTML
    sem precisar importar manualmente no Jinja2."""
    return {'csrf_token': generate_csrf}


def init_db():
    """Inicializa o banco de dados criando todas as tabelas definidas nos modelos.
    Também percorre os registros existentes e recalcula a criticidade de cada um,
    caso os limites (thresholds) tenham sido alterados no código. Dessa forma,
    após atualizar a lógica de faixas, basta reiniciar o servidor para corrigir
    automaticamente todos os registros antigos."""
    with app.app_context():
        db.create_all()
        # Percorre todos os chamados e verifica se a criticidade precisa de atualização
        changed = 0
        for c in Chamado.query.all():
            novo = Chamado.get_criticidade(c.score)
            if c.criticidade != novo:
                c.criticidade = novo
                changed += 1
        if changed:
            db.session.commit()
        app.config['_DB_READY'] = True


@app.before_request
def ensure_db_ready():
    """Garante que as tabelas existam antes de processar qualquer requisição.
    Funciona como um fallback caso init_db() não tenha sido chamada
    (por exemplo, durante testes automatizados). O flag '_DB_READY' evita
    que db.create_all() seja executado repetidamente a cada requisição."""
    if not app.config.get('_DB_READY'):
        db.create_all()
        app.config['_DB_READY'] = True


# =============================================================================
# ROTA: Dashboard principal (GET /)
# =============================================================================
# Exibe a página principal com estatísticas, KPIs de risco, gráficos e a
# tabela de ranking de chamados ordenada por score (do maior para o menor).
# Aceita filtros opcionais via query string: ?area=TI&criticidade=Crítica&status=Aberto
# =============================================================================
@app.route('/')
def index():
    # Lê os parâmetros de filtro da URL (query string)
    area_filter       = request.args.get('area', '')
    criticidade_filter = request.args.get('criticidade', '')
    status_filter     = request.args.get('status', '')

    # Consulta principal: ordena por score decrescente.
    # Em caso de empate no score, prioriza o chamado mais antigo (data_criacao ASC).
    query = Chamado.query.order_by(Chamado.score.desc(), Chamado.data_criacao.asc())

    # Aplica os filtros selecionados pelo usuário, se houver
    if area_filter and area_filter != 'Todas':
        query = query.filter_by(area=area_filter)
    if criticidade_filter and criticidade_filter != 'Todas':
        query = query.filter_by(criticidade=criticidade_filter)
    if status_filter and status_filter != 'Todos':
        query = query.filter_by(status=status_filter)

    # Executa a consulta e atribui a posição no ranking a cada chamado
    chamados = query.all()
    for idx, c in enumerate(chamados, 1):
        c.posicao = idx  # Posição no ranking (1 = mais prioritário)

    # Estatísticas gerais para os cards de resumo no topo da página
    total = Chamado.query.count()
    stats = {
        'total':       total,
        'abertos':     Chamado.query.filter_by(status='Aberto').count(),
        'em_progresso':Chamado.query.filter_by(status='Em Progresso').count(),
        'critica':     Chamado.query.filter_by(criticidade='Crítica').count(),
        'alta':        Chamado.query.filter_by(criticidade='Alta').count(),
        'resolvidos':  Chamado.query.filter(Chamado.status.in_(['Resolvido', 'Fechado'])).count(),
    }

    # ---------------------------------------------------------------------------
    # Cálculo dos KPIs (Key Performance Indicators) gerenciais
    # ---------------------------------------------------------------------------
    # Limites de SLA em dias para cada faixa de criticidade.
    # Ex.: chamados Críticos devem ser resolvidos em até 1 dia.
    sla_limites = {
        'Crítica': 1,
        'Alta': 2,
        'Média': 4,
        'Baixa': 7,
    }

    # Pesos de criticidade usados no cálculo do Índice de Risco.
    # Quanto maior o peso, mais o chamado contribui para o risco total.
    criticidade_peso = {
        'Crítica': 4,
        'Alta': 3,
        'Média': 2,
        'Baixa': 1,
    }

    # Filtra apenas chamados que ainda não foram resolvidos ou fechados
    abertos = [c for c in Chamado.query.all() if c.status not in ('Resolvido', 'Fechado')]
    total_abertos = len(abertos)

    # Contadores para os indicadores de SLA
    sla_estourado = 0   # Chamados que ultrapassaram o prazo de SLA
    proximos_sla = 0    # Chamados próximos de estourar o SLA
    soma_idade = 0      # Soma total de dias abertos (para calcular média)
    soma_peso = 0       # Soma ponderada dos pesos de criticidade

    for c in abertos:
        dias = c.dias_aberto or 0
        limite = sla_limites.get(c.criticidade, 4)
        soma_idade += dias
        soma_peso += criticidade_peso.get(c.criticidade, 1)
        # Verifica se o chamado estourou o SLA
        if dias > limite:
            sla_estourado += 1
        # Verifica se está próximo do limite (no limite ou faltando 1 dia)
        elif dias == limite or dias == max(limite - 1, 0):
            proximos_sla += 1

    # Idade média: tempo médio (em dias) que os chamados abertos existem
    idade_media = round(soma_idade / total_abertos, 1) if total_abertos else 0

    # Índice de risco: percentual que indica a gravidade geral dos chamados abertos.
    # Fórmula: (soma dos pesos de criticidade) / (total de abertos × peso máximo) × 100
    # Se todos os chamados forem Críticos, o índice será 100%.
    indice_risco = round((soma_peso / (total_abertos * 4)) * 100, 1) if total_abertos else 0

    # Taxa de SLA estourado: percentual de chamados que já passaram do prazo
    taxa_sla_estourado = round((sla_estourado / total_abertos) * 100, 1) if total_abertos else 0

    # Dicionário com todos os KPIs que serão exibidos no painel gerencial
    kpis = {
        'total_abertos': total_abertos,
        'sla_estourado': sla_estourado,
        'proximos_sla': proximos_sla,
        'idade_media': idade_media,
        'indice_risco': indice_risco,
        'taxa_sla_estourado': taxa_sla_estourado,
    }

    # Renderiza o template do dashboard passando todos os dados necessários
    return render_template(
        'dashboard.html',
        chamados=chamados,
        total_filtrado=len(chamados),
        total_geral=total,
        areas=AREAS,
        status_choices=STATUS_CHOICES,
        stats=stats,
        kpis=kpis,
        sla_limites=sla_limites,
        selected_area=area_filter,
        selected_criticidade=criticidade_filter,
        selected_status=status_filter,
    )


# =============================================================================
# ROTA: Criação de novo chamado (GET e POST /novo)
# =============================================================================
# GET: exibe o formulário em branco para o usuário preencher.
# POST: recebe os dados preenchidos, valida e, se tudo estiver correto,
# salva o chamado no banco e redireciona para o dashboard.
# =============================================================================
@app.route('/novo', methods=['GET', 'POST'])
def novo_chamado():
    form = ChamadoForm()
    # No formulário de criação, o campo status não é exibido ao usuário.
    # Aqui forçamos o valor 'Aberto' como padrão ao enviar o formulário,
    # pois todo chamado novo nasce com esse status.
    if request.method == 'POST' and not form.status.data:
        form.status.data = 'Aberto'

    # validate_on_submit() verifica o token CSRF e aplica todos os validadores
    # definidos em forms.py (campo obrigatório, tamanho mínimo/máximo, etc.)
    if form.validate_on_submit():
        # Cria a instância do modelo a partir dos dados do formulário
        chamado = Chamado.from_form(form)
        db.session.add(chamado)    # Adiciona ao contexto da sessão do banco
        db.session.commit()        # Persiste no banco de dados (grava no disco)

        # Exibe uma mensagem flash de sucesso que aparecerá no topo da próxima página
        flash(
            f'✅ Chamado "{chamado.titulo}" enviado com sucesso! '
            f'Score: {chamado.score:.2f} | Criticidade: {chamado.criticidade}',
            'success'
        )
        return redirect(url_for('index'))  # Redireciona para o dashboard

    # Se for GET ou se a validação falhar, renderiza o formulário (com erros, se houver)
    return render_template('novo.html', form=form)


# =============================================================================
# ROTA: Edição de chamado existente (GET e POST /editar/<id>)
# =============================================================================
# GET: carrega os dados atuais do chamado e preenche o formulário.
# POST: recebe as alterações, valida, recalcula o score e atualiza no banco.
# =============================================================================
@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_chamado(id):
    # Busca o chamado pelo ID. Se não existir, retorna 404 automaticamente.
    chamado = db.get_or_404(Chamado, id)
    form = ChamadoForm()

    if form.validate_on_submit():
        # Atualiza cada campo do modelo com os valores recebidos do formulário
        chamado.titulo           = form.titulo.data
        chamado.descricao        = form.descricao.data
        chamado.area             = form.area.data
        chamado.impacto          = form.impacto.data
        chamado.urgencia         = form.urgencia.data
        chamado.tipo             = form.tipo.data
        chamado.status           = form.status.data
        # Recalcula o score com base nos novos valores de impacto, urgência e tipo
        chamado.score            = Chamado.calculate_score(form.impacto.data, form.urgencia.data, form.tipo.data)
        # Reclassifica a criticidade com base no novo score
        chamado.criticidade      = Chamado.get_criticidade(chamado.score)
        # Atualiza a data de modificação para o momento atual
        chamado.data_atualizacao = datetime.now(UTC)
        db.session.commit()

        flash(
            f'Chamado atualizado! Novo score: {chamado.score:.2f} | Criticidade: {chamado.criticidade}',
            'success'
        )
        return redirect(url_for('index'))

    elif request.method == 'GET':
        # Preenche o formulário com os dados atuais para o usuário poder editar
        form.titulo.data   = chamado.titulo
        form.descricao.data = chamado.descricao
        form.area.data     = chamado.area
        form.impacto.data  = chamado.impacto
        form.urgencia.data = chamado.urgencia
        form.tipo.data     = chamado.tipo
        form.status.data   = chamado.status

    return render_template('editar.html', form=form, chamado=chamado)


# =============================================================================
# ROTA: Exclusão de chamado (POST /excluir/<id>)
# =============================================================================
# Remove permanentemente o chamado do banco de dados.
# Aceita apenas POST para evitar exclusões acidentais via navegação de URL.
# =============================================================================
@app.route('/excluir/<int:id>', methods=['POST'])
def excluir_chamado(id):
    chamado = db.get_or_404(Chamado, id)
    titulo = chamado.titulo              # Guarda o título antes de deletar
    db.session.delete(chamado)           # Remove o registro da sessão
    db.session.commit()                  # Confirma a remoção no banco
    flash(f'Chamado "{titulo}" excluído.', 'warning')
    return redirect(url_for('index'))


# =============================================================================
# ROTA: Atualização rápida de status via AJAX (POST /status/<id>/<status>)
# =============================================================================
# Permite mudar o status diretamente na tabela do dashboard sem recarregar a
# página inteira. O frontend envia uma requisição POST via JavaScript (fetch)
# e recebe um JSON indicando se a operação foi bem-sucedida.
# =============================================================================
@app.route('/status/<int:id>/<status>', methods=['POST'])
def update_status(id, status):
    chamado = db.get_or_404(Chamado, id)
    # Valida se o status recebido faz parte da lista de opções válidas
    if status not in STATUS_CHOICES:
        return jsonify({'success': False, 'error': 'Status inválido'}), 400
    chamado.status = status
    chamado.data_atualizacao = datetime.now(UTC)
    db.session.commit()
    return jsonify({'success': True, 'status': status, 'id': id})


# =============================================================================
# ROTA: API de estatísticas (GET /api/stats)
# =============================================================================
# Retorna um JSON com contagens agrupadas por criticidade, área, tipo e status.
# É consumida pelo JavaScript do dashboard para renderizar os gráficos Chart.js
# sem precisar recarregar a página.
# =============================================================================
@app.route('/api/stats')
def api_stats():
    stats = {
        'por_criticidade': {},
        'por_area': {},
        'por_tipo': {},
        'por_status': {},
    }
    # Conta chamados por faixa de criticidade
    for crit in ['Crítica', 'Alta', 'Média', 'Baixa']:
        stats['por_criticidade'][crit] = Chamado.query.filter_by(criticidade=crit).count()
    # Conta chamados por área solicitante
    for area in AREAS:
        stats['por_area'][area] = Chamado.query.filter_by(area=area).count()
    # Conta chamados por tipo (converte a chave interna para rótulo amigável)
    tipo_labels = {'incidente': 'Incidente', 'requisicao': 'Requisição', 'problema': 'Problema'}
    for key, label in tipo_labels.items():
        stats['por_tipo'][label] = Chamado.query.filter_by(tipo=key).count()
    # Conta chamados por status
    for st in STATUS_CHOICES:
        stats['por_status'][st] = Chamado.query.filter_by(status=st).count()
    return jsonify(stats)


# =============================================================================
# ROTA: API de detalhes do chamado (GET /api/chamado/<id>)
# =============================================================================
# Retorna os dados completos de um chamado específico em formato JSON.
# Usada pelo modal de detalhes no dashboard (chamada via fetch no JavaScript).
# =============================================================================
@app.route('/api/chamado/<int:id>')
def api_chamado(id):
    chamado = db.get_or_404(Chamado, id)
    return jsonify(chamado.to_dict())


# =============================================================================
# ROTA: Exportação de dados em CSV (GET /exportar)
# =============================================================================
# Gera um arquivo CSV com todos os chamados, ordenados por score decrescente,
# e força o download pelo navegador. O BOM (Byte Order Mark) no início garante
# que o Excel reconheça a codificação UTF-8 corretamente (caracteres acentuados).
# =============================================================================
@app.route('/exportar')
def exportar_csv():
    chamados = Chamado.query.order_by(Chamado.score.desc()).all()

    # StringIO funciona como um "arquivo em memória" para gerar o CSV
    output = io.StringIO()
    writer = csv.writer(output)

    # Escreve a linha de cabeçalho do CSV
    writer.writerow([
        'Posicao', 'ID', 'Titulo', 'Descricao', 'Area', 'Tipo',
        'Impacto', 'Urgencia', 'Score', 'Criticidade', 'Status',
        'Data Criacao', 'Dias Aberto'
    ])

    # Escreve uma linha para cada chamado
    for idx, c in enumerate(chamados, 1):
        writer.writerow([
            idx, c.id, c.titulo, c.descricao, c.area, c.tipo,
            c.impacto, c.urgencia, f'{c.score:.2f}', c.criticidade, c.status,
            c.data_criacao.strftime('%d/%m/%Y %H:%M'),
            c.dias_aberto if c.dias_aberto is not None else 'Encerrado',
        ])

    output.seek(0)  # Volta o cursor para o início do stream

    # Retorna o CSV como resposta HTTP com headers que forçam o download
    # O BOM (\ufeff) no início do conteúdo permite que o Excel abra o
    # arquivo corretamente em UTF-8, sem problemas com acentos.
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=chamados_priorizados.csv'},
    )


# =============================================================================
# Bloco principal — executado quando rodamos "python app.py" diretamente
# =============================================================================
if __name__ == '__main__':
    # Lê configurações do ambiente. Por padrão, roda em modo debug.
    debug = os.environ.get('FLASK_DEBUG', '1') != '0'
    live_reload = os.environ.get('LIVE_RELOAD', '0') == '1'
    port = int(os.environ.get('PORT', 5000))

    # Cria as tabelas e recalcula criticidades ao iniciar o servidor
    init_db()

    if live_reload:
        # Modo livereload: usa a biblioteca livereload para injetar um script
        # em todas as páginas que conecta via WebSocket. Quando algum arquivo
        # HTML ou CSS é alterado, o navegador atualiza automaticamente.
        # Com nodemon, alterações em .py reiniciam o processo por completo.
        from livereload import Server as LiveServer
        app.debug = False
        app.config['_DB_READY'] = False
        lr = LiveServer(app.wsgi_app)
        lr.watch('templates/')       # Observa mudanças nos templates
        lr.watch('static/')          # Observa mudanças em arquivos estáticos
        lr.serve(port=port, host='0.0.0.0', debug=False)
    else:
        # Modo padrão: servidor de desenvolvimento do Flask.
        # use_reloader=False evita conflitos com o nodemon.
        app.run(debug=debug, host='0.0.0.0', port=port, use_reloader=False)
