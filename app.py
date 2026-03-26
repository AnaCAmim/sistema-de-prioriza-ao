from flask import Flask, render_template, redirect, url_for, request, jsonify
from flask_sqlalchemy import SQLAlchemy
from models import db, Chamado, AREAS, STATUS_CHOICES
from forms import ChamadoForm
from sqlalchemy import func
import json
import os

app = Flask(__name__)
# Usa caminho absoluto para o SQLite para evitar abrir bancos diferentes
# quando o app eh iniciado em diretorios distintos.
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_DIR = os.path.join(BASE_DIR, 'instance')
os.makedirs(DB_DIR, exist_ok=True)
DB_PATH = os.path.join(DB_DIR, 'chamados.db')

app.config['SQLALCHEMY_DATABASE_URI'] = f'sqlite:///{DB_PATH}'
app.config['SECRET_KEY'] = 'dev-secret'
db.init_app(app)
app.config['_DB_READY'] = False

def init_db():
    with app.app_context():
        db.create_all()
        app.config['_DB_READY'] = True

init_db()


@app.before_request
def ensure_db_ready():
    # Fallback para garantir que a tabela exista antes de cada requisicao.
    if not app.config.get('_DB_READY'):
        db.create_all()
        app.config['_DB_READY'] = True

@app.route('/')
def index():
    area_filter = request.args.get('area', '')
    criticidade_filter = request.args.get('criticidade', '')
    status_filter = request.args.get('status', '')
    
    query = Chamado.query.order_by(Chamado.score.desc())
    
    if area_filter and area_filter != 'Todas':
        query = query.filter_by(area=area_filter)
    if criticidade_filter and criticidade_filter != 'Todas':
        query = query.filter_by(criticidade=criticidade_filter)
    if status_filter and status_filter != 'Todos':
        query = query.filter_by(status=status_filter)
    
    chamados = query.all()
    
    for idx, c in enumerate(chamados, 1):
        c.posicao = idx
    
    stats = {
        'total': Chamado.query.count(),
        'abertos': Chamado.query.filter_by(status='Aberto').count(),
        'critica': Chamado.query.filter_by(criticidade='Crítica').count(),
        'alta': Chamado.query.filter_by(criticidade='Alta').count(),
    }
    
    return render_template('dashboard.html', chamados=chamados, areas=AREAS, 
                         stats=stats, selected_area=area_filter,
                         selected_criticidade=criticidade_filter,
                         selected_status=status_filter)

@app.route('/novo', methods=['GET', 'POST'])
def novo_chamado():
    form = ChamadoForm()
    if form.validate_on_submit():
        chamado = Chamado.from_form(form)
        db.session.add(chamado)
        db.session.commit()
        return redirect(url_for('index'))
    return render_template('novo.html', form=form)

@app.route('/editar/<int:id>', methods=['GET', 'POST'])
def editar_chamado(id):
    chamado = Chamado.query.get_or_404(id)
    form = ChamadoForm()
    if form.validate_on_submit():
        chamado.titulo = form.titulo.data
        chamado.descricao = form.descricao.data
        chamado.area = form.area.data
        chamado.impacto = form.impacto.data
        chamado.urgencia = form.urgencia.data
        chamado.tipo = form.tipo.data
        chamado.score = Chamado.calculate_score(form.impacto.data, form.urgencia.data, form.tipo.data)
        chamado.criticidade = Chamado.get_criticidade(chamado.score)
        db.session.commit()
        return redirect(url_for('index'))
    elif request.method == 'GET':
        form.titulo.data = chamado.titulo
        form.descricao.data = chamado.descricao
        form.area.data = chamado.area
        form.impacto.data = chamado.impacto
        form.urgencia.data = chamado.urgencia
        form.tipo.data = chamado.tipo
    return render_template('editar.html', form=form, chamado=chamado)

@app.route('/status/<int:id>/<status>', methods=['POST'])
def update_status(id, status):
    chamado = Chamado.query.get_or_404(id)
    if status in STATUS_CHOICES:
        chamado.status = status
        db.session.commit()
    return jsonify({'success': True})

@app.route('/api/stats')
def api_stats():
    stats = {
        'por_criticidade': {},
        'por_area': {},
        'por_tipo': {},
        'por_status': {}
    }
    
    for crit in ['Crítica', 'Alta', 'Média', 'Baixa']:
        stats['por_criticidade'][crit] = Chamado.query.filter_by(criticidade=crit).count()
    
    for area in AREAS:
        stats['por_area'][area] = Chamado.query.filter_by(area=area).count()
    
    for tipo in ['incidente', 'requisicao', 'problema']:
        stats['por_tipo'][tipo.title()] = Chamado.query.filter_by(tipo=tipo).count()
    
    for st in STATUS_CHOICES:
        stats['por_status'][st] = Chamado.query.filter_by(status=st).count()
    
    return jsonify(stats)

@app.route('/api/chamado/<int:id>')
def api_chamado(id):
    chamado = Chamado.query.get_or_404(id)
    return jsonify(chamado.to_dict())

if __name__ == '__main__':
    app.run(debug=True)
