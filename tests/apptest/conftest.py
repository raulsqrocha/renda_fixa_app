"""
Conftest exclusivo dos testes de UI (streamlit.testing.v1.AppTest).

O conftest.py pai (tests/conftest.py) substitui `streamlit` por um MagicMock
para permitir testar funções puras sem runtime do Streamlit. AppTest precisa
do pacote streamlit REAL — aqui desfazemos o mock (e qualquer módulo do
projeto já importado com ele) antes de qualquer teste desta pasta rodar.

Por isso esta suíte deve ser executada como invocação separada do pytest
(`pytest tests/apptest`), nunca junto com `pytest tests/` — misturar as duas
no mesmo processo contamina o sys.modules em uma direção ou na outra,
dependendo da ordem de coleta.
"""

import sys
from unittest.mock import MagicMock

import pytest

for _nome in list(sys.modules):
    if (
        _nome == "streamlit"
        or _nome.startswith("streamlit.")
        or _nome.startswith(("core", "telas"))
    ):
        del sys.modules[_nome]

import streamlit as _st  # noqa: E402

assert not isinstance(_st, MagicMock), (
    "streamlit real não foi carregado — verifique se está instalado "
    "(requirements.txt) e se nenhum outro conftest mockou o módulo antes deste."
)


@pytest.fixture(autouse=True)
def _sem_rede_externa(monkeypatch):
    """
    Impede chamadas de rede reais (BCB, Tesouro Transparente) nos testes de UI.

    Sem isso, cada página bate em APIs externas de verdade — lento e instável
    (timeouts variam com a rede do ambiente). Forçar falha imediata em
    `_get_com_retry` faz todo `core.dados.buscar_*` cair no caminho de
    fallback local já existente no app, que é exatamente o que queremos
    exercitar em um teste determinístico.
    """
    import requests

    def _falha(*_args, **_kwargs):
        raise requests.exceptions.ConnectionError("rede desabilitada em tests/apptest")

    monkeypatch.setattr("core.dados._get_com_retry", _falha)


@pytest.fixture(autouse=True)
def _sem_persistencia_em_disco(monkeypatch):
    """
    Impede leitura/escrita em user_prefs.json durante os testes de UI.

    core/persistencia.py só toca o disco fora do Streamlit Cloud (_IS_CLOUD).
    Localmente esse arquivo guarda o portfólio real de quem está rodando o
    app — sem este isolamento, cada teste leria (e `salvar()` sobrescreveria)
    dados pessoais de verdade. Forçar _IS_CLOUD=True faz `carregar()` sempre
    devolver os defaults e `salvar()` virar no-op, exatamente como acontece
    em produção no Streamlit Cloud.
    """
    monkeypatch.setattr("core.persistencia._IS_CLOUD", True)
