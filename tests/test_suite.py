"""
QA Test Suite — Sistema de Priorização de Chamados de TI
=========================================================
Execução:
    pytest tests/ -v
"""

import pytest
from app import app as flask_app, db as _db
from models import Chamado, AREAS, STATUS_CHOICES, IMPACT_VALUES, URGENCY_VALUES, TYPE_VALUES


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture(scope='session')
def app():
    # Cria uma configuração de teste SEM modificar o flask_app global,
    # para não corromper o banco de produção (instance/chamados.db).
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SECRET_KEY'] = 'test-secret'

    with flask_app.app_context():
        # Descarta engine antigo (que apontava para o arquivo .db)
        # e cria novo engine em memória com as tabelas limpas.
        _db.engine.dispose()
        _db.create_all()
        yield flask_app
        _db.drop_all()
        _db.engine.dispose()


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Limpa a tabela antes de cada teste para garantir isolamento."""
    with app.app_context():
        _db.session.query(Chamado).delete()
        _db.session.commit()
    yield


def _criar_chamado(app, **kwargs):
    """Helper: cria e persiste um chamado com valores padrão sobrescrevíveis."""
    defaults = dict(
        titulo='Chamado de teste',
        descricao='Descrição de teste',
        area='TI',
        impacto='alto',
        urgencia='alta',
        tipo='incidente',
    )
    defaults.update(kwargs)
    with app.app_context():
        score = Chamado.calculate_score(defaults['impacto'], defaults['urgencia'], defaults['tipo'])
        c = Chamado(
            titulo=defaults['titulo'],
            descricao=defaults['descricao'],
            area=defaults['area'],
            impacto=defaults['impacto'],
            urgencia=defaults['urgencia'],
            tipo=defaults['tipo'],
            score=score,
            criticidade=Chamado.get_criticidade(score),
            status=defaults.get('status', 'Aberto'),
        )
        _db.session.add(c)
        _db.session.commit()
        return c.id


# ══════════════════════════════════════════════════════════════════════════════
# 1. MODELO — Cálculo de score
# ══════════════════════════════════════════════════════════════════════════════

class TestCalculoScore:
    def test_score_maximo(self):
        """alto + alta + incidente → 3.0 (máximo possível)."""
        assert Chamado.calculate_score('alto', 'alta', 'incidente') == 3.0

    def test_score_minimo(self):
        """baixo + baixa + requisicao → 1.0 (mínimo possível)."""
        assert Chamado.calculate_score('baixo', 'baixa', 'requisicao') == 1.0

    def test_score_medio(self):
        """medio + media + problema → (2×0.4)+(2×0.4)+(2×0.2) = 2.0."""
        assert Chamado.calculate_score('medio', 'media', 'problema') == 2.0

    def test_score_formula_ponderada(self):
        """alto(3) + baixa(1) + incidente(3) = 3×0.4 + 1×0.4 + 3×0.2 = 2.2."""
        assert Chamado.calculate_score('alto', 'baixa', 'incidente') == 2.2

    def test_score_arredondado(self):
        """Resultado deve ter no máximo 2 casas decimais."""
        score = Chamado.calculate_score('baixo', 'alta', 'problema')
        assert score == round(score, 2)

    def test_score_valor_invalido_usa_fallback(self):
        """Valor desconhecido cai no padrão 1 sem lançar exceção."""
        score = Chamado.calculate_score('invalido', 'invalido', 'invalido')
        assert score == 1.0

    @pytest.mark.parametrize('impacto,urgencia,tipo,esperado', [
        ('baixo',  'baixa',  'requisicao', 1.0),
        ('baixo',  'baixa',  'problema',   1.2),
        ('medio',  'media',  'problema',   2.0),
        ('alto',   'alta',   'problema',   2.8),
        ('alto',   'alta',   'incidente',  3.0),
    ])
    def test_score_parametrizado(self, impacto, urgencia, tipo, esperado):
        assert Chamado.calculate_score(impacto, urgencia, tipo) == esperado


# ══════════════════════════════════════════════════════════════════════════════
# 2. MODELO — Faixas de criticidade
# ══════════════════════════════════════════════════════════════════════════════

class TestCriticidade:
    @pytest.mark.parametrize('score,esperado', [
        (3.0,  'Crítica'),
        (2.6,  'Crítica'),
        (2.59, 'Alta'),
        (2.0,  'Alta'),
        (1.99, 'Média'),
        (1.4,  'Média'),
        (1.39, 'Baixa'),
        (1.0,  'Baixa'),
    ])
    def test_faixas_limites(self, score, esperado):
        assert Chamado.get_criticidade(score) == esperado

    def test_critica_score_maximo(self):
        assert Chamado.get_criticidade(3.0) == 'Crítica'

    def test_baixa_score_minimo(self):
        assert Chamado.get_criticidade(1.0) == 'Baixa'


# ══════════════════════════════════════════════════════════════════════════════
# 3. MODELO — Propriedade dias_aberto
# ══════════════════════════════════════════════════════════════════════════════

class TestDiasAberto:
    def test_aberto_retorna_inteiro(self, app):
        cid = _criar_chamado(app, status='Aberto')
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            assert isinstance(c.dias_aberto, int)
            assert c.dias_aberto >= 0

    @pytest.mark.parametrize('status', ['Resolvido', 'Fechado'])
    def test_encerrado_retorna_none(self, app, status):
        cid = _criar_chamado(app, status=status)
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            assert c.dias_aberto is None

    @pytest.mark.parametrize('status', ['Em Progresso', 'Aguardando'])
    def test_intermediario_retorna_inteiro(self, app, status):
        cid = _criar_chamado(app, status=status)
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            assert isinstance(c.dias_aberto, int)


# ══════════════════════════════════════════════════════════════════════════════
# 4. MODELO — to_dict
# ══════════════════════════════════════════════════════════════════════════════

class TestToDict:
    CAMPOS_OBRIGATORIOS = [
        'id', 'titulo', 'descricao', 'area', 'impacto', 'urgencia',
        'tipo', 'score', 'criticidade', 'status', 'data_criacao',
        'dias_aberto', 'posicao',
    ]

    def test_todos_campos_presentes(self, app):
        cid = _criar_chamado(app)
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            d = c.to_dict()
            for campo in self.CAMPOS_OBRIGATORIOS:
                assert campo in d, f'Campo ausente: {campo}'

    def test_score_float(self, app):
        cid = _criar_chamado(app)
        with app.app_context():
            d = _db.session.get(Chamado, cid).to_dict()
            assert isinstance(d['score'], float)

    def test_data_criacao_formato(self, app):
        cid = _criar_chamado(app)
        with app.app_context():
            d = _db.session.get(Chamado, cid).to_dict()
            from datetime import datetime
            datetime.strptime(d['data_criacao'], '%d/%m/%Y %H:%M')


# ══════════════════════════════════════════════════════════════════════════════
# 5. ROTAS — Dashboard (GET /)
# ══════════════════════════════════════════════════════════════════════════════

class TestDashboard:
    def test_dashboard_ok(self, client):
        r = client.get('/')
        assert r.status_code == 200

    def test_dashboard_contem_html_basico(self, client):
        r = client.get('/')
        body = r.data.decode('utf-8')
        assert '<html' in body
        assert 'Priorização' in body

    def test_dashboard_sem_chamados_exibe_mensagem_vazia(self, client):
        r = client.get('/')
        body = r.data.decode('utf-8')
        assert 'Nenhum chamado' in body

    def test_dashboard_exibe_chamado_criado(self, client, app):
        _criar_chamado(app, titulo='Incidente Crítico')
        r = client.get('/')
        assert b'Incidente Cr' in r.data

    def test_filtro_area(self, client, app):
        _criar_chamado(app, area='RH', titulo='Chamado RH')
        _criar_chamado(app, area='TI', titulo='Chamado TI')
        r = client.get('/?area=RH')
        body = r.data.decode('utf-8')
        assert 'Chamado RH' in body
        assert 'Chamado TI' not in body

    def test_filtro_criticidade(self, client, app):
        _criar_chamado(app, impacto='alto', urgencia='alta', tipo='incidente', titulo='Alta prioridade')
        _criar_chamado(app, impacto='baixo', urgencia='baixa', tipo='requisicao', titulo='Baixa prioridade')
        r = client.get('/?criticidade=Crítica')
        body = r.data.decode('utf-8')
        assert 'Alta prioridade' in body
        assert 'Baixa prioridade' not in body

    def test_filtro_status(self, client, app):
        _criar_chamado(app, status='Aberto', titulo='Chamado Aberto')
        _criar_chamado(app, status='Fechado', titulo='Chamado Fechado')
        r = client.get('/?status=Aberto')
        body = r.data.decode('utf-8')
        assert 'Chamado Aberto' in body
        assert 'Chamado Fechado' not in body

    def test_ranking_ordenado_por_score(self, client, app):
        _criar_chamado(app, impacto='baixo', urgencia='baixa', tipo='requisicao', titulo='Score Baixo')
        _criar_chamado(app, impacto='alto',  urgencia='alta',  tipo='incidente',  titulo='Score Alto')
        r = client.get('/')
        body = r.data.decode('utf-8')
        assert body.index('Score Alto') < body.index('Score Baixo')


# ══════════════════════════════════════════════════════════════════════════════
# 6. ROTAS — Criação de chamado (GET + POST /novo)
# ══════════════════════════════════════════════════════════════════════════════

class TestNovoChamado:
    PAYLOAD_VALIDO = {
        'titulo':    'Novo Chamado',
        'descricao': 'Descrição completa',
        'area':      'TI',
        'impacto':   'alto',
        'urgencia':  'alta',
        'tipo':      'incidente',
    }

    def test_get_novo_retorna_200(self, client):
        assert client.get('/novo').status_code == 200

    def test_get_novo_contem_formulario(self, client):
        r = client.get('/novo')
        assert b'<form' in r.data

    def test_post_valido_redireciona(self, client):
        r = client.post('/novo', data=self.PAYLOAD_VALIDO)
        assert r.status_code == 302
        assert r.headers['Location'] == '/'

    def test_post_valido_salva_no_banco(self, client, app):
        client.post('/novo', data=self.PAYLOAD_VALIDO)
        with app.app_context():
            c = Chamado.query.filter_by(titulo='Novo Chamado').first()
            assert c is not None
            assert c.area == 'TI'
            assert c.score == 3.0
            assert c.criticidade == 'Crítica'
            assert c.status == 'Aberto'

    def test_post_sem_titulo_nao_salva(self, client, app):
        payload = {**self.PAYLOAD_VALIDO, 'titulo': ''}
        r = client.post('/novo', data=payload)
        assert r.status_code == 200  # re-renderiza form com erro
        with app.app_context():
            assert Chamado.query.count() == 0

    def test_post_sem_descricao_nao_salva(self, client, app):
        payload = {**self.PAYLOAD_VALIDO, 'descricao': ''}
        r = client.post('/novo', data=payload)
        assert r.status_code == 200
        with app.app_context():
            assert Chamado.query.count() == 0

    def test_post_calcula_score_correto(self, client, app):
        payload = {**self.PAYLOAD_VALIDO, 'impacto': 'baixo', 'urgencia': 'baixa', 'tipo': 'requisicao'}
        client.post('/novo', data=payload)
        with app.app_context():
            c = Chamado.query.first()
            assert c.score == 1.0
            assert c.criticidade == 'Baixa'


# ══════════════════════════════════════════════════════════════════════════════
# 7. ROTAS — Edição de chamado (GET + POST /editar/<id>)
# ══════════════════════════════════════════════════════════════════════════════

class TestEditarChamado:
    def test_get_editar_retorna_200(self, client, app):
        cid = _criar_chamado(app)
        assert client.get(f'/editar/{cid}').status_code == 200

    def test_get_editar_id_inexistente_retorna_404(self, client):
        assert client.get('/editar/9999').status_code == 404

    def test_post_editar_atualiza_titulo(self, client, app):
        cid = _criar_chamado(app)
        client.post(f'/editar/{cid}', data={
            'titulo': 'Título Atualizado', 'descricao': 'Nova desc',
            'area': 'RH', 'impacto': 'medio', 'urgencia': 'media',
            'tipo': 'problema', 'status': 'Em Progresso',
        })
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            assert c.titulo == 'Título Atualizado'
            assert c.area == 'RH'
            assert c.status == 'Em Progresso'

    def test_post_editar_recalcula_score(self, client, app):
        cid = _criar_chamado(app, impacto='alto', urgencia='alta', tipo='incidente')
        client.post(f'/editar/{cid}', data={
            'titulo': 'Editado', 'descricao': 'Desc',
            'area': 'TI', 'impacto': 'baixo', 'urgencia': 'baixa',
            'tipo': 'requisicao', 'status': 'Aberto',
        })
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            assert c.score == 1.0
            assert c.criticidade == 'Baixa'

    def test_post_editar_redireciona(self, client, app):
        cid = _criar_chamado(app)
        r = client.post(f'/editar/{cid}', data={
            'titulo': 'X', 'descricao': 'Y', 'area': 'TI',
            'impacto': 'baixo', 'urgencia': 'baixa',
            'tipo': 'requisicao', 'status': 'Aberto',
        })
        assert r.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# 8. ROTAS — Exclusão (POST /excluir/<id>)
# ══════════════════════════════════════════════════════════════════════════════

class TestExcluirChamado:
    def test_excluir_remove_do_banco(self, client, app):
        cid = _criar_chamado(app)
        client.post(f'/excluir/{cid}')
        with app.app_context():
            assert _db.session.get(Chamado, cid) is None

    def test_excluir_redireciona(self, client, app):
        cid = _criar_chamado(app)
        r = client.post(f'/excluir/{cid}')
        assert r.status_code == 302

    def test_excluir_id_inexistente_retorna_404(self, client):
        assert client.post('/excluir/9999').status_code == 404

    def test_excluir_nao_afeta_outros_chamados(self, client, app):
        cid1 = _criar_chamado(app, titulo='Para excluir')
        cid2 = _criar_chamado(app, titulo='Para manter')
        client.post(f'/excluir/{cid1}')
        with app.app_context():
            assert _db.session.get(Chamado, cid2) is not None


# ══════════════════════════════════════════════════════════════════════════════
# 9. ROTAS — Atualização de status via AJAX (POST /status/<id>/<status>)
# ══════════════════════════════════════════════════════════════════════════════

class TestUpdateStatus:
    @pytest.mark.parametrize('novo_status', STATUS_CHOICES)
    def test_todos_status_validos(self, client, app, novo_status):
        cid = _criar_chamado(app)
        r = client.post(f'/status/{cid}/{novo_status}')
        assert r.status_code == 200
        data = r.get_json()
        assert data['success'] is True
        assert data['status'] == novo_status

    def test_status_invalido_retorna_400(self, client, app):
        cid = _criar_chamado(app)
        r = client.post(f'/status/{cid}/StatusInexistente')
        assert r.status_code == 400
        assert r.get_json()['success'] is False

    def test_status_id_inexistente_retorna_404(self, client):
        assert client.post('/status/9999/Aberto').status_code == 404

    def test_status_persiste_no_banco(self, client, app):
        cid = _criar_chamado(app)
        client.post(f'/status/{cid}/Resolvido')
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            assert c.status == 'Resolvido'


# ══════════════════════════════════════════════════════════════════════════════
# 10. API — GET /api/stats
# ══════════════════════════════════════════════════════════════════════════════

class TestApiStats:
    def test_retorna_200(self, client):
        assert client.get('/api/stats').status_code == 200

    def test_estrutura_json(self, client):
        data = client.get('/api/stats').get_json()
        assert 'por_criticidade' in data
        assert 'por_area' in data
        assert 'por_tipo' in data
        assert 'por_status' in data

    def test_todas_criticidades_presentes(self, client):
        data = client.get('/api/stats').get_json()
        for crit in ['Crítica', 'Alta', 'Média', 'Baixa']:
            assert crit in data['por_criticidade']

    def test_todas_areas_presentes(self, client):
        data = client.get('/api/stats').get_json()
        for area in AREAS:
            assert area in data['por_area']

    def test_todos_tipos_presentes(self, client):
        data = client.get('/api/stats').get_json()
        for tipo in ['Incidente', 'Requisição', 'Problema']:
            assert tipo in data['por_tipo']

    def test_todos_status_presentes(self, client):
        data = client.get('/api/stats').get_json()
        for st in STATUS_CHOICES:
            assert st in data['por_status']

    def test_contagem_reflete_banco(self, client, app):
        _criar_chamado(app, impacto='alto', urgencia='alta', tipo='incidente')
        data = client.get('/api/stats').get_json()
        assert data['por_criticidade']['Crítica'] >= 1
        assert data['por_area']['TI'] >= 1
        assert data['por_status']['Aberto'] >= 1


# ══════════════════════════════════════════════════════════════════════════════
# 11. API — GET /api/chamado/<id>
# ══════════════════════════════════════════════════════════════════════════════

class TestApiChamado:
    def test_retorna_200(self, client, app):
        cid = _criar_chamado(app)
        assert client.get(f'/api/chamado/{cid}').status_code == 200

    def test_id_inexistente_retorna_404(self, client):
        assert client.get('/api/chamado/9999').status_code == 404

    def test_dados_corretos(self, client, app):
        cid = _criar_chamado(app, titulo='API Test', area='Financeiro')
        data = client.get(f'/api/chamado/{cid}').get_json()
        assert data['id'] == cid
        assert data['titulo'] == 'API Test'
        assert data['area'] == 'Financeiro'
        assert data['score'] == 3.0
        assert data['criticidade'] == 'Crítica'

    def test_campos_obrigatorios_presentes(self, client, app):
        cid = _criar_chamado(app)
        data = client.get(f'/api/chamado/{cid}').get_json()
        for campo in ['id', 'titulo', 'descricao', 'area', 'score',
                      'criticidade', 'status', 'data_criacao', 'dias_aberto']:
            assert campo in data


# ══════════════════════════════════════════════════════════════════════════════
# 12. EXPORTAÇÃO CSV — GET /exportar
# ══════════════════════════════════════════════════════════════════════════════

class TestExportarCsv:
    def test_retorna_200(self, client):
        assert client.get('/exportar').status_code == 200

    def test_content_type_csv(self, client):
        r = client.get('/exportar')
        assert 'text/csv' in r.content_type

    def test_header_download(self, client):
        r = client.get('/exportar')
        assert 'chamados_priorizados.csv' in r.headers.get('Content-Disposition', '')

    def test_cabecalho_csv_correto(self, client):
        r = client.get('/exportar')
        texto = r.data.decode('utf-8-sig')
        linha = texto.splitlines()[0]
        for col in ['Posicao', 'ID', 'Titulo', 'Score', 'Criticidade', 'Status']:
            assert col in linha

    def test_csv_contem_chamado(self, client, app):
        _criar_chamado(app, titulo='Chamado CSV')
        r = client.get('/exportar')
        assert b'Chamado CSV' in r.data

    def test_csv_sem_chamados_tem_apenas_cabecalho(self, client):
        r = client.get('/exportar')
        linhas = r.data.decode('utf-8-sig').strip().splitlines()
        assert len(linhas) == 1  # só cabeçalho


# ══════════════════════════════════════════════════════════════════════════════
# 13. CONSTANTES e integridade de configuração
# ══════════════════════════════════════════════════════════════════════════════

class TestConstantes:
    def test_areas_nao_vazio(self):
        assert len(AREAS) > 0

    def test_status_choices_ordem(self):
        assert STATUS_CHOICES[0] == 'Aberto'
        assert STATUS_CHOICES[-1] == 'Fechado'

    def test_impact_values_range(self):
        assert set(IMPACT_VALUES.values()) == {1, 2, 3}

    def test_urgency_values_range(self):
        assert set(URGENCY_VALUES.values()) == {1, 2, 3}

    def test_type_values_range(self):
        assert set(TYPE_VALUES.values()) == {1, 2, 3}

    def test_score_range_completo(self):
        """Garante que score mínimo e máximo são 1.0 e 3.0."""
        scores = [
            Chamado.calculate_score(i, u, t)
            for i in IMPACT_VALUES
            for u in URGENCY_VALUES
            for t in TYPE_VALUES
        ]
        assert min(scores) == 1.0
        assert max(scores) == 3.0

    def test_todas_criticidades_alcancaveis(self):
        """Cada faixa de criticidade deve ser alcançável com alguma combinação."""
        scores = [
            Chamado.calculate_score(i, u, t)
            for i in IMPACT_VALUES
            for u in URGENCY_VALUES
            for t in TYPE_VALUES
        ]
        crits = {Chamado.get_criticidade(s) for s in scores}
        assert crits == {'Crítica', 'Alta', 'Média', 'Baixa'}
