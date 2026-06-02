"""
Cálculos de posição do Dashboard — extraídos de dashboard.py para permitir
testes unitários independentes do runtime do Streamlit.
"""

from datetime import date
from typing import TypedDict

import pandas as pd

from core.dados import TITULOS_CONFIG, calcular_vna_em_data
from core.financas import (
    MetricasCarteira,
    calcular_du,
    datas_cupom_ntnb,
    metricas_carteira,
    pu_ntnb,
)


class PosicaoNtnb(TypedDict):
    res: MetricasCarteira
    taxa_mkt_pct: float
    taxa_vda_pct: float | None
    dv: date
    dc: date
    tc: float
    tm: float
    cupom: bool
    pu_c: float
    cpns_h: list
    anos_tot: float
    anos_res: int
    vf: float
    prazo_score: float
    posicao_score: float
    score: float
    taxa_pct: float
    is_simples: bool


class PosicaoSimples(TypedDict):
    res: dict
    taxa_mkt_pct: float
    taxa_vda_pct: None
    dv: date
    dc: date
    tc: float
    tm: float
    cupom: bool
    pu_c: float
    cpns_h: list
    anos_tot: float
    anos_res: int
    vf: float
    prazo_score: float
    posicao_score: float
    score: float
    taxa_pct: float
    tipo_asset: str
    is_simples: bool


# ---------------------------------------------------------------------------
# Constantes do Índice de Saúde (0–100)
# ---------------------------------------------------------------------------

# Prazo: 10 pts base + 7 pts por ano restante, teto de 60 pts
SCORE_PRAZO_BASE = 10.0
SCORE_PRAZO_POR_ANO = 7.0
SCORE_PRAZO_MAX = 60.0

# Posição: 40 pts base + 1,6 pts por % acima do capital investido, piso 0
SCORE_POS_BASE = 40.0
SCORE_POS_SENSI = 1.6
SCORE_POS_MAX = 40.0

# Pré-fixado tem risco de MaM → posicao_score reduzido vs. Selic/bancários
SCORE_POS_PRE = 25.0


# ---------------------------------------------------------------------------
# Cálculo NTN-B (IPCA+, RendA+, Educar+)
# ---------------------------------------------------------------------------


def calcular_posicao_ntnb(
    titulo: str,
    valor: float,
    taxa_pct: float,
    data_compra_str: str,
    *,
    df_titulos: pd.DataFrame,
    df_ipca: pd.DataFrame,
    vna: float,
) -> PosicaoNtnb | None:
    """
    Retorna todas as métricas de uma posição NTN-B (IPCA+/RendA+/Educar+).

    Parâmetros keyword-only evitam passagem posicional acidental dos DataFrames.
    Retorna None se data_compra >= data_vencimento ou PU inválido.
    """
    dc = date.fromisoformat(data_compra_str)
    linha = (
        df_titulos[df_titulos["nome"] == titulo]
        if not df_titulos.empty
        else pd.DataFrame()
    )

    if not linha.empty:
        taxa_mkt_pct = float(linha["taxa_compra"].values[0])
        taxa_vda_pct = (
            float(linha["taxa_venda"].values[0])
            if "taxa_venda" in linha.columns
            else None
        )
        dv = date.fromisoformat(str(linha["vencimento"].values[0])[:10])
    else:
        cfg = TITULOS_CONFIG.get(titulo, {})
        taxa_mkt_pct = taxa_pct + 2.0
        taxa_vda_pct = None
        dv = cfg.get("vencimento", date(2035, 5, 15))

    if dc >= dv:
        return None

    tc, tm = taxa_pct / 100, taxa_mkt_pct / 100
    cupom = "Juros Semestrais" in titulo

    # VNA na data de compra — corrige quantidade e valores absolutos de MaM/carrego
    # pelo IPCA acumulado desde a compra; sem isso ambos ficam subestimados ~IPCA*anos.
    vna_compra = calcular_vna_em_data(df_ipca, dc)

    cpns_c = datas_cupom_ntnb(dc, dv) if cupom else []
    pu_c = pu_ntnb(vna_compra, tc, dc, dv, cpns_c)
    if pu_c <= 0:
        return None

    cpns_h = datas_cupom_ntnb(date.today(), dv) if cupom else []
    res = metricas_carteira(
        valor_investido=valor,
        pu_na_compra=pu_c,
        taxa_real_contratada=tc,
        taxa_real_mercado=tm,
        vna=vna,
        data_hoje=date.today(),
        data_vencimento=dv,
        datas_cupom=cpns_h,
    )

    anos_tot = (dv - dc).days / 365
    # max(1,...) intencional: evita exibir "0 anos restantes" para títulos com < 6 meses até vencimento
    anos_res = max(1, round((dv - date.today()).days / 365))
    # Valor no vencimento: usa carrego do pu_ntnb (já inclui VNA atual e DU/252)
    # Mais correto que valor*(1+tc)^anos pois captura IPCA acumulado e convenção 252.
    vf = res["vencimento"]

    diff_pct = (res["mam"] - valor) / valor * 100
    ps = min(SCORE_PRAZO_MAX, SCORE_PRAZO_BASE + anos_res * SCORE_PRAZO_POR_ANO)
    poss = max(0.0, min(SCORE_POS_MAX, SCORE_POS_BASE + diff_pct * SCORE_POS_SENSI))

    return dict(
        res=res,
        taxa_mkt_pct=taxa_mkt_pct,
        taxa_vda_pct=taxa_vda_pct,
        dv=dv,
        dc=dc,
        tc=tc,
        tm=tm,
        cupom=cupom,
        pu_c=pu_c,
        cpns_h=cpns_h,
        anos_tot=anos_tot,
        anos_res=anos_res,
        vf=vf,
        prazo_score=ps,
        posicao_score=poss,
        score=ps + poss,
        taxa_pct=taxa_pct,
        is_simples=False,
    )


# ---------------------------------------------------------------------------
# Cálculo por accrual (Selic, Pré-Fixado, CDB, LCI, LCA)
# ---------------------------------------------------------------------------


def calcular_posicao_simples(
    titulo: str,
    tipo_asset: str,
    valor: float,
    taxa_pct: float,
    data_compra_str: str,
    vencimento_str: str,
) -> PosicaoSimples | None:
    """
    Cálculo por accrual para títulos sem pricing NTN-B.
    Retorna None se data_compra >= data_vencimento.
    """
    dc = date.fromisoformat(data_compra_str)
    dv = date.fromisoformat(vencimento_str)
    if dc >= dv:
        return None

    tc = taxa_pct / 100
    hoje = date.today()
    # DU/252: convenção ANBIMA/B3 para todos os títulos de renda fixa
    du_d = calcular_du(dc, hoje)
    du_t = calcular_du(dc, dv)
    anos_t = du_t / 252
    # max(1,...) intencional: evita exibir "0 anos restantes" para títulos com < 6 meses até vencimento
    anos_r = max(1, round((dv - hoje).days / 365))
    mam = valor * (1 + tc) ** (du_d / 252)
    vf = valor * (1 + tc) ** (du_t / 252)
    ps = min(SCORE_PRAZO_MAX, SCORE_PRAZO_BASE + anos_r * SCORE_PRAZO_POR_ANO)
    # Selic e bancários: sem risco de MaM → posicao_score pleno
    # Prefixado: tem risco de taxa → posicao_score reduzido
    pos_sc = SCORE_POS_PRE if tipo_asset == "pre" else SCORE_POS_MAX

    return dict(
        res={"mam": mam, "variacao_dia": 0.0, "pu_hoje": 0.0, "quantidade": 1.0},
        taxa_mkt_pct=taxa_pct,
        taxa_vda_pct=None,
        dv=dv,
        dc=dc,
        tc=tc,
        tm=tc,
        cupom=False,
        pu_c=valor,
        cpns_h=[],
        anos_tot=anos_t,
        anos_res=anos_r,
        vf=vf,
        prazo_score=ps,
        posicao_score=pos_sc,
        score=ps + pos_sc,
        taxa_pct=taxa_pct,
        tipo_asset=tipo_asset,
        is_simples=True,
    )
