"""
Persistência de preferências do usuário entre sessões/refreshes.

Salva e carrega um JSON simples em disco. Ao iniciar, injeta os valores
salvos no st.session_state antes de cada widget ser renderizado.
"""

import json
import streamlit as st
from pathlib import Path
from datetime import date

_PREFS_FILE = Path(__file__).parent.parent / "user_prefs.json"


def _default_prefs() -> dict:
    return {
        # Dashboard — portfólio e análise
        "_portfolio":              [],
        "_analysis_pos_idx":       0,
        "dash_descontar_custodia": False,
        "dash_choque_stress":      2.0,
        # Simulador
        "sim_categoria":           None,
        "sim_titulo":              None,
        "sim_valor":               10_000.0,
        "sim_ipca_baixo":          3.0,
        "sim_ipca_base":           4.5,
        "sim_ipca_estresse":       9.0,
        "sim_prazo_saida":         3,
        "sim_ativos_sel":          [],
        # Qual Ativo
        "bat_horizonte":           3,
        "bat_capital":             10_000.0,
        "bat_com_ir":              True,
        "bat_ipca":                5.0,
        "bat_selic":               13.0,
        "bat_choque":              1.0,
        "bat_selecionados":        [
            "Tesouro Selic 2031",
            "Tesouro Prefixado 2029",
            "Tesouro Prefixado 2032",
            "Tesouro IPCA+ 2032",
            "Tesouro IPCA+ 2040",
        ],
        # Comparar Produtos
        "cmp_horizonte":           2,
        "cmp_capital":             50_000.0,
        "cmp_ipca":                5.0,
        "cmp_taxa_ipca_plus":      7.0,
        "cmp_taxa_pre":            14.5,
        "cmp_selic":               13.25,
        "cmp_cdb":                 14.0,
        "cmp_lci":                 11.5,
        "cmp_lca":                 11.2,
    }


def carregar() -> dict:
    """Lê o JSON de disco. Retorna defaults se não existir."""
    defaults = _default_prefs()
    if not _PREFS_FILE.exists():
        return defaults
    try:
        with _PREFS_FILE.open("r", encoding="utf-8") as f:
            saved = json.load(f)
        defaults.update(saved)
        return defaults
    except Exception:
        return defaults


def salvar(prefs: dict) -> None:
    """Faz merge com o JSON existente e grava. Datas viram string ISO."""
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


def inicializar_session(prefs: dict) -> None:
    """
    Injeta os valores salvos no session_state apenas para chaves que ainda
    não foram definidas nesta sessão. Isso garante que a primeira interação
    do usuário não seja sobrescrita pelos defaults do disco.
    """
    for k, v in prefs.items():
        if k not in st.session_state:
            # Converte strings ISO de volta para date quando necessário
            if isinstance(v, str) and len(v) == 10:
                try:
                    st.session_state[k] = date.fromisoformat(v)
                    continue
                except ValueError:
                    pass
            st.session_state[k] = v
