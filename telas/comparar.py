"""
Tela 4 — Comparar Produtos: CDB / LCI / LCA vs. Tesouro Direto

Responde: dado meu perfil de tributação e horizonte, qual produto entrega
mais renda real — um título público ou um produto bancário isentos/tributados?
"""

import streamlit as st
import pandas as pd
import plotly.graph_objects as go

from core.financas import (
    aliquota_ir_renda_fixa,
    formatar_brl,
)
from core.persistencia import carregar, salvar, inicializar_session
from core.dados import timestamp_ultima_atualizacao, chave_cache_mercado

_FUNDO = "#0E1117"


def _taxa_equivalente_isento(taxa_tributada: float, aliq_ir: float) -> float:
    """Taxa líquida de um produto tributado, equivalente a uma taxa isenta."""
    return taxa_tributada * (1 - aliq_ir)


def _taxa_bruta_necessaria(taxa_isenta: float, aliq_ir: float) -> float:
    """Qual taxa bruta um produto tributado precisa ter para empatar com um isento."""
    if aliq_ir >= 1.0:
        return float("inf")
    return taxa_isenta / (1 - aliq_ir)


def render():
    """Tela 4 — Comparar Produtos: Tesouro vs. CDB/LCI/LCA com equivalência de IR."""
    st.session_state["_page_id"] = "comparar"

    _prefs = carregar()
    inicializar_session(_prefs)

    st.markdown(
        '<p class="titulo-principal">Comparar Produtos</p>'
        '<p class="subtitulo">CDB, LCI e LCA versus Tesouro Direto — descubra qual produto '
        'entrega mais retorno real dado o seu horizonte e perfil de tributação.</p>',
        unsafe_allow_html=True,
    )
    _ts = timestamp_ultima_atualizacao(chave_cache_mercado())
    st.caption(f"✅ Taxas de referência · carregadas às **{_ts.strftime('%H:%M')}** (atualiza a cada 2h)")
    st.divider()

    # -----------------------------------------------------------------------
    # Inputs
    # -----------------------------------------------------------------------
    st.subheader("⚙️  Configure a Comparação")

    col_i1, col_i2, col_i3 = st.columns(3)

    with col_i1:
        horizonte = st.slider(
            "Horizonte de investimento (anos)",
            min_value=1, max_value=10, value=2, step=1,
            key="cmp_horizonte",
        )
        capital = st.number_input(
            "Capital Inicial (R$)",
            min_value=100.0, max_value=5_000_000.0,
            value=50_000.0, step=1_000.0, format="%.2f",
            key="cmp_capital",
        )
        ipca = st.number_input(
            "IPCA projetado (% a.a.)",
            min_value=1.0, max_value=15.0,
            value=5.0, step=0.1, format="%.1f",
            key="cmp_ipca",
        )

    with col_i2:
        st.markdown("**Tesouro IPCA+**")
        taxa_ipca_plus = st.number_input(
            "Taxa real contratada (% a.a.)",
            min_value=1.0, max_value=20.0,
            value=7.0, step=0.05, format="%.2f",
            help="Taxa real IPCA+ ofertada atualmente no Tesouro Direto.",
            key="cmp_taxa_ipca_plus",
        )
        st.markdown("**Tesouro Prefixado**")
        taxa_pre = st.number_input(
            "Taxa pré nominal (% a.a.)",
            min_value=1.0, max_value=30.0,
            value=14.5, step=0.05, format="%.2f",
            help="Taxa nominal do Prefixado atualmente ofertada no Tesouro Direto.",
            key="cmp_taxa_pre",
        )
        st.markdown("**Tesouro Selic**")
        selic = st.number_input(
            "Selic projetada (% a.a.)",
            min_value=1.0, max_value=30.0,
            value=14.75, step=0.05, format="%.2f",
            help="Taxa Selic média esperada no período.",
            key="cmp_selic",
        )

    with col_i3:
        st.markdown("**Produtos Bancários**")
        taxa_cdb = st.number_input(
            "CDB (% a.a. bruto)",
            min_value=1.0, max_value=30.0,
            value=14.0, step=0.1, format="%.2f",
            help="Taxa bruta anual ofertada pelo CDB. Sofre IR regressivo.",
            key="cmp_cdb",
        )
        taxa_lci = st.number_input(
            "LCI (% a.a. bruto isento)",
            min_value=1.0, max_value=20.0,
            value=11.5, step=0.1, format="%.2f",
            help="Taxa bruta do LCI. Isento de IR para pessoa física.",
            key="cmp_lci",
        )
        taxa_lca = st.number_input(
            "LCA (% a.a. bruto isento)",
            min_value=1.0, max_value=20.0,
            value=11.2, step=0.1, format="%.2f",
            help="Taxa bruta da LCA. Isento de IR para pessoa física.",
            key="cmp_lca",
        )

    st.divider()

    # -----------------------------------------------------------------------
    # Cálculos
    # -----------------------------------------------------------------------
    aliq_ir    = aliquota_ir_renda_fixa(horizonte)
    ipca_f     = ipca / 100
    H          = float(horizonte)

    # Tesouro IPCA+: taxa real × IPCA = taxa nominal, com IR
    taxa_nom_ipca = (1 + taxa_ipca_plus / 100) * (1 + ipca_f) - 1
    ret_ipca_bruto = (1 + taxa_nom_ipca) ** H - 1
    ret_ipca_liq   = ret_ipca_bruto * (1 - aliq_ir) if ret_ipca_bruto > 0 else ret_ipca_bruto

    # Tesouro Prefixado: taxa nominal, com IR
    ret_pre_bruto  = (1 + taxa_pre / 100) ** H - 1
    ret_pre_liq    = ret_pre_bruto * (1 - aliq_ir) if ret_pre_bruto > 0 else ret_pre_bruto

    # Tesouro Selic: pós-fixado, com IR
    ret_selic_bruto = (1 + selic / 100) ** H - 1
    ret_selic_liq   = ret_selic_bruto * (1 - aliq_ir) if ret_selic_bruto > 0 else ret_selic_bruto

    # CDB: taxa bruta nominal, com IR
    ret_cdb_bruto   = (1 + taxa_cdb / 100) ** H - 1
    ret_cdb_liq     = ret_cdb_bruto * (1 - aliq_ir) if ret_cdb_bruto > 0 else ret_cdb_bruto

    # LCI e LCA: ISENTOS de IR para PF
    ret_lci = (1 + taxa_lci / 100) ** H - 1
    ret_lca = (1 + taxa_lca / 100) ** H - 1

    # Retorno real (descontando IPCA)
    def _real(ret_liq):
        return (1 + ret_liq) / (1 + ipca_f) ** H - 1

    produtos = [
        {"Produto": "Tesouro IPCA+",    "taxa_str": f"IPCA+ {taxa_ipca_plus:.2f}%",  "Retorno Bruto": ret_ipca_bruto,  "Retorno Líquido": ret_ipca_liq,  "IR": aliq_ir, "Isento": False},
        {"Produto": "Tesouro Prefixado","taxa_str": f"{taxa_pre:.2f}%",               "Retorno Bruto": ret_pre_bruto,   "Retorno Líquido": ret_pre_liq,   "IR": aliq_ir, "Isento": False},
        {"Produto": "Tesouro Selic",    "taxa_str": f"Selic {selic:.2f}%",            "Retorno Bruto": ret_selic_bruto, "Retorno Líquido": ret_selic_liq, "IR": aliq_ir, "Isento": False},
        {"Produto": "CDB",              "taxa_str": f"{taxa_cdb:.2f}%",               "Retorno Bruto": ret_cdb_bruto,   "Retorno Líquido": ret_cdb_liq,   "IR": aliq_ir, "Isento": False},
        {"Produto": "LCI",              "taxa_str": f"{taxa_lci:.2f}% (isento)",      "Retorno Bruto": ret_lci,         "Retorno Líquido": ret_lci,       "IR": 0.0,     "Isento": True},
        {"Produto": "LCA",              "taxa_str": f"{taxa_lca:.2f}% (isento)",      "Retorno Bruto": ret_lca,         "Retorno Líquido": ret_lca,       "IR": 0.0,     "Isento": True},
    ]

    melhor = max(produtos, key=lambda p: p["Retorno Líquido"])
    # CDB pode ter retorno maior mas risco de crédito diferente — avisamos no insight

    # -----------------------------------------------------------------------
    # Cards de resultado
    # -----------------------------------------------------------------------
    st.subheader(f"📊  Comparativo — Horizonte de {horizonte} Ano(s) · IR {aliq_ir*100:.1f}%")
    st.caption(f"Capital: {formatar_brl(capital)} · IPCA projetado: {ipca:.1f}% a.a. · Alíquota IR: {aliq_ir*100:.1f}%")

    cols = st.columns(len(produtos))
    for col, p in zip(cols, produtos):
        nome = p["Produto"]
        rl   = p["Retorno Líquido"]
        vf   = capital * (1 + rl)
        lucro = vf - capital
        is_winner = nome == melhor["Produto"]
        with col:
            st.metric(
                label=f"{'🏆 ' if is_winner else ''}{nome}{'  ✨Isento' if p['Isento'] else ''}",
                value=f"{rl*100:.2f}%",
                delta=formatar_brl(lucro),
                delta_color="normal" if lucro >= 0 else "inverse",
                help=(
                    f"Bruto: {p['Retorno Bruto']*100:.2f}% | "
                    f"IR: {p['IR']*100:.1f}% | "
                    f"Líquido: {rl*100:.2f}% | "
                    f"Valor final: {formatar_brl(vf)}"
                ),
            )

    # -----------------------------------------------------------------------
    # Tabela detalhada
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("📋  Tabela Comparativa Detalhada")

    rows = []
    for p in sorted(produtos, key=lambda x: x["Retorno Líquido"], reverse=True):
        vf     = capital * (1 + p["Retorno Líquido"])
        real   = _real(p["Retorno Líquido"])
        rows.append({
            "Produto":            p["Produto"],
            "Taxa Bruta a.a.":    p["taxa_str"],
            "IR":                 "Isento" if p["Isento"] else f"{p['IR']*100:.1f}%",
            "Retorno Bruto":      f"{p['Retorno Bruto']*100:.2f}%",
            "Retorno Líquido":    f"{p['Retorno Líquido']*100:.2f}%",
            "Retorno Real":       f"{real*100:.2f}%",
            "Valor Final":        formatar_brl(vf),
            "Ranking":            "🏆" if p["Produto"] == melhor["Produto"] else "",
        })

    st.dataframe(pd.DataFrame(rows), hide_index=True, use_container_width=True)

    # -----------------------------------------------------------------------
    # Gráfico de barras
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("📈  Retorno Líquido por Produto")

    _COR_PRODUTO = {
        "Tesouro IPCA+":     "#a5d6a7",  # verde suave
        "Tesouro Prefixado": "#ef9a9a",  # vermelho suave
        "Tesouro Selic":     "#4fc3f7",  # azul claro
        "CDB":               "#ce93d8",  # roxo
        "LCI":               "#fff176",  # amarelo
        "LCA":               "#ffcc80",  # laranja
    }

    nomes    = [p["Produto"] for p in produtos]
    rets_liq = [p["Retorno Líquido"] * 100 for p in produtos]
    cores    = [_COR_PRODUTO.get(p["Produto"], "#90caf9") for p in produtos]

    fig = go.Figure(go.Bar(
        x=nomes,
        y=rets_liq,
        marker_color=cores,
        text=[f"{r:.2f}%" for r in rets_liq],
        textposition="outside",
        hovertemplate="%{x}: %{y:.2f}%<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor=_FUNDO, plot_bgcolor=_FUNDO,
        font=dict(color="#FAFAFA", family="Inter"),
        yaxis=dict(title="Retorno Líquido (%)", gridcolor="#2D3748"),
        xaxis=dict(gridcolor="#2D3748"),
        margin=dict(t=30, b=10),
        height=360,
        showlegend=False,
    )
    st.plotly_chart(fig, use_container_width=True)

    # -----------------------------------------------------------------------
    # Taxa equivalente
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader("🔄  Taxa Equivalente — Quebrando a Isenção do IR")

    st.markdown(
        "Qual taxa **bruta** um CDB precisa pagar para empatar com um LCI/LCA isento?"
    )

    col_eq1, col_eq2, col_eq3 = st.columns(3)
    equiv_lci = _taxa_bruta_necessaria(taxa_lci / 100, aliq_ir) * 100
    equiv_lca = _taxa_bruta_necessaria(taxa_lca / 100, aliq_ir) * 100

    with col_eq1:
        st.metric(
            "CDB mínimo p/ empatar LCI",
            f"{equiv_lci:.2f}% a.a.",
            f"LCI isento a {taxa_lci:.2f}% a.a.",
            delta_color="off",
            help="Taxa bruta que o CDB precisa pagar para, após IR, igualar o LCI isento.",
        )
        st.caption(
            f"CDB abaixo de **{equiv_lci:.2f}% a.a.** perde para o LCI de {taxa_lci:.2f}% "
            f"(após {aliq_ir*100:.1f}% IR, CDB fica com "
            f"{_taxa_equivalente_isento(equiv_lci/100, aliq_ir)*100:.2f}% líquido)."
        )
    with col_eq2:
        st.metric(
            "CDB mínimo p/ empatar LCA",
            f"{equiv_lca:.2f}% a.a.",
            f"LCA isento a {taxa_lca:.2f}% a.a.",
            delta_color="off",
            help="Taxa bruta que o CDB precisa pagar para, após IR, igualar o LCA isento.",
        )
    with col_eq3:
        cdb_liq_equiv = _taxa_equivalente_isento(taxa_cdb / 100, aliq_ir) * 100
        st.metric(
            f"CDB {taxa_cdb:.2f}% → líquido",
            f"{cdb_liq_equiv:.2f}% a.a.",
            f"Após IR de {aliq_ir*100:.1f}%",
            delta_color="off",
        )

    # -----------------------------------------------------------------------
    # Insight macro
    # -----------------------------------------------------------------------
    st.divider()
    melhor_retorno = melhor["Retorno Líquido"] * 100
    vf_melhor = capital * (1 + melhor["Retorno Líquido"])
    lucro_melhor = vf_melhor - capital

    _nome_melhor = melhor["Produto"]
    _fgc_aviso = (
        "\n\n⚠️ **Atenção:** o CDB lidera pelo retorno, mas leve em conta o risco de crédito "
        "da instituição emissora. O FGC cobre até **R$ 250 mil por CPF por instituição** — "
        "acima disso, não há garantia. O Tesouro Direto tem garantia soberana (Governo Federal), "
        "sem limite de valor."
        if _nome_melhor == "CDB"
        else "\n\n*LCI/LCA têm cobertura FGC até R$ 250k por inst. O Tesouro tem garantia soberana.*"
    )
    st.info(
        f"**Melhor retorno líquido no horizonte de {horizonte} ano(s):** {_nome_melhor} "
        f"com **{melhor_retorno:.2f}%** acumulado. "
        f"{formatar_brl(capital)} → **{formatar_brl(vf_melhor)}** "
        f"(lucro: {formatar_brl(lucro_melhor)})."
        + _fgc_aviso,
        icon="💡",
    )

    salvar({
        "cmp_horizonte":      st.session_state.get("cmp_horizonte", 2),
        "cmp_capital":        st.session_state.get("cmp_capital", 50_000.0),
        "cmp_ipca":           st.session_state.get("cmp_ipca", 5.0),
        "cmp_taxa_ipca_plus": st.session_state.get("cmp_taxa_ipca_plus", 7.0),
        "cmp_taxa_pre":       st.session_state.get("cmp_taxa_pre", 14.5),
        "cmp_selic":          st.session_state.get("cmp_selic", 14.75),
        "cmp_cdb":            st.session_state.get("cmp_cdb", 14.0),
        "cmp_lci":            st.session_state.get("cmp_lci", 11.5),
        "cmp_lca":            st.session_state.get("cmp_lca", 11.2),
    })


