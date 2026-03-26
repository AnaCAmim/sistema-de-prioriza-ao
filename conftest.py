# =============================================================================
# conftest.py — Configuração global do pytest
# =============================================================================
# Este arquivo é automaticamente carregado pelo pytest antes de executar
# qualquer teste. Sua função principal aqui é garantir que os módulos do
# projeto (app.py, models.py, etc.) possam ser importados nos testes,
# adicionando o diretório raiz do projeto ao sys.path (caminho de busca
# de módulos do Python). Sem isso, o pytest não encontraria os imports.
# =============================================================================

import sys
import os

# Adiciona o diretório onde este arquivo está localizado (raiz do projeto)
# ao início da lista de caminhos do Python, permitindo imports como:
# from app import app
# from models import Chamado
sys.path.insert(0, os.path.dirname(__file__))
