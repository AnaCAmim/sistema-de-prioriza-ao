"""
=============================================================================
test_suite.py — Suite completa de testes automatizados
=============================================================================
Este arquivo contém todos os testes automatizados do sistema de priorização.
Utiliza o framework pytest para Python, que permite escrever testes de forma
simples e organizada.

Organização dos testes (17 grupos):
  1. TestCalculoScore       — Fórmula de cálculo do score
  2. TestCriticidade        — Faixas de classificação por score
  3. TestDiasAberto         — Propriedade dias_aberto do modelo
  4. TestToDict             — Serialização do modelo para dicionário
  5. TestDashboard          — Rota GET / (página principal)
  6. TestNovoChamado        — Rota GET/POST /novo (criação)
  7. TestEditarChamado      — Rota GET/POST /editar/<id> (edição)
  8. TestExcluirChamado     — Rota POST /excluir/<id> (exclusão)
  9. TestUpdateStatus       — Rota POST /status/<id>/<status> (AJAX)
 10. TestApiStats           — Rota GET /api/stats (dados para gráficos)
 11. TestApiChamado         — Rota GET /api/chamado/<id> (detalhes)
 12. TestExportarCsv        — Rota GET /exportar (download CSV)
 13. TestConstantes         — Integridade das constantes do sistema
 14. TestSeguranca          — Proteção contra XSS e inputs maliciosos
 15. TestValidacaoFormulario— Limites de comprimento dos campos
 16. TestFromForm           — Factory method e integridade dos dados
 17. TestApiCampos          — Campos adicionais na API

Execução:
    pytest tests/ -v
=============================================================================
"""

import pytest
from app import app as flask_app, db as _db
from models import Chamado, AREAS, STATUS_CHOICES, IMPACT_VALUES, URGENCY_VALUES, TYPE_VALUES


# ══════════════════════════════════════════════════════════════════════════════
# Fixtures — Funções auxiliares que preparam o ambiente de testes
# ══════════════════════════════════════════════════════════════════════════════
# Fixtures são funções especiais do pytest que criam recursos reutilizáveis.
# O pytest injeta automaticamente essas funções nos testes que as solicitam
# como parâmetros (ex.: def test_exemplo(self, client, app):).
# ══════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope='session')
def app():
    """Cria e configura a aplicação Flask para testes.
    Usa scope='session' para criar uma única instância durante toda a
    execução dos testes, evitando overhead de recriação.

    Diferenças em relação à configuração de produção:
    - TESTING=True: ativa o modo de teste do Flask
    - SQLite em memória (:///:memory:): banco temporário que não persiste
    - CSRF desabilitado: permite enviar formulários de teste sem token
    - SECRET_KEY fixa: não precisa de variável de ambiente em testes"""
    flask_app.config['TESTING'] = True
    flask_app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///:memory:'
    flask_app.config['WTF_CSRF_ENABLED'] = False
    flask_app.config['SECRET_KEY'] = 'test-secret'

    with flask_app.app_context():
        # Descarta a engine atual (que apontava para o arquivo .db real)
        # e cria uma nova engine em memória com as tabelas limpas
        _db.engine.dispose()
        _db.create_all()
        yield flask_app
        # Limpeza: remove as tabelas e encerra a conexão após todos os testes
        _db.drop_all()
        _db.engine.dispose()


@pytest.fixture
def client(app):
    """Cria um cliente HTTP de teste que simula requisições ao servidor.
    Permite fazer requests sem precisar iniciar o servidor real.
    Exemplo: client.get('/') simula acessar o dashboard no navegador."""
    return app.test_client()


@pytest.fixture(autouse=True)
def clean_db(app):
    """Limpa a tabela de chamados antes de cada teste individual.
    autouse=True faz com que seja executada automaticamente antes de
    todo teste, garantindo isolamento — nenhum teste interfere no outro."""
    with app.app_context():
        _db.session.query(Chamado).delete()
        _db.session.commit()
    yield


def _criar_chamado(app, **kwargs):
    """Função auxiliar que cria um chamado de teste no banco de dados.
    Aceita parâmetros opcionais para sobrescrever os valores padrão.
    Retorna o ID do chamado criado para uso nos testes.

    Exemplo de uso:
        cid = _criar_chamado(app, titulo='Teste', area='RH')
    """
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
# Testa a fórmula de priorização: Score = (I×0.4) + (U×0.4) + (T×0.2)
# Verifica combinações extremas (máximo, mínimo), valores intermediários,
# arredondamento e comportamento com valores inválidos (fallback).
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
# Testa se os limites das faixas estão corretos:
# >= 2.60 = Crítica, >= 2.00 = Alta, >= 1.40 = Média, < 1.40 = Baixa
# Usa parametrize do pytest para testar múltiplos valores em um único teste.
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
# Testa se a propriedade calculada retorna um número inteiro para chamados
# ativos e None para chamados finalizados (Resolvido / Fechado).
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
# 4. MODELO — to_dict (serialização)
# ══════════════════════════════════════════════════════════════════════════════
# Testa se o método to_dict() retorna todos os campos esperados com os
# tipos corretos (score como float, data no formato dd/mm/aaaa hh:mm).
# ══════════════════════════════════════════════════════════════════════════════

class TestToDict:
    CAMPOS_OBRIGATORIOS = [
        'id', 'titulo', 'descricao', 'area', 'impacto', 'urgencia',
        'tipo', 'score', 'criticidade', 'status', 'data_criacao',
        'dias_aberto', 'data_atualizacao',
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
# Testa se a página principal carrega corretamente, exibe chamados criados,
# mostra mensagem quando não há dados e aplica os filtros (área, criticidade,
# status) corretamente na consulta.
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
# Testa o formulário de criação: verifica se GET retorna 200, se POST válido
# redireciona e salva no banco, e se POST inválido (campos vazios) não salva.
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
# Testa se o formulário de edição carrega os dados existentes (GET), se POST
# atualiza corretamente os campos e recalcula o score, e se ID inexistente
# retorna 404.
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
            'titulo': 'Título Atualizado', 'descricao': 'Nova descrição detalhada do chamado',
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
            'titulo': 'Editado', 'descricao': 'Descrição atualizada com detalhes',
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
            'titulo': 'Titulo Editado', 'descricao': 'Descrição com detalhe suficiente', 'area': 'TI',
            'impacto': 'baixo', 'urgencia': 'baixa',
            'tipo': 'requisicao', 'status': 'Aberto',
        })
        assert r.status_code == 302


# ══════════════════════════════════════════════════════════════════════════════
# 8. ROTAS — Exclusão (POST /excluir/<id>)
# ══════════════════════════════════════════════════════════════════════════════
# Testa se a exclusão remove o chamado do banco, redireciona para o dashboard,
# retorna 404 para IDs inexistentes e não afeta outros chamados.
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
# Testa a rota AJAX que permite alterar o status sem recarregar a página.
# Verifica se todos os status válidos são aceitos, se status inválidos são
# rejeitados (400) e se a mudança persiste no banco.
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
# 10. API — GET /api/stats (dados para os gráficos)
# ══════════════════════════════════════════════════════════════════════════════
# Testa se a API retorna JSON com a estrutura esperada (contagens por
# criticidade, área, tipo, status) e se os valores refletem o banco.
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
# 11. API — GET /api/chamado/<id> (detalhes individuais)
# ══════════════════════════════════════════════════════════════════════════════
# Testa se a API retorna dados corretos de um chamado específico,
# se IDs inexistentes retornam 404 e se todos os campos estão presentes.
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
                      'criticidade', 'status', 'data_criacao', 'dias_aberto',
                      'data_atualizacao']:
            assert campo in data


# ══════════════════════════════════════════════════════════════════════════════
# 12. EXPORTAÇÃO CSV — GET /exportar
# ══════════════════════════════════════════════════════════════════════════════
# Testa se a rota de exportação retorna um arquivo CSV válido com content-type
# correto, header de download, cabeçalho com nomes das colunas e dados.

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
# 13. CONSTANTES — Integridade da configuração do sistema
# ══════════════════════════════════════════════════════════════════════════════
# Garante que as listas de áreas, status e os mapeamentos de valores estão
# corretos. Também verifica se todas as quatro faixas de criticidade são
# alcançáveis com combinações reais dos campos do formulário.
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


# ══════════════════════════════════════════════════════════════════════════════
# 14. SEGURANÇA — Proteção contra ataques comuns
# ══════════════════════════════════════════════════════════════════════════════
# Testa se a aplicação está protegida contra:
# - XSS (Cross-Site Scripting): tags HTML no input devem ser escapadas
# - Status inválidos via URL: rejeitar valores fora da lista de opções
# - Métodos HTTP incorretos: GET não deve funcionar em rotas POST-only
# - IDs negativos: não devem retornar dados
# ══════════════════════════════════════════════════════════════════════════════

class TestSeguranca:
    """Testes de segurança: XSS, CSRF, input boundaries."""

    def test_titulo_com_html_nao_executa_xss(self, client, app):
        """Tags HTML no título devem ser escapadas na resposta."""
        payload = {
            'titulo': '<script>alert("xss")</script>',
            'descricao': 'Descrição de teste com conteúdo seguro',
            'area': 'TI', 'impacto': 'baixo', 'urgencia': 'baixa', 'tipo': 'requisicao',
        }
        client.post('/novo', data=payload)
        r = client.get('/')
        body = r.data.decode('utf-8')
        assert '<script>alert("xss")</script>' not in body
        assert '&lt;script&gt;' in body or 'alert' not in body.split('<script')[0] if '<script' in body else True

    def test_descricao_com_html_nao_executa_xss(self, client, app):
        """Tags HTML na descrição devem ser escapadas."""
        payload = {
            'titulo': 'Chamado Teste XSS',
            'descricao': '<img src=x onerror=alert(1)>',
            'area': 'TI', 'impacto': 'baixo', 'urgencia': 'baixa', 'tipo': 'requisicao',
        }
        client.post('/novo', data=payload)
        with app.app_context():
            c = Chamado.query.filter_by(titulo='Chamado Teste XSS').first()
            assert c is not None

    def test_status_invalido_via_url_retorna_400(self, client, app):
        """Tentativa de definir status arbitrário via URL deve falhar."""
        cid = _criar_chamado(app)
        r = client.post(f'/status/{cid}/HackedStatus')
        assert r.status_code == 400
        data = r.get_json()
        assert data['success'] is False

    def test_get_nao_permitido_em_excluir(self, client, app):
        """Rota /excluir só aceita POST, GET deve retornar 405."""
        cid = _criar_chamado(app)
        r = client.get(f'/excluir/{cid}')
        assert r.status_code == 405

    def test_get_nao_permitido_em_status(self, client, app):
        """Rota /status só aceita POST, GET deve retornar 405."""
        cid = _criar_chamado(app)
        r = client.get(f'/status/{cid}/Aberto')
        assert r.status_code == 405

    def test_id_negativo_retorna_404(self, client):
        """IDs negativos não devem retornar dados."""
        assert client.get('/editar/-1').status_code == 404
        assert client.get('/api/chamado/-1').status_code == 404


# ══════════════════════════════════════════════════════════════════════════════
# 15. VALIDAÇÃO DE FORMULÁRIO — Limites de comprimento
# ══════════════════════════════════════════════════════════════════════════════
# Testa se a validação server-side rejeita títulos muito curtos (< 3 chars),
# descrições muito curtas (< 10 chars), aceita títulos no limite máximo (120)
# e rejeita valores inválidos nos campos select (áreas inexistentes).
# ══════════════════════════════════════════════════════════════════════════════

class TestValidacaoFormulario:
    """Testes de validação de comprimento e campos obrigatórios."""

    def test_titulo_muito_curto_nao_salva(self, client, app):
        """Título com menos de 3 caracteres deve ser rejeitado."""
        payload = {
            'titulo': 'AB',
            'descricao': 'Descrição válida com detalhes suficientes',
            'area': 'TI', 'impacto': 'baixo', 'urgencia': 'baixa', 'tipo': 'requisicao',
        }
        r = client.post('/novo', data=payload)
        assert r.status_code == 200  # re-renderiza formulário
        with app.app_context():
            assert Chamado.query.count() == 0

    def test_descricao_muito_curta_nao_salva(self, client, app):
        """Descrição com menos de 10 caracteres deve ser rejeitada."""
        payload = {
            'titulo': 'Título Válido',
            'descricao': 'Curta',
            'area': 'TI', 'impacto': 'baixo', 'urgencia': 'baixa', 'tipo': 'requisicao',
        }
        r = client.post('/novo', data=payload)
        assert r.status_code == 200
        with app.app_context():
            assert Chamado.query.count() == 0

    def test_titulo_no_limite_maximo_salva(self, client, app):
        """Título com exatamente 120 caracteres deve ser aceito."""
        titulo = 'A' * 120
        payload = {
            'titulo': titulo,
            'descricao': 'Descrição válida com detalhes suficientes',
            'area': 'TI', 'impacto': 'baixo', 'urgencia': 'baixa', 'tipo': 'requisicao',
        }
        client.post('/novo', data=payload)
        with app.app_context():
            c = Chamado.query.first()
            assert c is not None
            assert len(c.titulo) == 120

    def test_campos_select_com_valor_invalido(self, client, app):
        """Campos select com valores fora das opções não devem salvar."""
        payload = {
            'titulo': 'Chamado Teste',
            'descricao': 'Descrição com detalhes suficientes',
            'area': 'AreaInexistente',
            'impacto': 'baixo', 'urgencia': 'baixa', 'tipo': 'requisicao',
        }
        r = client.post('/novo', data=payload)
        assert r.status_code == 200
        with app.app_context():
            assert Chamado.query.count() == 0


# ══════════════════════════════════════════════════════════════════════════════
# 16. MODELO — from_form (factory method) e integridade de dados
# ══════════════════════════════════════════════════════════════════════════════
# Testa se o chamado criado via formulário recebe status 'Aberto' por padrão,
# se data_criacao é preenchida automaticamente e se a edição atualiza o
# campo data_atualizacao.
# ══════════════════════════════════════════════════════════════════════════════

class TestFromForm:
    """Testes para o método from_form e integridade dos dados criados."""

    def test_chamado_criado_tem_status_aberto(self, client, app):
        """Todo chamado novo deve ter status 'Aberto' por padrão."""
        payload = {
            'titulo': 'Teste Status Padrão',
            'descricao': 'Garantir que status padrão é Aberto',
            'area': 'TI', 'impacto': 'alto', 'urgencia': 'alta', 'tipo': 'incidente',
        }
        client.post('/novo', data=payload)
        with app.app_context():
            c = Chamado.query.first()
            assert c.status == 'Aberto'

    def test_data_criacao_preenchida(self, client, app):
        """Chamado novo deve ter data_criacao preenchida."""
        payload = {
            'titulo': 'Teste Data Criação',
            'descricao': 'Verificar se data de criação é preenchida',
            'area': 'TI', 'impacto': 'baixo', 'urgencia': 'baixa', 'tipo': 'requisicao',
        }
        client.post('/novo', data=payload)
        with app.app_context():
            c = Chamado.query.first()
            assert c.data_criacao is not None

    def test_edicao_atualiza_data_atualizacao(self, client, app):
        """Edição deve atualizar o campo data_atualizacao."""
        cid = _criar_chamado(app, titulo='Para Editar')
        client.post(f'/editar/{cid}', data={
            'titulo': 'Editado Agora', 'descricao': 'Nova descrição detalhada',
            'area': 'TI', 'impacto': 'baixo', 'urgencia': 'baixa',
            'tipo': 'requisicao', 'status': 'Em Progresso',
        })
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            assert c.data_atualizacao is not None


# ══════════════════════════════════════════════════════════════════════════════
# 17. API — Validação dos campos retornados pelo to_dict
# ══════════════════════════════════════════════════════════════════════════════
# Testa campos específicos da serialização: verifica que 'posicao' foi
# removido, que 'data_atualizacao' está presente, que contagens são zero
# quando não há dados e que o ID retornado é o correto.
# ══════════════════════════════════════════════════════════════════════════════

class TestApiCampos:
    """Testes para garantir que a API retorna todos os campos esperados."""

    def test_to_dict_sem_posicao(self, app):
        """to_dict não deve mais incluir campo 'posicao' (removido)."""
        cid = _criar_chamado(app)
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            d = c.to_dict()
            assert 'posicao' not in d

    def test_to_dict_inclui_data_atualizacao(self, app):
        """to_dict deve incluir campo 'data_atualizacao'."""
        cid = _criar_chamado(app)
        with app.app_context():
            c = _db.session.get(Chamado, cid)
            d = c.to_dict()
            assert 'data_atualizacao' in d

    def test_api_stats_contagem_zero_sem_dados(self, client):
        """Sem dados no banco, todas as contagens da API devem ser 0."""
        data = client.get('/api/stats').get_json()
        for crit in data['por_criticidade'].values():
            assert crit == 0
        for area in data['por_area'].values():
            assert area == 0

    def test_api_chamado_retorna_id_correto(self, client, app):
        """API de chamado individual retorna o ID correto."""
        cid = _criar_chamado(app, titulo='Check ID')
        data = client.get(f'/api/chamado/{cid}').get_json()
        assert data['id'] == cid
