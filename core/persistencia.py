"""
Persistência de preferências do usuário entre sessões/refreshes.

Em ambiente local: salva e carrega um JSON simples em disco.
Em Streamlit Cloud (HOME=/home/appuser): usa apenas st.session_state —
o arquivo não é gravado, evitando que dados pessoais (portfólio) sejam
compartilhados entre visitantes do app público.
"""

import os
import json
import streamlit as st
from pathlib import Path
from datetime import date

_PREFS_FILE = Path(__file__).parent.parent / "user_prefs.json"

# True quando rodando no Streamlit Cloud (filesystem compartilhado entre usuários)
_IS_CLOUD = os.environ.get("HOME") == "/home/appuser"

# Portfólio de demonstração — carregado por padrão quando não há dados salvos
# (visitante novo no Streamlit Cloud, ou clone local sem user_prefs.json), para
# que o valor do app apareça de imediato em vez de uma tela vazia. mam_cache/
# carrego_cache/anos são placeholders: telas/dashboard.py recalcula esses três
# campos com dados ao vivo para TODA posição a cada render, antes de qualquer
# uso — os valores aqui nunca chegam a ser exibidos sem recálculo.
_PORTFOLIO_DEMO: list = [
    {
        "titulo": "Tesouro IPCA+ 2032",
        "valor": 15_000.0,
        "taxa": 7.50,
        "data_compra": "2025-05-20",
        "mam_cache": 15_000.0,
        "carrego_cache": 15_000.0,
        "vencimento": "2032-08-15",
        "anos": 6,
        "tipo_asset": "ipca_mais",
    },
    {
        "titulo": "Tesouro Selic 2031",
        "valor": 8_000.0,
        "taxa": 14.75,
        "data_compra": "2025-09-10",
        "mam_cache": 8_000.0,
        "carrego_cache": 8_000.0,
        "vencimento": "2031-03-01",
        "anos": 5,
        "tipo_asset": "selic",
    },
    {
        "titulo": "Tesouro Prefixado 2029",
        "valor": 6_000.0,
        "taxa": 14.50,
        "data_compra": "2025-11-01",
        "mam_cache": 6_000.0,
        "carrego_cache": 6_000.0,
        "vencimento": "2029-01-01",
        "anos": 3,
        "tipo_asset": "pre",
    },
]


def _default_prefs() -> dict:
    """Retorna o dicionário de preferências com todos os valores padrão do app."""
    return {
        # Dashboard — portfólio e análise
        "_portfolio": [dict(p) for p in _PORTFOLIO_DEMO],
        "_analysis_pos_idx": 0,
        "dash_descontar_custodia": False,
        "venda_ipca_b": 5.0,
        "dash_choque_stress": 2.0,
        # Formulário de nova posição (datas não têm default — widget define no primeiro run)
        "port_cat": None,
        "port_titulo": None,
        "port_valor": 10_000.0,
        "port_taxa": 5.50,
        # Simulador
        "sim_categoria": None,
        "sim_titulo": None,
        "sim_valor": 10_000.0,
        "sim_ipca_baixo": 3.0,
        "sim_ipca_base": 4.5,
        "sim_ipca_estresse": 9.0,
        "sim_prazo_saida": 3,
        "sim_curva_slope": 0.0,
        "sim_di_jan27": 14.75,
        "sim_di_jan28": 14.70,
        "sim_di_jan29": 14.65,
        "sim_di_jan31": 14.55,
        "sim_di_jan33": 14.40,
        "sim_di_jan35": 14.25,
        "sim_ativos_sel": [],
        # Qual Ativo
        "bat_horizonte": 3,
        "bat_capital": 10_000.0,
        "bat_com_ir": True,
        "bat_ipca": 5.0,
        "bat_selic": 14.75,
        "bat_choque": 1.0,
        "bat_selecionados": [
            "Tesouro Selic 2031",
            "Tesouro Prefixado 2029",
            "Tesouro Prefixado 2032",
            "Tesouro IPCA+ 2032",
            "Tesouro IPCA+ 2040",
        ],
        "bat_perfil": "Moderado",
        # Comparar Produtos
        "cmp_horizonte": 2,
        "cmp_capital": 50_000.0,
        "cmp_ipca": 5.0,
        "cmp_taxa_ipca_plus": 7.0,
        "cmp_taxa_pre": 14.5,
        "cmp_selic": 14.75,
        "cmp_cdb": 14.0,
        "cmp_lci": 11.5,
        "cmp_lca": 11.2,
        # Calculadora de Aportes Mensais (Dashboard — aba Simulações)
        "dash_calc_ipca": 5.0,
        "dash_calc_selic": 14.75,
        "dash_calc_pre": 14.5,
        "dash_calc_ipca_plus": 7.0,
        "dash_calc_cdb": 14.0,
        "dash_calc_lci": 11.5,
        "dash_calc_lca": 11.2,
        "dash_calc_aporte": 500.0,
        "dash_calc_meta": 200_000.0,
        "dash_calc_prazo_proj": 5,
        "dash_calc_prazo_rev": 5,
        "dash_calc_capital": 10_000.0,
        "dash_calc_cap_rev": 10_000.0,
    }


def carregar() -> dict:
    """Lê o JSON de disco. Em cloud, retorna apenas defaults (sem leitura de arquivo)."""
    defaults = _default_prefs()
    if _IS_CLOUD or not _PREFS_FILE.exists():
        return defaults
    try:
        with _PREFS_FILE.open("r", encoding="utf-8") as f:
            saved = json.load(f)
        # Só carrega chaves reconhecidas — evita que chaves órfãs de versões
        # anteriores do app poluam o session_state
        _known = set(defaults) | _DATE_KEYS
        defaults.update({k: v for k, v in saved.items() if k in _known})
        # Garante que campos lista não foram corrompidos no JSON
        for k in ("_portfolio", "sim_ativos_sel", "bat_selecionados"):
            if not isinstance(defaults.get(k), list):
                defaults[k] = _default_prefs()[k]
        # Garante que índice de análise é inteiro válido
        if not isinstance(defaults.get("_analysis_pos_idx"), int):
            defaults["_analysis_pos_idx"] = 0
        return defaults
    except Exception:
        return defaults


def salvar(prefs: dict) -> None:
    """Faz merge com o JSON existente e grava. Em cloud, é no-op."""
    if _IS_CLOUD:
        return
    # Lê o estado atual para não sobrescrever chaves de outras telas
    atual = carregar()
    atual.update(prefs)

    serializable = {}
    for k, v in atual.items():
        if isinstance(v, date):
            serializable[k] = v.isoformat()
        else:
            serializable[k] = v
    try:
        with _PREFS_FILE.open("w", encoding="utf-8") as f:
            json.dump(serializable, f, ensure_ascii=False, indent=2)
    except Exception:
        pass


_DATE_KEYS = frozenset({"port_data", "port_vencimento"})


def inicializar_session(prefs: dict) -> None:
    """
    Injeta os valores salvos no session_state apenas para chaves que ainda
    não foram definidas nesta sessão. Isso garante que a primeira interação
    do usuário não seja sobrescrita pelos defaults do disco.
    """
    for k, v in prefs.items():
        if k not in st.session_state:
            if v is None:
                continue  # deixa o widget usar seu próprio default
            # Converte strings ISO → date apenas para chaves de data conhecidas
            if k in _DATE_KEYS and isinstance(v, str):
                try:
                    st.session_state[k] = date.fromisoformat(v)
                except ValueError:
                    pass  # data corrompida — widget usa seu próprio default
                continue
            st.session_state[k] = v
