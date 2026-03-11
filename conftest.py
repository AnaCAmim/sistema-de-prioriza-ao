# conftest.py — garante que pytest encontra os módulos do projeto
import sys
import os

# Adiciona a raiz do projeto ao sys.path para imports funcionarem
sys.path.insert(0, os.path.dirname(__file__))
