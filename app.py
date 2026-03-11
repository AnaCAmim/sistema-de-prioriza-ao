from flask import Flask, render_template, redirect, url_for, request, jsonify, flash, Response
from flask_wtf.csrf import generate_csrf
from models import db, Chamado, AREAS, STATUS_CHOICES
from forms import ChamadoForm
from datetime import datetime, timezone
import csv
import io
import os

UTC = timezone.utc

# Caminho absoluto baseado na localização deste arquivo,
# garantindo que o banco seja sempre o mesmo independente do CWD.
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_DB_PATH  = os.path.join(_BASE_DIR, 'instance', 'chamados.db')
os.makedirs(os.path.join(_BASE_DIR, 'instance'), exist_ok=True)

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{_DB_PATH}'
app.config['SECRET_KEY'] = 'dev-secret-change-in-production'
db.init_app(app)
app.config['_DB_READY'] = False


@app.context_processor
def inject_csrf_token():
    return {'csrf_token': generate_csrf}


def init_db():
    with app.app_context():
        db.create_all()
        # Recalculate criticidade for all existing records when thresholds change
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
    if not app.config.get('_DB_READY'):
        db.create_all()
        app.config['_DB_READY'] = True


@app.route('/')
def index():
    area_filter       = request.args.get('area', '')
    criticidade_filter = request.args.get('criticidade', '')
    status_filter     = request.args.get('status', '')

    # Primary sort: score DESC; secondary: data_criacao ASC (older first at same score)
    query = Chamado.query.order_by(Chamado.score.desc(), Chamado.data_criacao.asc())

    if area_filter and area_filter != 'Todas':
        query = query.filter_by(area=area_filter)
    if criticidade_filter and criticidade_filter != 'Todas':
        query = query.filter_by(criticidade=criticidade_filter)
    if status_filter and status_filter != 'Todos':
        query = query.filter_by(status=status_filter)

    chamados = query.all()
    for idx, c in enumerate(chamados, 1):
        c.posicao = idx

    total = Chamado.query.count()
    stats = {
        'total':       total,
        'abertos':     Chamado.query.filter_by(status='Aberto').count(),
        'em_progresso':Chamado.query.filter_by(status='Em Progresso').count(),
        'critica':     Chamado.query.filter_by(criticidade='Crítica').count(),
        'alta':        Chamado.query.filter_by(criticidade='Alta').count(),
        'resolvidos':  Chamado.query.filter(Chamado.status.in_(['Resolvido', 'Fechado'])).count(),
    }

    sla_limites = {
        'Crítica': 1,
        'Alta': 2,
        'Média': 4,
        'Baixa': 7,
    }
    criticidade_peso = {
        'Crítica': 4,
        'Alta': 3,
        'Média': 2,
        'Baixa': 1,
    }
    abertos = [c for c in Chamado.query.all() if c.status not in ('Resolvido', 'Fechado')]
    total_abertos = len(abertos)

    sla_estourado = 0
    proximos_sla = 0
    soma_idade = 0
    soma_peso = 0

    for c in abertos:
        dias = c.dias_aberto or 0
        limite = sla_limites.get(c.criticidade, 4)
        soma_idade += dias
        soma_peso += criticidade_peso.get(c.criticidade, 1)
        if dias > limite:
            sla_estourado += 1
        elif dias == limite or dias == max(limite - 1, 0):
            proximos_sla += 1

    idade_media = round(soma_idade / total_abertos, 1) if total_abertos else 0
    indice_risco = round((soma_peso / (total_abertos * 4)) * 100, 1) if total_abertos else 0
    taxa_sla_estourado = round((sla_estourado / total_abertos) * 100, 1) if total_abertos else 0

    kpis = {
        'total_abertos': total_abertos,
        'sla_estourado': sla_estourado,
        'proximos_sla': proximos_sla,
        'idade_media': idade_media,
        'indice_risco': indice_risco,
        'taxa_sla_estourado': taxa_sla_estourado,
    }

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


@app.route('/novo', methods=['GET', 'POST'])
def novo_chamado():
    form = ChamadoForm()
    # The new ticket form does not expose status; keep default workflow as "Aberto".
    if request.method == 'POST' and not form.status.data:
        form.status.data = 'Aberto'
    if form.validate_on_submit():
        chamado = Chamado.from_form(form)
        db.session.add(chamado)
        db.session.commit()
        flash(
            f'✅ Chamado "{chamado.titulo}" enviado com sucesso! '
            f'Score: {chamado.score:.2f} | Criticidade: {chamado.criticidade}',
            'success'
        )
        return redirect(url_for('index'))
    return render_template('novo.html', form=form)


@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_chamado(id):
    chamado = db.get_or_404(Chamado, id)
    form = ChamadoForm()
    if form.validate_on_submit():
        chamado.titulo           = form.titulo.data
        chamado.descricao        = form.descricao.data
        chamado.area             = form.area.data
        chamado.impacto          = form.impacto.data
        chamado.urgencia         = form.urgencia.data
        chamado.tipo             = form.tipo.data
        chamado.status           = form.status.data
        chamado.score            = Chamado.calculate_score(form.impacto.data, form.urgencia.data, form.tipo.data)
        chamado.criticidade      = Chamado.get_criticidade(chamado.score)
        chamado.data_atualizacao = datetime.now(UTC)
        db.session.commit()
        flash(
            f'Chamado atualizado! Novo score: {chamado.score:.2f} | Criticidade: {chamado.criticidade}',
            'success'
        )
        return redirect(url_for('index'))
    elif request.method == 'GET':
        form.titulo.data   = chamado.titulo
        form.descricao.data = chamado.descricao
        form.area.data     = chamado.area
        form.impacto.data  = chamado.impacto
        form.urgencia.data = chamado.urgencia
        form.tipo.data     = chamado.tipo
        form.status.data   = chamado.status
    return render_template('editar.html', form=form, chamado=chamado)


@app.route('/excluir/<int:id>', methods=['POST'])
def excluir_chamado(id):
    chamado = db.get_or_404(Chamado, id)
    titulo = chamado.titulo
    db.session.delete(chamado)
    db.session.commit()
    flash(f'Chamado "{titulo}" excluído.', 'warning')
    return redirect(url_for('index'))


@app.route('/status/<int:id>/<status>', methods=['POST'])
def update_status(id, status):
    chamado = db.get_or_404(Chamado, id)
    if status not in STATUS_CHOICES:
        return jsonify({'success': False, 'error': 'Status inválido'}), 400
    chamado.status = status
    chamado.data_atualizacao = datetime.now(UTC)
    db.session.commit()
    return jsonify({'success': True, 'status': status})


@app.route('/api/stats')
def api_stats():
    stats = {
        'por_criticidade': {},
        'por_area': {},
        'por_tipo': {},
        'por_status': {},
    }
    for crit in ['Crítica', 'Alta', 'Média', 'Baixa']:
        stats['por_criticidade'][crit] = Chamado.query.filter_by(criticidade=crit).count()
    for area in AREAS:
        stats['por_area'][area] = Chamado.query.filter_by(area=area).count()
    tipo_labels = {'incidente': 'Incidente', 'requisicao': 'Requisição', 'problema': 'Problema'}
    for key, label in tipo_labels.items():
        stats['por_tipo'][label] = Chamado.query.filter_by(tipo=key).count()
    for st in STATUS_CHOICES:
        stats['por_status'][st] = Chamado.query.filter_by(status=st).count()
    return jsonify(stats)


@app.route('/api/chamado/<int:id>')
def api_chamado(id):
    chamado = db.get_or_404(Chamado, id)
    return jsonify(chamado.to_dict())


@app.route('/exportar')
def exportar_csv():
    chamados = Chamado.query.order_by(Chamado.score.desc()).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow([
        'Posicao', 'ID', 'Titulo', 'Descricao', 'Area', 'Tipo',
        'Impacto', 'Urgencia', 'Score', 'Criticidade', 'Status',
        'Data Criacao', 'Dias Aberto'
    ])
    for idx, c in enumerate(chamados, 1):
        writer.writerow([
            idx, c.id, c.titulo, c.descricao, c.area, c.tipo,
            c.impacto, c.urgencia, f'{c.score:.2f}', c.criticidade, c.status,
            c.data_criacao.strftime('%d/%m/%Y %H:%M'),
            c.dias_aberto if c.dias_aberto is not None else 'Encerrado',
        ])
    output.seek(0)
    # BOM (\ufeff) ensures Excel opens UTF-8 CSV correctly
    return Response(
        '\ufeff' + output.getvalue(),
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': 'attachment; filename=chamados_priorizados.csv'},
    )


if __name__ == '__main__':
    debug = os.environ.get('FLASK_DEBUG', '1') != '0'
    live_reload = os.environ.get('LIVE_RELOAD', '0') == '1'
    port = int(os.environ.get('PORT', 5000))
    init_db()
    if live_reload:
        # Livereload: injeta script em todas as páginas e conecta via WebSocket.
        # Mudanças em .html → browser atualiza sem reiniciar o servidor.
        # Mudanças em .py  → nodemon reinicia o processo → browser reconecta e atualiza.
        from livereload import Server as LiveServer
        app.debug = False
        app.config['_DB_READY'] = False
        lr = LiveServer(app.wsgi_app)
        lr.watch('templates/')
        lr.watch('static/')
        lr.serve(port=port, host='0.0.0.0', debug=False)
    else:
        app.run(debug=debug, host='0.0.0.0', port=port, use_reloader=False)
