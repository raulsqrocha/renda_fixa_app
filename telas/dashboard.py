"""
Tela 1 — Seu Dashboard

Portfólio como visão principal; análise detalhada como drill-down da posição selecionada.
"""

import streamlit as st
import pandas as pd
import calendar as _cal
import base64
from pathlib import Path
from datetime import date, timedelta
from typing import cast

from core.financas import (
    pu_ntnb,
    metricas_carteira,
    serie_paradoxo,
    formatar_brl,
    aliquota_iof_renda_fixa,
    aliquota_ir_renda_fixa,
    fv_mensal,
    pmt_para_meta,
    analise_batalha,
)
from core.dados import (
    obter_dados_completos,
    buscar_selic_meta_bcb,
    buscar_selic_na_data,
    montar_catalogo_batalha,
    CATEGORIAS_TITULOS,
    TITULOS_BATALHA,
    timestamp_ultima_atualizacao,
    chave_cache_mercado,
)
from core.persistencia import carregar, salvar, inicializar_session
from core.graficos import grafico_paradoxo, grafico_score
import plotly.graph_objects as go

from telas._dashboard_metricas import calcular_posicao_ntnb, calcular_posicao_simples


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def _serie_cached(
    vna, taxa_contratada, taxa_mercado, compra, vencimento, qtd, tem_cupom
):
    return serie_paradoxo(
        vna, taxa_contratada, taxa_mercado, compra, vencimento, qtd, tem_cupom
    )


@st.cache_data(show_spinner=False)
def _bull_img_tag() -> str:
    _path = Path(__file__).parent.parent / "assets" / "bull.png"
    if not _path.exists():
        return ""
    _b64 = base64.b64encode(_path.read_bytes()).decode()
    return f'<img src="data:image/png;base64,{_b64}" alt="touro"/>'


def render():
    """Tela 1 — Dashboard principal: portfólio, paradoxo MaM e análise de posição."""
    st.session_state["_page_id"] = "dashboard"

    _prefs = carregar()
    inicializar_session(_prefs)

    # -----------------------------------------------------------------------
    # Cabeçalho
    # -----------------------------------------------------------------------
    st.markdown(
        f"""
<div class="hero-banner">
  <div class="hero-tag">Dashboard Principal</div>
  <div class="hero-title-row">
    <h1 class="hero-title">Renda Fixa <span>CF</span></h1>
    <div class="hero-bull">{_bull_img_tag()}</div>
  </div>
  <p class="hero-subtitle">Visualize o paradoxo da renda fixa: a volatilidade que você
  <em>sente</em> versus a segurança que você <em>tem</em>.</p>
  <p style="font-size:0.72rem; color:#718096; margin:0.4rem 0 0 0; letter-spacing:0.03em;">por Raul Rocha</p>
</div>
""",
        unsafe_allow_html=True,
    )

    with st.spinner("Carregando dados do Tesouro Direto e BCB..."):
        df_ipca, df_titulos, vna = obter_dados_completos()

    _ts = timestamp_ultima_atualizacao(chave_cache_mercado())
    _hora = _ts.strftime("%H:%M")
    _ipca_ok = not df_ipca.empty and df_ipca["data"].max() >= pd.Timestamp(
        date.today() - timedelta(days=60)
    )
    if not df_titulos.empty and _ipca_ok:
        st.caption(
            f"✅ Dados ao vivo — Tesouro Direto e BCB · carregados às **{_hora}** (atualiza a cada 2h)"
        )
    elif not df_titulos.empty:
        st.caption(
            f"⚠️ Preços ao vivo, mas IPCA em modo offline (série histórica local até {df_ipca['data'].max().strftime('%b/%Y')}) "
            f"· carregados às **{_hora}**"
        )
    else:
        st.caption("⚠️ Modo offline — usando dados de referência para preços e IPCA")

    # -----------------------------------------------------------------------
    # Cards de taxa ao vivo — pulso do mercado
    # -----------------------------------------------------------------------
    if not df_titulos.empty:
        _m_sl = df_titulos[
            df_titulos["nome"].str.contains("Selic", na=False)
        ].sort_values("vencimento")
        _m_pre = df_titulos[
            df_titulos["nome"].str.contains("Prefixado", na=False)
            & ~df_titulos["nome"].str.contains("Semestrais", na=False)
        ].sort_values("vencimento")
        _m_ip = df_titulos[df_titulos["nome"] == "Tesouro IPCA+ 2032"]
        if _m_ip.empty:
            _m_ip = df_titulos[
                df_titulos["nome"].str.contains("IPCA\\+", na=False, regex=True)
                & ~df_titulos["nome"].str.contains("Semestrais", na=False)
            ]
        _selic_meta = buscar_selic_meta_bcb()
        _pc1, _pc2, _pc3 = st.columns(3)
        with _pc1:
            if not _m_sl.empty:
                _spread_sl = _m_sl.iloc[0]["taxa_compra"]
                st.metric(
                    "Tesouro Selic",
                    f"~{_selic_meta:.2f}% a.a.",
                    f"Pós-fixado · Selic {_selic_meta:.2f}% + spread {_spread_sl:.2f}%",
                    delta_color="off",
                    help=(
                        "**Por que o valor é aproximado (~)?**\n\n"
                        "O Tesouro Selic é pós-fixado: ele rende *diariamente* a taxa Selic vigente, "
                        "que pode mudar a cada reunião do COPOM (~45 dias).\n\n"
                        f"**Meta Selic atual:** {_selic_meta:.2f}% a.a. (fonte: Banco Central, Série 1178)\n\n"
                        f"**Spread do Tesouro Selic:** +{_spread_sl:.2f}% a.a. "
                        "(pequena taxa adicional paga pelo título acima da Selic pura)\n\n"
                        "O rendimento final do investidor é a **Selic acumulada dia a dia** até o resgate — "
                        "não é possível saber com exatidão hoje quanto será no futuro, pois depende das "
                        "decisões futuras do COPOM. O símbolo **~** indica exatamente isso: é o melhor "
                        "valor de referência disponível agora, não uma taxa travada."
                    ),
                )
        with _pc2:
            if not _m_pre.empty:
                _p = _m_pre.iloc[0]
                st.metric(
                    f"Pré {_p['nome'].split()[-1]}",
                    f"{_p['taxa_compra']:.2f}% a.a.",
                    "Nominal · taxa travada",
                    delta_color="off",
                    help=(
                        "**Taxa nominal pré-fixada** — definida no momento da compra e "
                        "garantida até o vencimento independentemente da inflação ou da Selic.\n\n"
                        "**Risco de MaM:** se você vender antes do vencimento, o preço de "
                        "mercado pode ser maior ou menor que o valor contratado, dependendo "
                        "do nível das taxas de juros no dia da venda.\n\n"
                        "Para maximizar o resultado, o ideal é carregar o título até o vencimento."
                    ),
                )
        with _pc3:
            if not _m_ip.empty:
                _ip = _m_ip.iloc[0]
                _ip_label = _ip["nome"].replace("Tesouro ", "")
                st.metric(
                    f"{_ip_label}",
                    f"{_ip['taxa_compra']:.2f}% real",
                    "IPCA + taxa real",
                    delta_color="off",
                    help=(
                        "**Taxa real** contratada acima do IPCA — seu poder de compra "
                        "cresce a essa taxa independentemente da inflação.\n\n"
                        "O rendimento total é: **(1 + taxa real) × (1 + IPCA) − 1**. "
                        "Por exemplo, com IPCA de 5% e taxa real de 7%, o rendimento "
                        "nominal seria aproximadamente 12,35% a.a.\n\n"
                        "**Risco de MaM:** assim como o Prefixado, uma venda antecipada "
                        "está sujeita à marcação a mercado — quanto mais longo o prazo, "
                        "maior a sensibilidade a variações de taxa."
                    ),
                )

    # -----------------------------------------------------------------------
    # Helper: calcula todas as métricas de uma posição a partir dos inputs
    # -----------------------------------------------------------------------
    def _calcular(titulo: str, valor: float, taxa_pct: float, data_compra_str: str):
        return calcular_posicao_ntnb(
            titulo,
            valor,
            taxa_pct,
            data_compra_str,
            df_titulos=df_titulos,
            df_ipca=df_ipca,
            vna=vna,
        )

    def _calcular_simples(
        titulo: str,
        tipo_asset: str,
        valor: float,
        taxa_pct: float,
        data_compra_str: str,
        vencimento_str: str,
    ):
        return calcular_posicao_simples(
            titulo, tipo_asset, valor, taxa_pct, data_compra_str, vencimento_str
        )

    def _render_calc(default_cap: float):
        """Aba "Simulações": calculadora de aportes mensais com projeção e meta."""
        st.markdown("#### Calculadora de Aportes Mensais")
        st.caption(
            "Simule quanto vai acumular com aportes regulares, ou quanto precisa poupar para atingir uma meta."
        )

        with st.expander("⚙️  Taxas de Referência", expanded=False):
            _dc1, _dc2, _dc3 = st.columns(3)
            with _dc1:
                _dc_ipca = st.number_input(
                    "IPCA projetado (% a.a.)",
                    min_value=1.0,
                    max_value=15.0,
                    value=5.0,
                    step=0.1,
                    format="%.1f",
                    key="dash_calc_ipca",
                )
            with _dc2:
                _dc_selic = st.number_input(
                    "Tesouro Selic (% a.a.)",
                    min_value=1.0,
                    max_value=30.0,
                    value=14.75,
                    step=0.05,
                    format="%.2f",
                    key="dash_calc_selic",
                )
                _dc_pre = st.number_input(
                    "Tesouro Prefixado (% a.a.)",
                    min_value=1.0,
                    max_value=30.0,
                    value=14.5,
                    step=0.05,
                    format="%.2f",
                    key="dash_calc_pre",
                )
                _dc_ipca_plus = st.number_input(
                    "Tesouro IPCA+ (taxa real % a.a.)",
                    min_value=1.0,
                    max_value=20.0,
                    value=7.0,
                    step=0.05,
                    format="%.2f",
                    key="dash_calc_ipca_plus",
                )
            with _dc3:
                _dc_cdb = st.number_input(
                    "CDB (% a.a. bruto)",
                    min_value=1.0,
                    max_value=30.0,
                    value=14.0,
                    step=0.1,
                    format="%.2f",
                    key="dash_calc_cdb",
                )
                _dc_lci = st.number_input(
                    "LCI (% a.a. isento)",
                    min_value=1.0,
                    max_value=20.0,
                    value=11.5,
                    step=0.1,
                    format="%.2f",
                    key="dash_calc_lci",
                )
                _dc_lca = st.number_input(
                    "LCA (% a.a. isento)",
                    min_value=1.0,
                    max_value=20.0,
                    value=11.2,
                    step=0.1,
                    format="%.2f",
                    key="dash_calc_lca",
                )
            if not df_titulos.empty:
                _sl_live = df_titulos[
                    df_titulos["nome"].str.contains("Selic", na=False)
                ]
                _pre_live = df_titulos[
                    df_titulos["nome"].str.contains("Prefixado", na=False)
                    & ~df_titulos["nome"].str.contains("Semestrais", na=False)
                ]
                _ip_live = df_titulos[df_titulos["nome"] == "Tesouro IPCA+ 2032"]
                _live_pts = []
                if not _sl_live.empty:
                    _live_pts.append(f"Selic {_sl_live.iloc[0]['taxa_compra']:.2f}%")
                if not _pre_live.empty:
                    _live_pts.append(f"Pré {_pre_live.iloc[0]['taxa_compra']:.2f}%")
                if not _ip_live.empty:
                    _live_pts.append(
                        f"IPCA+ 2032: {_ip_live.iloc[0]['taxa_compra']:.2f}% real"
                    )
                if _live_pts:
                    st.caption("📡 Taxas ao vivo — " + " · ".join(_live_pts))

        _dc_ipca_f = _dc_ipca / 100
        _taxas_dc = {
            "Tesouro IPCA+": (1 + _dc_ipca_plus / 100) * (1 + _dc_ipca_f) - 1,
            "Tesouro Prefixado": _dc_pre / 100,
            "Tesouro Selic": _dc_selic / 100,
            "CDB": _dc_cdb / 100,
            "LCI": _dc_lci / 100,
            "LCA": _dc_lca / 100,
        }
        _isentos_dc = {"LCI", "LCA"}

        _dtab_proj, _dtab_rev = st.tabs(
            [
                "Se eu poupar X/mês, quanto terei?",
                "Quanto preciso poupar por mês?",
            ]
        )

        with _dtab_proj:
            _dtp1, _dtp2 = st.columns(2)
            with _dtp1:
                _dc_pmt = st.number_input(
                    "Aporte mensal (R$)",
                    min_value=0.0,
                    max_value=100_000.0,
                    value=500.0,
                    step=100.0,
                    format="%.2f",
                    key="dash_calc_aporte",
                )
                _dc_cap = st.number_input(
                    "Capital inicial (R$)",
                    min_value=0.0,
                    max_value=5_000_000.0,
                    value=default_cap,
                    step=500.0,
                    format="%.2f",
                    key="dash_calc_capital",
                )
            with _dtp2:
                _dc_prazo_p = st.slider(
                    "Prazo (anos)",
                    min_value=1,
                    max_value=30,
                    value=5,
                    key="dash_calc_prazo_proj",
                )

            _dc_n_p = _dc_prazo_p * 12

            _dc_rows_p = []
            for _dn, _dt in _taxas_dc.items():
                _da = 0.0 if _dn in _isentos_dc else aliquota_ir_renda_fixa(_dc_prazo_p)
                _dr = fv_mensal(_dt, _dc_n_p, _dc_cap, _dc_pmt, _da)
                _dc_rows_p.append(
                    {
                        "Produto": _dn,
                        "Valor Final": formatar_brl(_dr["fv_liq"]),
                        "Total Investido": formatar_brl(_dr["total_inv"]),
                        "IR pago": formatar_brl(_dr["ir"]),
                        "Ganho Líquido": formatar_brl(_dr["fv_liq"] - _dr["total_inv"]),
                        "_fv": _dr["fv_liq"],
                    }
                )
            _dc_rows_p.sort(key=lambda r: cast(float, r["_fv"]), reverse=True)
            _dc_mp = _dc_rows_p[0]["Produto"] if _dc_rows_p else ""
            _dc_df_p = pd.DataFrame(
                [{k: v for k, v in r.items() if k != "_fv"} for r in _dc_rows_p]
            )
            _dc_df_p.insert(
                0, "🏆", ["🏆" if r["Produto"] == _dc_mp else "" for r in _dc_rows_p]
            )
            st.dataframe(_dc_df_p, hide_index=True, use_container_width=True)

            _dc_anos_r = list(range(0, _dc_prazo_p + 1))
            _dc_fig_p = go.Figure()
            for _dn, _dt in _taxas_dc.items():
                _dc_fig_p.add_trace(
                    go.Scatter(
                        x=_dc_anos_r,
                        y=[
                            fv_mensal(
                                _dt,
                                a * 12,
                                _dc_cap,
                                _dc_pmt,
                                0.0
                                if _dn in _isentos_dc
                                else aliquota_ir_renda_fixa(max(1, a)),
                            )["fv_liq"]
                            for a in _dc_anos_r
                        ],
                        name=_dn,
                        mode="lines",
                        hovertemplate=f"{_dn}: R$ %{{y:,.2f}}<extra></extra>",
                    )
                )
            _dc_fig_p.add_trace(
                go.Scatter(
                    x=_dc_anos_r,
                    y=[_dc_cap + _dc_pmt * a * 12 for a in _dc_anos_r],
                    name="Total Investido",
                    mode="lines",
                    line=dict(dash="dot", color="#718096"),
                    hovertemplate="Total investido: R$ %{y:,.2f}<extra></extra>",
                )
            )
            _dc_fig_p.update_layout(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e0e0",
                yaxis=dict(
                    title="Valor Final (R$)",
                    gridcolor="rgba(255,255,255,0.06)",
                    tickprefix="R$ ",
                    tickformat=",.0f",
                ),
                xaxis=dict(title="Anos", gridcolor="rgba(255,255,255,0.04)"),
                legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.25),
                margin=dict(t=10, b=10),
                height=320,
            )
            st.plotly_chart(_dc_fig_p, use_container_width=True)

        with _dtab_rev:
            _dtr1, _dtr2 = st.columns(2)
            with _dtr1:
                _dc_meta = st.number_input(
                    "Meta (valor final líquido, R$)",
                    min_value=1_000.0,
                    max_value=10_000_000.0,
                    value=200_000.0,
                    step=10_000.0,
                    format="%.2f",
                    key="dash_calc_meta",
                )
                _dc_cap_r = st.number_input(
                    "Capital inicial (R$)",
                    min_value=0.0,
                    max_value=5_000_000.0,
                    value=default_cap,
                    step=500.0,
                    format="%.2f",
                    key="dash_calc_cap_rev",
                )
            with _dtr2:
                _dc_prazo_r = st.slider(
                    "Prazo (anos)",
                    min_value=1,
                    max_value=30,
                    value=5,
                    key="dash_calc_prazo_rev",
                )

            _dc_n_r = _dc_prazo_r * 12
            _dc_aliq_r = aliquota_ir_renda_fixa(_dc_prazo_r)

            _dc_rows_r = []
            for _dn, _dt in _taxas_dc.items():
                _da = 0.0 if _dn in _isentos_dc else _dc_aliq_r
                _dpmt = pmt_para_meta(_dt, _dc_n_r, _dc_cap_r, _dc_meta, _da)
                _dtot = _dc_cap_r + _dpmt * _dc_n_r
                _dc_rows_r.append(
                    {
                        "Produto": _dn,
                        "Aporte Mensal": formatar_brl(_dpmt),
                        "Total Aportado": formatar_brl(_dtot),
                        "Juros trabalham": formatar_brl(_dc_meta - _dtot),
                        "_pmt": _dpmt,
                    }
                )
            _dc_rows_r.sort(key=lambda r: cast(float, r["_pmt"]))
            _dc_mr = _dc_rows_r[0]["Produto"] if _dc_rows_r else ""
            _dc_df_r = pd.DataFrame(
                [{k: v for k, v in r.items() if k != "_pmt"} for r in _dc_rows_r]
            )
            _dc_df_r.insert(
                0, "🏆", ["🏆" if r["Produto"] == _dc_mr else "" for r in _dc_rows_r]
            )
            st.dataframe(_dc_df_r, hide_index=True, use_container_width=True)

            if _dc_rows_r:
                _dc_best = _dc_rows_r[0]
                _dc_worst = _dc_rows_r[-1]
                _dc_diff = cast(float, _dc_worst["_pmt"]) - cast(
                    float, _dc_best["_pmt"]
                )
                _dc_juros = _dc_meta - (
                    _dc_cap_r + cast(float, _dc_best["_pmt"]) * _dc_n_r
                )
                st.info(
                    f"**{_dc_best['Produto']}** exige o menor aporte: "
                    f"**{formatar_brl(cast(float, _dc_best['_pmt']))}/mês** para atingir "
                    f"{formatar_brl(_dc_meta)} em {_dc_prazo_r} ano(s).\n\n"
                    f"Você economiza **{formatar_brl(_dc_diff)}/mês** vs. "
                    f"**{_dc_worst['Produto']}** ({formatar_brl(cast(float, _dc_worst['_pmt']))}/ mês). "
                    f"Os juros cobrem **{formatar_brl(_dc_juros)}** do seu objetivo.",
                    icon="💡",
                )

    # -----------------------------------------------------------------------
    # Portfólio
    # -----------------------------------------------------------------------
    if "_portfolio" not in st.session_state:
        st.session_state["_portfolio"] = []

    portfolio = st.session_state["_portfolio"]

    st.divider()
    st.subheader(":material/account_balance_wallet:  Portfólio")

    # ---- Formulário de adicionar posição (código inline, keys consistentes) ----
    def _render_form():
        """Formulário de adição/edição de posição no portfólio."""
        _CAT_SELIC = sorted(
            [k for k, v in TITULOS_BATALHA.items() if v.get("tipo") == "selic"]
        )
        _CAT_PRE = sorted(
            [k for k, v in TITULOS_BATALHA.items() if v.get("tipo") == "pre"]
        )
        _CATS_ALL = {
            **CATEGORIAS_TITULOS,
            "Tesouro Selic": _CAT_SELIC or ["Tesouro Selic 2031"],
            "Tesouro Prefixado": _CAT_PRE or ["Tesouro Prefixado 2029"],
            "CDB": ["CDB"],
            "LCI": ["LCI"],
            "LCA": ["LCA"],
        }
        _TIPO_CAT = {
            "IPCA+ Principal": "ipca_mais",
            "IPCA+ com Juros Semestrais": "ipca_mais",
            "Tesouro RendA+": "ipca_mais",
            "Tesouro Educar+": "ipca_mais",
            "Tesouro Selic": "selic",
            "Tesouro Prefixado": "pre",
            "CDB": "cdb",
            "LCI": "lci",
            "LCA": "lca",
        }
        _DEFAULTS_TAXA = {
            "IPCA+ Principal": 7.50,
            "IPCA+ com Juros Semestrais": 7.50,
            "Tesouro RendA+": 7.50,
            "Tesouro Educar+": 7.50,
            "Tesouro Selic": 14.75,
            "Tesouro Prefixado": 14.50,
            "CDB": 14.00,
            "LCI": 11.50,
            "LCA": 11.20,
        }
        _TAXA_LABELS = {
            "ipca_mais": "Taxa Real (% a.a.) — spread IPCA+",
            "selic": "Taxa Selic (% a.a.)",
            "pre": "Taxa Prefixada (% a.a.)",
            "cdb": "Rentabilidade CDB (% a.a.)",
            "lci": "Rentabilidade LCI (% a.a.)",
            "lca": "Rentabilidade LCA (% a.a.)",
        }
        _TAXA_HELP = {
            "ipca_mais": "Spread real sobre o IPCA contratado na compra. Ex.: 7,50 → IPCA + 7,50% a.a.",
            "selic": "Taxa Selic equivalente anual esperada. Ex.: 14,75 para Selic atual.",
            "pre": "Taxa nominal prefixada contratada na compra. Ex.: 13,50% a.a.",
            "cdb": "Taxa nominal anual do CDB (pré-fixado) ou equivalente CDI. Ex.: 12,50.",
            "lci": "Taxa nominal anual da LCI — isenta de IR para pessoa física. Ex.: 11,00.",
            "lca": "Taxa nominal anual da LCA — isenta de IR para pessoa física. Ex.: 10,80.",
        }

        # Detecta mudança de categoria e redefine a taxa padrão automaticamente
        _curr_cat = st.session_state.get("port_cat")
        _prev_cat = st.session_state.get("_port_cat_prev")
        if _curr_cat is not None and _curr_cat != _prev_cat:
            st.session_state["port_taxa"] = _DEFAULTS_TAXA.get(_curr_cat, 5.50)
        st.session_state["_port_cat_prev"] = _curr_cat

        # Para Tesouro Selic: auto-preenche a taxa com a meta COPOM vigente na data de compra
        if _curr_cat == "Tesouro Selic":
            _selic_date = st.session_state.get("port_data")
            _prev_selic_date = st.session_state.get("_port_selic_date_prev")
            if _selic_date is not None and _selic_date != _prev_selic_date:
                st.session_state["port_taxa"] = buscar_selic_na_data(_selic_date)
            st.session_state["_port_selic_date_prev"] = _selic_date

        # Garante que port_cat é sempre uma categoria válida (evita KeyError se None ou inválido)
        if st.session_state.get("port_cat") not in _CATS_ALL:
            st.session_state["port_cat"] = list(_CATS_ALL.keys())[0]

        _fc = st.session_state["port_cat"]
        _titulos_fc = _CATS_ALL.get(_fc, [])
        if not _titulos_fc:
            _fc = next(
                (k for k, v in _CATS_ALL.items() if v), list(_CATS_ALL.keys())[0]
            )
            st.session_state["port_cat"] = _fc
            _titulos_fc = _CATS_ALL.get(_fc, [])
        if st.session_state.get("port_titulo") not in _titulos_fc:
            st.session_state["port_titulo"] = _titulos_fc[0] if _titulos_fc else None

        _fc1, _fc2 = st.columns([1, 2])
        with _fc1:
            _pcat = st.selectbox("Categoria", list(_CATS_ALL.keys()), key="port_cat")
        with _fc2:
            _ptit = st.selectbox("Título", _CATS_ALL[_pcat], key="port_titulo")

        _tipo = _TIPO_CAT.get(_pcat, "ipca_mais")
        _is_simples = _tipo != "ipca_mais"
        _taxa_lbl = _TAXA_LABELS.get(_tipo, "Taxa (% a.a.)")
        _taxa_help = _TAXA_HELP.get(_tipo, "")

        _fc3, _fc4, _fc5 = st.columns([1.6, 1.2, 1.2])
        with _fc3:
            _pval = st.number_input(
                "Valor Investido (R$)",
                min_value=30.0,
                max_value=1_000_000.0,
                value=10_000.0,
                step=500.0,
                format="%.2f",
                key="port_valor",
            )
        with _fc4:
            _ptax = st.number_input(
                _taxa_lbl,
                min_value=0.5,
                max_value=30.0,
                step=0.05,
                format="%.2f",
                key="port_taxa",
                help=_taxa_help,
            )
        with _fc5:
            _pdat = st.date_input(
                "Data de Compra",
                value=date.today() - timedelta(days=365),
                max_value=date.today() - timedelta(days=1),
                format="DD/MM/YYYY",
                key="port_data",
            )

        if _tipo == "selic":
            st.caption(
                f"✅ Taxa Selic efetiva em {_pdat.strftime('%d/%m/%Y')} preenchida automaticamente via BCB — editável se necessário."
            )

        if _tipo in ("cdb", "lci", "lca"):
            _pvenc_date = st.date_input(
                "Data de Vencimento",
                value=date.today() + timedelta(days=365 * 2),
                min_value=date.today() + timedelta(days=31),
                format="DD/MM/YYYY",
                key="port_vencimento",
            )
        elif _is_simples:
            _pvenc_date = TITULOS_BATALHA.get(_ptit, {}).get(
                "vencimento", date(2031, 3, 1)
            )

        if st.button("Adicionar ao portfólio", type="primary", key="port_btn"):
            if _is_simples:
                c = _calcular_simples(
                    _ptit,
                    _tipo,
                    _pval,
                    _ptax,
                    _pdat.isoformat(),
                    _pvenc_date.isoformat(),
                )
            else:
                c = _calcular(_ptit, _pval, _ptax, _pdat.isoformat())
            if c is None:
                st.error("Data de compra deve ser anterior ao vencimento do título.")
            else:
                chave = (_ptit, _pval, _ptax, _pdat.isoformat())
                _titulo_ja_existe = any(
                    p["titulo"] == _ptit for p in st.session_state["_portfolio"]
                )
                _entrada_duplicada = any(
                    (p["titulo"], p["valor"], p["taxa"], p["data_compra"]) == chave
                    for p in st.session_state["_portfolio"]
                )
                if _entrada_duplicada:
                    st.info(
                        "Entrada idêntica já registrada. "
                        "Para registrar um novo aporte no mesmo título, "
                        "altere a data de compra ou o valor investido."
                    )
                else:
                    st.session_state["_portfolio"].append(
                        dict(
                            titulo=_ptit,
                            valor=_pval,
                            taxa=_ptax,
                            data_compra=_pdat.isoformat(),
                            mam_cache=c["res"]["mam"],
                            carrego_cache=c["vf"],
                            vencimento=c["dv"].isoformat(),
                            anos=c["anos_res"],
                            tipo_asset=_tipo,
                        )
                    )
                    st.session_state["_analysis_pos_idx"] = (
                        len(st.session_state["_portfolio"]) - 1
                    )
                    if _titulo_ja_existe:
                        st.toast(
                            f"Novo aporte em {_ptit.replace('Tesouro ', '')} registrado.",
                            icon=":material/add_circle:",
                        )
                    st.rerun()

    # ---- Estado vazio ----
    if not portfolio:
        st.info(
            "**Bem-vindo!** Ainda não há posições no portfólio. "
            "Adicione sua primeira posição abaixo ou carregue um exemplo.",
            icon="👋",
        )
        if st.button(
            "Carregar Exemplo: Tesouro IPCA+ 2032 comprado em 20/05/2026",
            type="secondary",
        ):
            c_ex = _calcular("Tesouro IPCA+ 2032", 15_000.0, 7.50, "2026-05-20")
            if c_ex:
                st.session_state["_portfolio"] = [
                    dict(
                        titulo="Tesouro IPCA+ 2032",
                        valor=15_000.0,
                        taxa=7.50,
                        data_compra="2026-05-20",
                        tipo_asset="ipca_mais",
                        mam_cache=c_ex["res"]["mam"],
                        carrego_cache=c_ex["vf"],
                        vencimento=c_ex["dv"].isoformat(),
                        anos=c_ex["anos_res"],
                    )
                ]
                st.session_state["_analysis_pos_idx"] = 0
                st.rerun()

        st.markdown("---")
        st.markdown("##### Nova posição")
        _render_form()

    # ---- Com posições ----
    else:
        # Atualiza caches com dados ao vivo para garantir consistência com a análise detalhada
        _calcs_port = []
        for p in st.session_state["_portfolio"]:
            _ta = p.get("tipo_asset", "ipca_mais")
            if _ta == "ipca_mais":
                c = _calcular(p["titulo"], p["valor"], p["taxa"], p["data_compra"])
            else:
                c = _calcular_simples(
                    p["titulo"],
                    _ta,
                    p["valor"],
                    p["taxa"],
                    p["data_compra"],
                    p["vencimento"],
                )
            if c is not None:
                p["mam_cache"] = c["res"]["mam"]
                p["carrego_cache"] = c["vf"]
                p["anos"] = c["anos_res"]
            _calcs_port.append(c)

        # Métricas consolidadas
        total_cap = sum(p["valor"] for p in portfolio)
        total_mam = sum(p["mam_cache"] for p in portfolio)
        total_carrego = sum(p["carrego_cache"] for p in portfolio)
        var_total = (total_mam - total_cap) / total_cap * 100

        _score_cap = [
            (c["score"], portfolio[i]["valor"])
            for i, c in enumerate(_calcs_port)
            if c is not None
        ]
        _tot_sc = sum(v for _, v in _score_cap)
        score_medio = (
            sum(s * v for s, v in _score_cap) / _tot_sc if _tot_sc > 0 else 0.0
        )
        score_label = (
            "🟢 Sereno"
            if score_medio >= 70
            else "🟡 Atenção"
            if score_medio >= 40
            else "🔴 Risco"
        )

        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
        with _mc1:
            _pos_label = (
                "1 posição" if len(portfolio) == 1 else f"{len(portfolio)} posições"
            )
            st.metric("Capital Investido", formatar_brl(total_cap), _pos_label)
        with _mc2:
            st.metric(
                "MaM Consolidado",
                formatar_brl(total_mam),
                f"{var_total:+.1f}% vs capital",
                delta_color="normal",
                help=(
                    "**Marcação a Mercado (MaM):** valor que você receberia se vendesse "
                    "todas as posições hoje, calculado com base nas taxas atuais do mercado. "
                    "Pode estar abaixo do capital investido quando as taxas sobem — "
                    "mas isso não afeta o que você recebe se aguardar o vencimento."
                ),
            )
        with _mc3:
            st.metric(
                "No Vencimento",
                formatar_brl(total_carrego),
                f"+{(total_carrego / total_cap - 1) * 100:.1f}% vs capital",
                help=(
                    "**Carrego consolidado:** soma do valor que cada posição pagará "
                    "se mantida até o vencimento, calculado pela taxa contratada na compra. "
                    "Este é o valor garantido — independente das oscilações de mercado."
                ),
            )
        with _mc4:
            st.metric(
                "Saúde da Carteira",
                f"{score_medio:.0f}/100",
                score_label,
                delta_color="off",
                help=(
                    "**Índice de Saúde (0–100):** mede o quanto sua carteira está bem "
                    "posicionada para atravessar a volatilidade sem precisar vender.\n\n"
                    "- **⏳ Prazo (até 60 pts):** quanto mais tempo até o vencimento, "
                    "mais fácil aguardar.\n"
                    "- **📊 Posição (até 40 pts):** quanto mais próximo do capital investido "
                    "estiver o MaM, menor o desconforto.\n\n"
                    "**70–100 🟢 Saudável · 40–69 🟡 Atenção · 0–39 🔴 Risco**"
                ),
            )

        # Gráficos de alocação — visíveis com 2+ posições
        if len(portfolio) >= 2:
            _TIPO_INFO = {
                "ipca_mais": ("IPCA+", "#a5d6a7"),
                "selic": ("Pós-Fixado", "#4fc3f7"),
                "pre": ("Pré-Fixado", "#ef9a9a"),
                "cdb": ("CDB", "#ffcc80"),
                "lci": ("LCI", "#ce93d8"),
                "lca": ("LCA", "#80cbc4"),
            }
            _tipo_agg: dict = {}
            _prazo_agg: dict = {}
            for p in portfolio:
                _ta = p.get("tipo_asset", "ipca_mais")
                _lbl, _cor = _TIPO_INFO.get(_ta, (_ta, "#718096"))
                if _lbl not in _tipo_agg:
                    _tipo_agg[_lbl] = [0.0, _cor]
                _tipo_agg[_lbl][0] += p["valor"]
                _ar = p.get("anos", 1)
                _pk = (
                    "Curto (≤ 2a)"
                    if _ar <= 2
                    else "Médio (3–5a)"
                    if _ar <= 5
                    else "Longo (> 5a)"
                )
                _prazo_agg[_pk] = _prazo_agg.get(_pk, 0.0) + p["valor"]

            _PRAZO_COR = {
                "Curto (≤ 2a)": "#4fc3f7",
                "Médio (3–5a)": "#a5d6a7",
                "Longo (> 5a)": "#ef9a9a",
            }
            _dl = dict(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e0e0",
                margin=dict(t=36, b=0, l=0, r=0),
                height=210,
                legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.08),
            )
            _da1, _da2 = st.columns(2)
            with _da1:
                _fig_t = go.Figure(
                    go.Pie(
                        labels=[k for k in _tipo_agg],
                        values=[v[0] for v in _tipo_agg.values()],
                        hole=0.55,
                        marker=dict(
                            colors=[v[1] for v in _tipo_agg.values()],
                            line=dict(color="#0e1117", width=2),
                        ),
                        textinfo="percent",
                        hovertemplate="%{label}: R$ %{value:,.2f} (%{percent})<extra></extra>",
                    )
                )
                _fig_t.update_layout(
                    **_dl,
                    title=dict(
                        text="Alocação por Tipo",
                        font=dict(size=12, color="#e0e0e0"),
                        x=0.5,
                        xanchor="center",
                    ),
                )
                st.plotly_chart(_fig_t, use_container_width=True)
            with _da2:
                _prazo_order = [
                    k
                    for k in ("Curto (≤ 2a)", "Médio (3–5a)", "Longo (> 5a)")
                    if k in _prazo_agg
                ]
                _fig_p = go.Figure(
                    go.Pie(
                        labels=_prazo_order,
                        values=[_prazo_agg[k] for k in _prazo_order],
                        hole=0.55,
                        marker=dict(
                            colors=[_PRAZO_COR[k] for k in _prazo_order],
                            line=dict(color="#0e1117", width=2),
                        ),
                        textinfo="percent",
                        hovertemplate="%{label}: R$ %{value:,.2f} (%{percent})<extra></extra>",
                    )
                )
                _fig_p.update_layout(
                    **_dl,
                    title=dict(
                        text="Alocação por Prazo",
                        font=dict(size=12, color="#e0e0e0"),
                        x=0.5,
                        xanchor="center",
                    ),
                )
                st.plotly_chart(_fig_p, use_container_width=True)

        # ---- Recomendação de Diversificação ----------------------------------------
        if len(portfolio) >= 1:
            _GRUPO = {
                "ipca_mais": "ipca_mais",
                "selic": "selic",
                "pre": "pre",
                "cdb": "credito",
                "lci": "credito",
                "lca": "credito",
            }
            _totais_grupo: dict = {}
            for _p in portfolio:
                _g = _GRUPO.get(_p.get("tipo_asset", "ipca_mais"), "ipca_mais")
                _totais_grupo[_g] = _totais_grupo.get(_g, 0.0) + _p["valor"]

            _tipo_conc = next(
                (_g for _g, _v in _totais_grupo.items() if _v / total_cap > 0.70),
                None,
            )

            if _tipo_conc:
                _pct_conc = _totais_grupo[_tipo_conc] / total_cap

                # Prazo médio ponderado apenas das posições concentradas
                _pos_conc = [
                    _p
                    for _p in portfolio
                    if _GRUPO.get(_p.get("tipo_asset", "ipca_mais")) == _tipo_conc
                ]
                _total_conc = sum(_p["valor"] for _p in _pos_conc)
                _prazo_conc = sum(
                    _p.get("anos", 3) * _p["valor"] for _p in _pos_conc
                ) / max(_total_conc, 1)

                # Prazo médio do portfólio inteiro (referência para escolher o título recomendado)
                _prazo_med = (
                    sum(_p.get("anos", 3) * _p["valor"] for _p in portfolio) / total_cap
                )

                # Nível de risco real da concentração:
                #   "seguro"   — Selic/crédito: sem risco MaM; a concentração é oportunidade perdida, não perigo
                #   "moderado" — IPCA+/Pré com prazo ≤ 5 anos: risco MaM existe mas é administrável
                #   "exposto"  — IPCA+/Pré com prazo > 5 anos: duration alta, choque de taxa = perda relevante
                if _tipo_conc in ("selic", "credito"):
                    _nivel = "seguro"
                elif _prazo_conc <= 5:
                    _nivel = "moderado"
                else:
                    _nivel = "exposto"

                _NOME_CONC = {
                    "ipca_mais": "IPCA+",
                    "selic": "Pós-Fixado (Selic)",
                    "pre": "Pré-Fixado",
                    "credito": "Crédito Privado (CDB/LCI/LCA)",
                }
                _GAP = {
                    "ipca_mais": "selic",
                    "selic": "ipca_mais",
                    "pre": "ipca_mais",
                    "credito": "selic",
                }
                _ESTILO = {
                    "seguro": "badge-seguranca",
                    "moderado": "alerta-mercado",
                    "exposto": "alerta-mercado",
                }
                _CABECALHO = {
                    "seguro": (
                        f"💡 <strong>{_pct_conc * 100:.0f}% da carteira em {_NOME_CONC[_tipo_conc]} "
                        f"— posição segura, sem risco de MaM.</strong>"
                    ),
                    "moderado": (
                        f"⚠️ <strong>{_pct_conc * 100:.0f}% da carteira em {_NOME_CONC[_tipo_conc]} "
                        f"com prazo médio de {_prazo_conc:.1f} ano(s) — risco de MaM moderado.</strong>"
                    ),
                    "exposto": (
                        f"⚠️ <strong>{_pct_conc * 100:.0f}% da carteira em {_NOME_CONC[_tipo_conc]} "
                        f"de longo prazo ({_prazo_conc:.1f} anos médios) — risco de MaM elevado.</strong>"
                    ),
                }
                _CORPO = {
                    "seguro": (
                        "Você não corre risco de preço — pode resgatar a qualquer momento sem surpresas. "
                        "Se quiser maior rentabilidade real com um pouco mais de risco controlado, "
                        "considere diversificar parte da carteira para:"
                    ),
                    "moderado": (
                        "Com essa concentração, uma alta de taxas reduziria o valor de resgate antecipado. "
                        "Para equilibrar risco e liquidez, considere adicionar:"
                    ),
                    "exposto": (
                        f"Com {_prazo_conc:.1f} anos de duration médio, um choque de 1 p.p. nas taxas pode "
                        "reduzir significativamente o valor de resgate. Para proteger a carteira, considere:"
                    ),
                }

                _selic_ref = buscar_selic_meta_bcb()
                _ipca_ref = st.session_state.get("bat_ipca", 5.0)
                _tipo_rec = _GAP[_tipo_conc]
                _cat_rec = montar_catalogo_batalha(df_titulos, _selic_ref)
                _cands = [t for t in _cat_rec if t["tipo"] == _tipo_rec][:6]

                _melhor, _melhor_score = None, -999.0
                for _ct in _cands:
                    _an = analise_batalha(
                        nome=_ct["nome"],
                        tipo=_ct["tipo"],
                        taxa=_ct["taxa"],
                        anos_total=_ct["anos_total"],
                        anos_saida=float(max(1, round(_prazo_med))),
                        ipca=_ipca_ref,
                        choque=1.0,
                        com_ir=True,
                        selic=_selic_ref,
                    )
                    _sc = _an["ret_neu"] / max(_an["risco_std"], 0.01)
                    if _sc > _melhor_score:
                        _melhor_score, _melhor = _sc, (_ct, _an)

                if _melhor:
                    _ct, _an = _melhor
                    _nome_rec = _ct["nome"].replace("Tesouro ", "")
                    if _tipo_rec == "selic":
                        _taxa_rec = f"~{_selic_ref:.2f}% a.a."
                    elif _tipo_rec == "ipca_mais":
                        _taxa_rec = f"IPCA+ {_ct['taxa']:.2f}% a.a."
                    else:
                        _taxa_rec = f"{_ct['taxa']:.2f}% a.a."

                    st.markdown(
                        f'<div class="{_ESTILO[_nivel]}" style="margin-top:0.8rem;">'
                        f"{_CABECALHO[_nivel]}<br><br>"
                        f"{_CORPO[_nivel]}<br><br>"
                        f"→ <strong>{_nome_rec}</strong> &nbsp;·&nbsp; {_taxa_rec} &nbsp;·&nbsp; "
                        f"Retorno estimado: <strong>{_an['ret_neu']:.1f}% a.a.</strong> (neutro, com IR) &nbsp;·&nbsp; "
                        f"Risco MaM: <strong>{_an['risco_label']}</strong>"
                        f'<br><span style="font-size:0.8rem; color:#718096; margin-top:0.4rem; display:block;">'
                        f"Análise baseada no prazo médio da carteira ({_prazo_med:.1f} ano(s)). "
                        f"Para comparar cenários completos, acesse <em>Qual Ativo Escolher?</em>.</span>"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

        # Tabela
        rows_p = []
        for i, p in enumerate(portfolio):
            var = (p["mam_cache"] - p["valor"]) / p["valor"] * 100
            score_p = _calcs_port[i]["score"] if _calcs_port[i] is not None else 0.0
            rows_p.append(
                {
                    "#": i + 1,
                    "Título": p["titulo"].replace("Tesouro ", ""),
                    "Capital": formatar_brl(p["valor"]),
                    "Taxa": f"{p['taxa']:.2f}%",
                    "MaM Hoje": formatar_brl(p["mam_cache"]),
                    "Var. %": f"{var:+.1f}%",
                    "Saúde": score_p,
                    "Vencimento": p["vencimento"],
                }
            )
        st.dataframe(
            pd.DataFrame(rows_p),
            hide_index=True,
            use_container_width=True,
            column_config={
                "Saúde": st.column_config.ProgressColumn(
                    "Saúde",
                    help="Índice 0–100: prazo restante (até 60 pts) + posição MaM (até 40 pts). 🟢 ≥70 · 🟡 40–69 · 🔴 <40",
                    min_value=0,
                    max_value=100,
                    format="%.0f",
                ),
            },
        )

        # Controles de remoção
        _nomes_r = [
            f"#{i + 1} — {p['titulo'].replace('Tesouro ', '')} | {formatar_brl(p['valor'])} | compra {p['data_compra']}"
            for i, p in enumerate(portfolio)
        ]
        _rc1, _rc2, _rc3 = st.columns([4, 1, 1])
        with _rc1:
            _rem_i = st.selectbox(
                "Remover",
                range(len(portfolio)),
                format_func=lambda i: _nomes_r[i],
                key="port_rem_idx",
                label_visibility="collapsed",
            )
        with _rc2:
            if st.button("🗑️  Remover", key="port_rem_btn"):
                st.session_state["_portfolio"].pop(_rem_i)
                st.session_state["_analysis_pos_idx"] = 0
                st.rerun()
        with _rc3:
            if st.button("🗑️  Limpar tudo", key="port_clear"):
                st.session_state["_portfolio"] = []
                st.session_state["_analysis_pos_idx"] = 0
                st.rerun()

        with st.expander("➕  Adicionar nova posição", expanded=False):
            st.caption(
                "Preencha os dados e clique em Adicionar — sem precisar sair desta seção."
            )
            _render_form()

    # -----------------------------------------------------------------------
    # Análise Detalhada (só renderiza se há posições)
    # -----------------------------------------------------------------------
    if not portfolio:
        st.divider()
        _render_calc(10_000.0)
        salvar(
            {
                "dash_descontar_custodia": st.session_state.get(
                    "dash_descontar_custodia", False
                ),
                "dash_choque_stress": st.session_state.get("dash_choque_stress", 2.0),
                "_portfolio": [],
                "_analysis_pos_idx": 0,
                "port_cat": st.session_state.get("port_cat"),
                "port_titulo": st.session_state.get("port_titulo"),
                "port_valor": st.session_state.get("port_valor", 10_000.0),
                "port_taxa": st.session_state.get("port_taxa", 5.50),
                "port_data": st.session_state.get("port_data"),
                "port_vencimento": st.session_state.get("port_vencimento"),
                # Calculadora de Aportes Mensais
                "dash_calc_ipca": st.session_state.get("dash_calc_ipca", 5.0),
                "dash_calc_selic": st.session_state.get("dash_calc_selic", 14.75),
                "dash_calc_pre": st.session_state.get("dash_calc_pre", 14.5),
                "dash_calc_ipca_plus": st.session_state.get("dash_calc_ipca_plus", 7.0),
                "dash_calc_cdb": st.session_state.get("dash_calc_cdb", 14.0),
                "dash_calc_lci": st.session_state.get("dash_calc_lci", 11.5),
                "dash_calc_lca": st.session_state.get("dash_calc_lca", 11.2),
                "dash_calc_aporte": st.session_state.get("dash_calc_aporte", 500.0),
                "dash_calc_meta": st.session_state.get("dash_calc_meta", 200_000.0),
                "dash_calc_prazo_proj": st.session_state.get("dash_calc_prazo_proj", 5),
                "dash_calc_prazo_rev": st.session_state.get("dash_calc_prazo_rev", 5),
                "dash_calc_capital": st.session_state.get(
                    "dash_calc_capital", 10_000.0
                ),
                "dash_calc_cap_rev": st.session_state.get(
                    "dash_calc_cap_rev", 10_000.0
                ),
            }
        )
        return

    st.divider()
    st.subheader(":material/analytics:  Análise Detalhada")

    if "_analysis_pos_idx" not in st.session_state:
        st.session_state["_analysis_pos_idx"] = 0

    _nomes_a = [
        f"{p['titulo'].replace('Tesouro ', '')} — {formatar_brl(p['valor'])} · {p['taxa']:.2f}% a.a."
        for p in portfolio
    ]

    sel_idx = st.selectbox(
        "Posição em análise",
        range(len(portfolio)),
        format_func=lambda i: _nomes_a[i],
        key="_analysis_pos_idx",
    )

    pos = portfolio[sel_idx]
    _tipo_sel = pos.get("tipo_asset", "ipca_mais")
    if _tipo_sel == "ipca_mais":
        calc = _calcular(pos["titulo"], pos["valor"], pos["taxa"], pos["data_compra"])
    else:
        calc = _calcular_simples(
            pos["titulo"],
            _tipo_sel,
            pos["valor"],
            pos["taxa"],
            pos["data_compra"],
            pos["vencimento"],
        )

    if calc is None:
        st.error(
            "⛔ Não foi possível calcular esta posição. Verifique se a data de compra é válida."
        )
        return

    titulo_sel = pos["titulo"]
    valor_investido = pos["valor"]
    taxa_contratada_pct = pos["taxa"]
    data_compra = calc["dc"]
    data_vencimento = calc["dv"]
    taxa_mercado_pct = calc["taxa_mkt_pct"]
    taxa_venda_pct = calc["taxa_vda_pct"]
    taxa_contratada = calc["tc"]
    taxa_mercado = calc["tm"]
    tem_cupom = calc["cupom"]
    pu_compra = calc["pu_c"]
    cpns_hoje = calc["cpns_h"]
    resultado = calc["res"]
    anos_restantes = calc["anos_res"]
    valor_vencimento = calc["vf"]
    prazo_score = calc["prazo_score"]
    posicao_score = calc["posicao_score"]
    score = calc["score"]

    st.session_state["_dash_pos"] = {
        "titulo": titulo_sel,
        "mam": resultado["mam"],
        "carrego": valor_vencimento,
        "data_venc": data_vencimento,
        "score": score,
    }

    # -----------------------------------------------------------------------
    # Abas
    # -----------------------------------------------------------------------
    tab_pos, tab_sim, tab_port, tab_util = st.tabs(
        [
            "Posição",
            "Simulações",
            "Portfólio",
            "Utilitários",
        ]
    )

    # ============================= ABA 1: POSIÇÃO ============================
    with tab_pos:
        # IOF ativo — aviso prioritário
        dias_investido = (date.today() - data_compra).days
        if 0 < dias_investido < 30:
            aliq_iof = aliquota_iof_renda_fixa(dias_investido)
            lucro_bruto = max(0.0, resultado["mam"] - valor_investido)
            iof_estimado = lucro_bruto * aliq_iof
            st.warning(
                f"**IOF Regressivo Ativo** — {dias_investido} dia(s) de aplicação. "
                f"Alíquota: **{aliq_iof * 100:.0f}%** · IOF estimado: **{formatar_brl(iof_estimado)}**. "
                f"Zera daqui a **{30 - dias_investido} dia(s)**.",
                icon="🔴",
            )

        if calc.get("is_simples"):
            # ---- Vista simplificada para Selic, Pré-Fixado, CDB, LCI, LCA ----
            _tipo_labels_pos = {
                "selic": "Tesouro Selic — Pós-Fixado",
                "pre": "Tesouro Pré-Fixado",
                "cdb": "CDB — Crédito Privado",
                "lci": "LCI — Crédito Privado (isento IR)",
                "lca": "LCA — Crédito Privado (isento IR)",
            }
            st.info(
                f"**{_tipo_labels_pos.get(_tipo_sel, 'Renda Fixa')}** — "
                "este ativo não possui marcação a mercado diária. "
                "O valor exibido é o rendimento acumulado pela taxa contratada.",
                icon="ℹ️",
            )
            _sc1, _sc2, _sc3 = st.columns(3)
            with _sc1:
                st.metric(
                    "Capital Investido",
                    formatar_brl(valor_investido),
                    f"Comprado em {data_compra.strftime('%d/%m/%Y')}",
                )
            with _sc2:
                _acum_pct = (resultado["mam"] / valor_investido - 1) * 100
                st.metric(
                    "Valor Atual (accrual)",
                    formatar_brl(resultado["mam"]),
                    f"+{_acum_pct:.2f}% acumulado",
                    delta_color="normal",
                )
            with _sc3:
                _venc_pct = (valor_vencimento / valor_investido - 1) * 100
                st.metric(
                    "No Vencimento",
                    formatar_brl(valor_vencimento),
                    f"+{_venc_pct:.1f}% acumulado nominal",
                    delta_color="normal",
                )

            if _tipo_sel in ("lci", "lca"):
                st.success(
                    "✅ **Isenção de IR** — LCI e LCA são isentos de Imposto de Renda "
                    "para pessoa física em qualquer prazo."
                )

            if _tipo_sel in ("cdb", "lci", "lca"):
                st.info(
                    "🛡️ **Garantia FGC:** CDB, LCI e LCA são cobertos pelo Fundo Garantidor "
                    "de Créditos até **R$ 250 mil por CPF por instituição**. Valores acima desse "
                    "limite têm risco de crédito do emissor bancário.\n\n"
                    "Títulos do **Tesouro Direto** têm risco soberano (governo federal) — "
                    "sem limite de cobertura e considerado o menor risco de crédito do Brasil.",
                    icon="ℹ️",
                )

            _pos_max_simples = 25 if _tipo_sel == "pre" else 40
            col_sg, col_sc = st.columns([2.5, 1])
            with col_sg:
                st.markdown("---")
                st.markdown("#### Projeção de Crescimento")
                # Projeção a partir do valor acumulado hoje (mam) até o vencimento.
                # Usar valor_investido como base deixaria o gráfico inconsistente com
                # a métrica "No Vencimento" para posições mantidas há algum tempo.
                _mam_sim = resultado["mam"]
                _d, _meses_x, _meses_y = date.today(), [], []
                while _d < data_vencimento:
                    _dias = (_d - date.today()).days
                    _meses_x.append(_d.strftime("%b/%Y"))
                    _meses_y.append(_mam_sim * (1 + taxa_contratada) ** (_dias / 365))
                    _nm = _d.month % 12 + 1
                    _ny = _d.year + (_d.month // 12)
                    _d = date(_ny, _nm, min(_d.day, _cal.monthrange(_ny, _nm)[1]))
                # Garante que o vencimento está incluído
                _dias_venc = (data_vencimento - date.today()).days
                _meses_x.append(data_vencimento.strftime("%b/%Y"))
                _meses_y.append(_mam_sim * (1 + taxa_contratada) ** (_dias_venc / 365))
                _cap_line = [valor_investido] * len(_meses_x)
                _y_pad = (max(_meses_y) - valor_investido) * 0.15
                fig_proj = go.Figure()
                fig_proj.add_trace(
                    go.Scatter(
                        x=_meses_x,
                        y=_cap_line,
                        mode="lines",
                        name="Capital investido",
                        line=dict(color="#90caf9", width=1.5, dash="dash"),
                        hovertemplate="Capital: R$ %{y:,.2f}<extra></extra>",
                    )
                )
                fig_proj.add_trace(
                    go.Scatter(
                        x=_meses_x,
                        y=_meses_y,
                        mode="lines",
                        name="Valor projetado",
                        line=dict(color="#a5d6a7", width=2.5),
                        fill="tonexty",
                        fillcolor="rgba(165,214,167,0.12)",
                        hovertemplate="%{x}<br><b>R$ %{y:,.2f}</b><extra></extra>",
                    )
                )
                fig_proj.update_layout(
                    margin=dict(t=10, b=30, l=10, r=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0",
                    yaxis=dict(
                        tickprefix="R$ ",
                        separatethousands=True,
                        range=[valor_investido - _y_pad, max(_meses_y) + _y_pad],
                        gridcolor="rgba(255,255,255,0.06)",
                    ),
                    xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickangle=-30),
                    legend=dict(orientation="h", y=-0.25, x=0),
                    height=290,
                )
                st.plotly_chart(fig_proj, use_container_width=True)
            with col_sc:
                st.metric(
                    "Saúde da Posição",
                    "",
                    help=(
                        f"**⏳ Prazo ({prazo_score:.0f}/60 pts):** quanto mais tempo restante, "
                        "mais fácil esperar.\n\n"
                        f"**📊 Posição ({posicao_score:.0f}/{_pos_max_simples} pts)**\n\n"
                        "**70–100 🟢 Saudável · 40–69 🟡 Atenção · 0–39 🔴 Risco**"
                    ),
                )
                st.plotly_chart(grafico_score(score), use_container_width=True)

            st.info(
                f"📅 **Vencimento:** {data_vencimento.strftime('%d/%m/%Y')}  ·  "
                f"**Anos restantes:** {anos_restantes}  ·  "
                f"**Taxa:** {taxa_contratada_pct:.2f}% a.a.",
            )

        else:
            # ---- Vista completa para Tesouro IPCA+/RendA+/Educar+ ----
            # KPI cards
            col1, col2, col3 = st.columns(3)
            variacao = resultado["variacao_dia"]

            with col1:
                st.metric(
                    "Variação do Dia (est.)",
                    f"{variacao:+.2f}%",
                    f"{variacao:.2f}%",
                    delta_color="normal",
                    help=(
                        "**Variação estimada** do PU de mercado hoje vs. ontem.\n\n"
                        "O Tesouro Direto não publica a taxa de ontem em tempo real — "
                        "essa oscilação é gerada por um modelo estocástico calibrado à "
                        "duration do título (seed determinístico = mesmo valor no mesmo dia). "
                        "Serve para ilustrar a volatilidade diária típica do MaM, "
                        "**não é dado de mercado real**."
                    ),
                )

            with col2:
                delta_vs = resultado["mam"] - valor_investido
                delta_str = (
                    f"-{formatar_brl(abs(delta_vs))} vs. capital"
                    if delta_vs < 0
                    else f"+{formatar_brl(delta_vs)} vs. capital"
                )
                st.metric(
                    "Resgate Antecipado Hoje",
                    formatar_brl(resultado["mam"]),
                    delta_str,
                    delta_color="normal",
                    help="Valor que você receberia se vender hoje — sujeito à MaM",
                )
                if taxa_venda_pct and taxa_venda_pct > taxa_mercado_pct:
                    spread_bps = (taxa_venda_pct - taxa_mercado_pct) * 100
                    pu_venda_est = pu_ntnb(
                        vna,
                        taxa_venda_pct / 100,
                        date.today(),
                        data_vencimento,
                        cpns_hoje,
                    )
                    spread_rs = (resultado["pu_hoje"] - pu_venda_est) * resultado[
                        "quantidade"
                    ]
                    st.caption(
                        f"⚠️ Spread bid-ask: {spread_bps:.0f} bps — impacto estimado: "
                        f"{formatar_brl(spread_rs)} a menos no resgate real."
                    )

            with col3:
                ganho_real_pct = (valor_vencimento / valor_investido - 1) * 100
                if "RendA+" in titulo_sel:
                    lbl = "Capital Acumulado (RendA+)"
                elif "Educar+" in titulo_sel:
                    lbl = "Capital Acumulado (Educar+)"
                else:
                    lbl = "Resgate no Vencimento"
                st.metric(
                    lbl,
                    formatar_brl(valor_vencimento),
                    f"+{ganho_real_pct:.1f}% real acumulado",
                    delta_color="normal",
                )

            # ---- Duration Modificada (diferença central bilateral) ----
            st.markdown("---")
            _tm_up = taxa_mercado + 0.01
            _tm_dn = max(0.001, taxa_mercado - 0.01)
            _res_up = metricas_carteira(
                valor_investido=valor_investido,
                pu_na_compra=pu_compra,
                taxa_real_contratada=taxa_contratada,
                taxa_real_mercado=_tm_up,
                vna=vna,
                data_hoje=date.today(),
                data_vencimento=data_vencimento,
                datas_cupom=cpns_hoje,
            )
            _res_dn = metricas_carteira(
                valor_investido=valor_investido,
                pu_na_compra=pu_compra,
                taxa_real_contratada=taxa_contratada,
                taxa_real_mercado=_tm_dn,
                vna=vna,
                data_hoje=date.today(),
                data_vencimento=data_vencimento,
                datas_cupom=cpns_hoje,
            )
            _dur_mod = (
                -((_res_up["mam"] - _res_dn["mam"]) / (2 * resultado["mam"] * 0.01))
                if resultado["mam"] > 0
                else 0.0
            )

            _col_dur, _ = st.columns([1, 2])
            with _col_dur:
                st.metric(
                    "📐 Duration Modificada",
                    f"{_dur_mod:.1f} anos",
                    delta_color="off",
                    help=(
                        "Estima quantos % o preço muda para cada 1 p.p. de variação na taxa. "
                        "Duration de 5 anos → subir 1 p.p. reduz o resgate ~5%.\n\n"
                        "Títulos mais longos têm duration maior — mais sensíveis a choques de taxa. "
                        "Para simular diferentes magnitudes de choque, use a aba **Simulações**."
                    ),
                )

            # Banner comportamental + saúde
            col_b, col_g = st.columns([1.8, 1])
            with col_b:
                if resultado["mam"] < valor_investido:
                    st.markdown(
                        """
        <div class="alerta-mercado">
            ⚠️ <strong>Por que minha carteira aparece "negativa"?</strong><br>
            <small>A Marcação a Mercado reflete o preço que o mercado pagaria <em>agora</em>.
            Quando as taxas sobem, esse preço cai — mas não afeta o que você receberá no vencimento.
            Se você <strong>não vender antes</strong>, receberá exatamente a taxa contratada,
            corrigida pelo IPCA.</small>
        </div>""",
                        unsafe_allow_html=True,
                    )
                else:
                    st.markdown(
                        """
        <div class="badge-seguranca">
            ✅ <strong>Sua posição está acima do capital investido.</strong><br>
            <small>As taxas caíram desde sua compra, valorizando o título. Você pode resgatar
            antecipadamente com ganho — ou manter até o vencimento para receber a taxa integral.</small>
        </div>""",
                        unsafe_allow_html=True,
                    )

            with col_g:
                st.metric(
                    "Saúde da Posição",
                    "",
                    help=(
                        f"**⏳ Prazo ({prazo_score:.0f}/60 pts):** quanto mais tempo restante, "
                        "mais fácil esperar.\n\n"
                        f"**📊 Posição ({posicao_score:.0f}/40 pts):** quanto mais próximo do capital "
                        "investido estiver o MaM, menor o desconforto.\n\n"
                        "**70–100 🟢 Saudável · 40–69 🟡 Atenção · 0–39 🔴 Risco**"
                    ),
                )
                st.plotly_chart(grafico_score(score), use_container_width=True)

            # Gráfico do Paradoxo
            st.markdown("---")
            st.markdown("#### O Gráfico do Paradoxo")
            col_graf, col_leg = st.columns([3, 1])

            with st.spinner("Calculando série temporal..."):
                df_paradoxo = _serie_cached(
                    vna,
                    taxa_contratada,
                    taxa_mercado,
                    data_compra,
                    data_vencimento,
                    resultado["quantidade"],
                    tem_cupom,
                )

            with col_graf:
                st.plotly_chart(
                    grafico_paradoxo(
                        df_paradoxo,
                        data_compra=data_compra,
                        data_vencimento=data_vencimento,
                        datas_cupom=cpns_hoje if tem_cupom else None,
                    ),
                    use_container_width=True,
                )

            with col_leg:
                st.markdown("**O que estou vendo?**")
                padrao_c = (
                    "Oscila em **dente de serra** a cada semestre — reflexo dos cupons."
                    if tem_cupom
                    else "Curva **exponencial lisa** — sem cupons."
                )
                st.markdown(f"""
**🔴 MaM** — preço de mercado dia a dia.
É o que você recebe **se vender hoje**.

---

**🟢 Carrego** — trajetória pela taxa de
**{taxa_contratada_pct:.2f}% a.a.** contratada.
{padrao_c}
É o que você recebe **se aguardar
{data_vencimento.strftime("%d/%m/%Y")}**.

---

As duas linhas **convergem no vencimento.**
                """)

            st.info(
                f"📅 **Vencimento:** {data_vencimento.strftime('%d/%m/%Y')}  ·  "
                f"**Anos restantes:** {anos_restantes}  ·  "
                f"**VNA:** {formatar_brl(vna)}  ·  "
                f"**Taxa mercado:** {taxa_mercado_pct:.2f}% a.a.  ·  "
                f"**Qtd:** {resultado['quantidade']:.4f} títulos",
            )
            st.caption(
                "ℹ️ O VNA (Valor Nominal Atualizado) é corrigido pelo IPCA oficial do mês já fechado, "
                "divulgado pelo IBGE com defasagem de cerca de 15 dias. Por isso, pequenas variações "
                "centesimais entre o PU exibido aqui e o do seu home broker são normais — cada "
                "plataforma pode aplicar o IPCA do mês corrente de forma diferente (projeção vs. dado oficial)."
            )

    # =========================== ABA 2: SIMULAÇÕES ===========================
    with tab_sim:
        # Stress Test — apenas para IPCA+ (usa pricing NTN-B)
        if not calc.get("is_simples"):
            st.markdown("#### Choque de Taxa — Adverso e Favorável")
            st.caption("O carrego permanece inalterado em ambos os cenários.")

            choque_stress = st.slider(
                "Magnitude do Choque (p.p.)",
                min_value=0.0,
                max_value=5.0,
                value=2.0,
                step=0.25,
                format="%.2f p.p.",
                key="dash_choque_stress",
            )

            taxa_adv = taxa_mercado + choque_stress / 100
            res_adv = metricas_carteira(
                valor_investido=valor_investido,
                pu_na_compra=pu_compra,
                taxa_real_contratada=taxa_contratada,
                taxa_real_mercado=taxa_adv,
                vna=vna,
                data_hoje=date.today(),
                data_vencimento=data_vencimento,
                datas_cupom=cpns_hoje,
            )
            taxa_fav = max(0.001, taxa_mercado - choque_stress / 100)
            res_fav = metricas_carteira(
                valor_investido=valor_investido,
                pu_na_compra=pu_compra,
                taxa_real_contratada=taxa_contratada,
                taxa_real_mercado=taxa_fav,
                vna=vna,
                data_hoje=date.today(),
                data_vencimento=data_vencimento,
                datas_cupom=cpns_hoje,
            )
            tombo_adv = res_adv["mam"] - resultado["mam"]
            tombo_adv_pct = (
                (tombo_adv / resultado["mam"] * 100) if resultado["mam"] > 0 else 0.0
            )
            ganho_fav = res_fav["mam"] - resultado["mam"]
            ganho_fav_pct = (
                (ganho_fav / resultado["mam"] * 100) if resultado["mam"] > 0 else 0.0
            )

            st.markdown("**🔴 Cenário Adverso — Taxa Sobe**")
            ca1, ca2, ca3 = st.columns(3)
            with ca1:
                st.metric(
                    "Taxa de Mercado",
                    f"{taxa_adv * 100:.2f}% a.a.",
                    f"+{choque_stress:.2f} p.p.",
                    delta_color="inverse",
                )
            with ca2:
                st.metric(
                    "Resgate Antecipado",
                    formatar_brl(res_adv["mam"]),
                    formatar_brl(tombo_adv),
                    delta_color="inverse",
                )
            with ca3:
                st.metric("Impacto", f"{tombo_adv_pct:+.1f}%")
                st.caption(
                    f"🛡️ Carrego no vencimento: **{formatar_brl(valor_vencimento)}** — inalterado"
                )

            st.markdown(
                """<div class="alerta-mercado" style="margin-bottom:0.8rem">
🧠 <strong>Este tombo é real — mas temporário.</strong>
Vender agora cristaliza o prejuízo. Aguardar o vencimento o elimina completamente.
</div>""",
                unsafe_allow_html=True,
            )

            st.markdown("**🟢 Cenário Favorável — Taxa Cai**")
            cf1, cf2, cf3 = st.columns(3)
            with cf1:
                st.metric(
                    "Taxa de Mercado",
                    f"{taxa_fav * 100:.2f}% a.a.",
                    f"-{choque_stress:.2f} p.p.",
                    delta_color="normal",
                )
            with cf2:
                st.metric(
                    "Resgate Antecipado",
                    formatar_brl(res_fav["mam"]),
                    f"+{formatar_brl(ganho_fav)}",
                    delta_color="normal",
                )
            with cf3:
                st.metric(
                    "Ganho de Capital",
                    f"{ganho_fav_pct:+.1f}%",
                    "Vender agora captura este ganho",
                    delta_color="normal",
                )

            st.markdown(
                """<div class="badge-seguranca">
💡 <strong>Oportunidade de MaM:</strong> Quando taxas caem, você pode vender com ganho
— ou manter e receber a taxa contratada integral.
</div>""",
                unsafe_allow_html=True,
            )

        st.markdown("---")

        _render_calc(valor_investido)

        st.markdown("---")

        # Estou Pensando em Vender
        st.markdown("#### Estou Pensando em Vender — Qual o Custo Real?")
        cv1, cv2 = st.columns(2)
        with cv1:
            mam_input = st.number_input(
                "Resgate antecipado hoje (R$)",
                min_value=1.0,
                max_value=10_000_000.0,
                value=float(round(resultado["mam"], 2)),
                step=100.0,
                format="%.2f",
                key="venda_mam",
            )
            anos_venda = st.number_input(
                "Você aguardaria quantos anos?",
                min_value=1,
                max_value=anos_restantes,
                value=min(3, anos_restantes),
                step=1,
                key="venda_anos",
            )
        with cv2:
            taxa_reinv = st.number_input(
                "Taxa de reinvestimento (% a.a.)",
                min_value=1.0,
                max_value=25.0,
                value=float(round(taxa_mercado_pct, 2)),
                step=0.1,
                format="%.2f",
                key="venda_reinv",
            )
            _ir_default = _tipo_sel not in ("lci", "lca")
            ir_venda = st.checkbox(
                "Considerar IR na venda", value=_ir_default, key="venda_ir"
            )
            if _tipo_sel in ("lci", "lca"):
                st.caption("LCI/LCA são isentos de IR para pessoa física.")
            if _tipo_sel == "ipca_mais":
                ipca_cen_b = st.number_input(
                    "IPCA estimado — Cenário B (% a.a.)",
                    min_value=0.5,
                    max_value=20.0,
                    value=5.0,
                    step=0.1,
                    format="%.1f",
                    help="IPCA médio anual estimado para o período de aguardo. "
                    "Afeta apenas o valor nominal do Cenário B — o ganho real travado não muda.",
                    key="venda_ipca_b",
                )
            else:
                ipca_cen_b = 0.0

        lucro_v = max(0.0, mam_input - valor_investido)
        if ir_venda:
            dias_tot = (date.today() - data_compra).days
            aliq_ir_v = aliquota_ir_renda_fixa(dias_tot / 365)
            ir_dev = lucro_v * aliq_ir_v
        else:
            ir_dev, aliq_ir_v = 0.0, 0.0

        liq_venda = mam_input - ir_dev
        _lucro_reinv = liq_venda * (1 + taxa_reinv / 100) ** anos_venda - liq_venda
        if ir_venda:
            _aliq_reinv = aliquota_ir_renda_fixa(anos_venda)
            _ir_reinv = max(0.0, _lucro_reinv) * _aliq_reinv
        else:
            _aliq_reinv, _ir_reinv = 0.0, 0.0
        val_reinvest = liq_venda + _lucro_reinv - _ir_reinv

        # Cenário B: carrego bruto, depois desconta IR pelo prazo total desde a compra
        # Para IPCA+ multiplica pelo IPCA inserido pelo usuário; demais ativos já embutem inflação na taxa nominal
        # Base = mam_input (igual a resultado["mam"] por padrão, mas segue ajuste do usuário no widget).
        _ipca_b = (1 + ipca_cen_b / 100) if _tipo_sel == "ipca_mais" else 1.0
        vf_bruto_b = (
            mam_input * (1 + taxa_contratada) ** anos_venda * (_ipca_b**anos_venda)
        )
        if ir_venda:
            dias_b = (date.today() - data_compra).days + int(anos_venda * 365)
            aliq_ir_b = aliquota_ir_renda_fixa(dias_b / 365)
            lucro_b = max(0.0, vf_bruto_b - valor_investido)
            val_aguardar = vf_bruto_b - lucro_b * aliq_ir_b
        else:
            val_aguardar = vf_bruto_b
            aliq_ir_b = 0.0

        diferenca = val_reinvest - val_aguardar

        st.markdown(f"**Comparação: vender agora vs. aguardar {anos_venda} ano(s)**")
        cv_c1, cv_c2, cv_c3 = st.columns(3)
        with cv_c1:
            st.metric(
                "Cenário A — Vender e Reinvestir",
                formatar_brl(val_reinvest),
                f"Líquido: {formatar_brl(liq_venda)} → {taxa_reinv:.1f}% a.a.",
                delta_color="normal" if diferenca >= 0 else "inverse",
            )
        with cv_c2:
            ir_b_str = f" · IR {aliq_ir_b * 100:.0f}%" if ir_venda else " · sem IR"
            _b_taxa_str = (
                f"{taxa_contratada_pct:.2f}% real + IPCA {ipca_cen_b:.1f}% est."
                if _tipo_sel == "ipca_mais"
                else f"{taxa_contratada_pct:.2f}% a.a. nominal"
            )
            st.metric(
                "Cenário B — Aguardar (carrego)",
                formatar_brl(val_aguardar),
                f"{_b_taxa_str}{ir_b_str}",
                delta_color="off",
            )
        with cv_c3:
            st.metric(
                "Diferença A−B",
                formatar_brl(diferenca),
                "Vender compensa" if diferenca > 0 else "Aguardar compensa",
                delta_color="normal" if diferenca > 0 else "inverse",
            )

        if ir_venda:
            st.caption(
                f"IR Cenário A: venda {formatar_brl(ir_dev)} ({aliq_ir_v * 100:.0f}%) "
                f"+ reinvest. {formatar_brl(_ir_reinv)} ({_aliq_reinv * 100:.0f}%) — "
                f"IR Cenário B: {aliq_ir_b * 100:.0f}% sobre lucro total (prazo desde a compra)."
            )

    # =========================== ABA 3: PORTFÓLIO ============================
    with tab_port:
        st.caption(
            "Visão estatística de toda a carteira — independente da posição selecionada acima."
        )

        _tipo_map = {
            "selic": "Pós-Fixado (Selic)",
            "pre": "Pré-Fixado",
            "ipca_mais": "IPCA+/RendA+/Educar+",
            "cdb": "CDB",
            "lci": "LCI",
            "lca": "LCA",
        }
        _cor_tipo = {
            "Pós-Fixado (Selic)": "#4fc3f7",
            "Pré-Fixado": "#ef9a9a",
            "IPCA+/RendA+/Educar+": "#a5d6a7",
            "CDB": "#ce93d8",
            "LCI": "#fff176",
            "LCA": "#ffcc80",
        }

        _port_stats = []
        for i, p in enumerate(_calcs_port):
            if p is None:
                continue
            pos_p = portfolio[i]
            tipo = pos_p.get("tipo_asset", "ipca_mais")
            tipo_label = _tipo_map.get(tipo, "IPCA+/RendA+/Educar+")
            _port_stats.append(
                {
                    "nome": pos_p["titulo"].replace("Tesouro ", ""),
                    "capital": pos_p["valor"],
                    "mam": pos_p["mam_cache"],
                    "carrego": pos_p["carrego_cache"],
                    "taxa": pos_p["taxa"],
                    "anos": pos_p["anos"],
                    "score": p["score"],
                    "tipo": tipo_label,
                    "var_pct": (pos_p["mam_cache"] - pos_p["valor"])
                    / pos_p["valor"]
                    * 100,
                }
            )

        if not _port_stats:
            st.info("Nenhuma posição calculável no portfólio.")
        else:
            total_cap = sum(s["capital"] for s in _port_stats)

            # Métricas ponderadas
            taxa_pond = sum(s["taxa"] * s["capital"] for s in _port_stats) / total_cap
            dur_pond = sum(s["anos"] * s["capital"] for s in _port_stats) / total_cap
            score_pond = sum(s["score"] * s["capital"] for s in _port_stats) / total_cap

            _tipos_cart = {s["tipo"] for s in _port_stats}
            _so_ipca = _tipos_cart <= {"IPCA+/RendA+/Educar+"}
            _so_nominal = _tipos_cart <= {
                "Pós-Fixado (Selic)",
                "Pré-Fixado",
                "CDB",
                "LCI",
                "LCA",
            }
            _sfx_taxa = "real" if _so_ipca else "nominal" if _so_nominal else "mista"

            pm1, pm2, pm3 = st.columns(3)
            with pm1:
                st.metric(
                    "Taxa Média Ponderada",
                    f"{taxa_pond:.2f}% a.a. {_sfx_taxa}",
                    "Média por capital investido",
                    help="Para carteiras mistas (IPCA+ real + Selic/Pré nominal), "
                    "a média é apenas indicativa — não representa uma taxa homogênea."
                    if _sfx_taxa == "mista"
                    else None,
                )
            with pm2:
                st.metric(
                    "Duração Média Ponderada",
                    f"{dur_pond:.1f} anos",
                    "Prazo médio restante da carteira",
                )
            with pm3:
                lbl_s = (
                    "🟢 Serena"
                    if score_pond >= 70
                    else "🟡 Atenção"
                    if score_pond >= 40
                    else "🔴 Risco"
                )
                st.metric(
                    "Saúde Ponderada", f"{score_pond:.0f}/100", lbl_s, delta_color="off"
                )

            # ---- Alertas de concentração ----
            _por_tipo_cap: dict[str, float] = {}
            for s in _port_stats:
                _por_tipo_cap[s["tipo"]] = (
                    _por_tipo_cap.get(s["tipo"], 0.0) + s["capital"]
                )

            _tipo_dominante = max(_por_tipo_cap, key=lambda k: _por_tipo_cap[k])
            _pct_dominante = _por_tipo_cap[_tipo_dominante] / total_cap * 100

            # Tipos sem risco de MaM: concentração é oportunidade perdida, não perigo
            _sem_mam = {"Pós-Fixado (Selic)", "CDB", "LCI", "LCA"}
            _rec_diversificar = {
                "IPCA+/RendA+/Educar+": "Tesouro Selic e/ou Pré-Fixado",
                "Pré-Fixado": "IPCA+ e/ou Tesouro Selic",
            }
            _rec = _rec_diversificar.get(_tipo_dominante, "")

            if _tipo_dominante not in _sem_mam and _rec:
                if _pct_dominante >= 90:
                    st.error(
                        f"🔴 **Concentração crítica em MaM:** {_pct_dominante:.0f}% em "
                        f"**{_tipo_dominante}**. Um choque de taxas afeta fortemente o resgate "
                        f"antecipado. Considere adicionar **{_rec}**.",
                        icon="⚠️",
                    )
                elif _pct_dominante >= 70:
                    st.warning(
                        f"🟡 **Alta exposição a MaM:** {_pct_dominante:.0f}% em "
                        f"**{_tipo_dominante}**. Adicionar **{_rec}** reduz sensibilidade "
                        f"a variações de taxa.",
                        icon="⚠️",
                    )

            st.markdown("---")

            # Alocação por tipo
            col_g1, col_g2 = st.columns(2)

            with col_g1:
                st.markdown("**Alocação por título**")
                _palette = [
                    "#4fc3f7",
                    "#a5d6a7",
                    "#ef9a9a",
                    "#fff176",
                    "#ce93d8",
                    "#ffcc80",
                    "#80cbc4",
                    "#f48fb1",
                    "#b0bec5",
                    "#bcaaa4",
                ]
                _labels_pie = [s["nome"] for s in _port_stats]
                _values_pie = [s["capital"] for s in _port_stats]
                _cores_pie = [
                    _palette[i % len(_palette)] for i in range(len(_port_stats))
                ]
                fig_pie = go.Figure(
                    go.Pie(
                        labels=_labels_pie,
                        values=_values_pie,
                        hole=0.45,
                        marker_colors=_cores_pie,
                        textinfo="label+percent",
                        hovertemplate="%{label}<br>R$ %{value:,.0f}<br>%{percent}<extra></extra>",
                    )
                )
                fig_pie.update_layout(
                    margin=dict(t=10, b=10, l=10, r=10),
                    showlegend=False,
                    paper_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0",
                    height=260,
                )
                st.plotly_chart(fig_pie, use_container_width=True)

            with col_g2:
                st.markdown("**Saúde por posição**")
                _nomes_s = [s["nome"] for s in _port_stats]
                _scores_s = [s["score"] for s in _port_stats]
                _cores_s = [
                    _palette[i % len(_palette)] for i in range(len(_port_stats))
                ]
                fig_bar = go.Figure(
                    go.Bar(
                        x=_scores_s,
                        y=_nomes_s,
                        orientation="h",
                        marker_color=_cores_s,
                        text=[f"{sc:.0f}" for sc in _scores_s],
                        textposition="inside",
                    )
                )
                fig_bar.update_layout(
                    xaxis=dict(range=[0, 100], showgrid=False),
                    yaxis=dict(autorange="reversed"),
                    margin=dict(t=10, b=10, l=10, r=10),
                    paper_bgcolor="rgba(0,0,0,0)",
                    plot_bgcolor="rgba(0,0,0,0)",
                    font_color="#e0e0e0",
                    height=260,
                )
                st.plotly_chart(fig_bar, use_container_width=True)

            # MaM vs Carrego por posição
            st.markdown("**MaM atual vs. Carrego no vencimento**")
            _n = [s["nome"] for s in _port_stats]
            _mam = [s["mam"] for s in _port_stats]
            _car = [s["carrego"] for s in _port_stats]
            _cap = [s["capital"] for s in _port_stats]

            fig_cmp = go.Figure()
            fig_cmp.add_trace(
                go.Bar(name="Capital Investido", x=_n, y=_cap, marker_color="#90caf9")
            )
            fig_cmp.add_trace(
                go.Bar(name="MaM Hoje", x=_n, y=_mam, marker_color="#ef9a9a")
            )
            fig_cmp.add_trace(
                go.Bar(name="Carrego Vencimento", x=_n, y=_car, marker_color="#a5d6a7")
            )
            fig_cmp.update_layout(
                barmode="group",
                margin=dict(t=10, b=10, l=10, r=10),
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font_color="#e0e0e0",
                legend=dict(orientation="h", y=-0.2),
                height=300,
                yaxis=dict(tickprefix="R$ ", separatethousands=True),
            )
            st.plotly_chart(fig_cmp, use_container_width=True)

            # Tabela detalhada
            st.markdown("**Detalhamento por posição**")
            _df_tab = pd.DataFrame(
                [
                    {
                        "Título": s["nome"],
                        "Tipo": s["tipo"],
                        "Capital": formatar_brl(s["capital"]),
                        "Taxa (% a.a.)": f"{s['taxa']:.2f}%",
                        "Prazo (anos)": s["anos"],
                        "MaM Hoje": formatar_brl(s["mam"]),
                        "Var. %": f"{s['var_pct']:+.1f}%",
                        "Carrego": formatar_brl(s["carrego"]),
                        "Saúde": f"{s['score']:.0f}/100",
                    }
                    for s in _port_stats
                ]
            )
            st.dataframe(_df_tab, hide_index=True, use_container_width=True)

            # Visão consolidada por título (só aparece quando há aportes múltiplos)
            _titulos_unicos = {s["nome"] for s in _port_stats}
            if len(_port_stats) > len(_titulos_unicos):
                st.markdown("---")
                st.markdown("**Consolidado por título** — múltiplos aportes detectados")
                _consolidado = {}
                for s in _port_stats:
                    nm = s["nome"]
                    if nm not in _consolidado:
                        _consolidado[nm] = {
                            "Título": nm,
                            "Aportes": 0,
                            "_cap": 0.0,
                            "_mam": 0.0,
                            "_carrego": 0.0,
                            "_taxa_pond": 0.0,
                        }
                    _consolidado[nm]["Aportes"] += 1
                    _consolidado[nm]["_cap"] += s["capital"]
                    _consolidado[nm]["_mam"] += s["mam"]
                    _consolidado[nm]["_carrego"] += s["carrego"]
                    _consolidado[nm]["_taxa_pond"] += s["taxa"] * s["capital"]

                _rows_cons = []
                for d in _consolidado.values():
                    cap = d["_cap"]
                    taxa_media = d["_taxa_pond"] / cap if cap > 0 else 0
                    var = (d["_mam"] - cap) / cap * 100
                    _rows_cons.append(
                        {
                            "Título": d["Título"],
                            "Aportes": d["Aportes"],
                            "Capital Total": formatar_brl(cap),
                            "Taxa Média (% a.a.)": f"{taxa_media:.2f}%",
                            "MaM Consolidado": formatar_brl(d["_mam"]),
                            "Var. %": f"{var:+.1f}%",
                            "No Vencimento": formatar_brl(d["_carrego"]),
                        }
                    )
                st.dataframe(
                    pd.DataFrame(_rows_cons), hide_index=True, use_container_width=True
                )

    # =========================== ABA 4: UTILITÁRIOS ==========================
    with tab_util:
        # Custódia B3
        st.markdown("#### Taxa de Custódia B3")
        if _tipo_sel in ("cdb", "lci", "lca"):
            st.info(
                "Taxa de custódia B3 aplica-se apenas a títulos do Tesouro Direto.",
                icon="ℹ️",
            )
        else:
            descontar_custodia = st.checkbox(
                "Simular impacto da taxa de custódia B3 (0,20% a.a.)",
                value=False,
                key="dash_descontar_custodia",
            )
            if descontar_custodia:
                is_selic = "Selic" in titulo_sel or "Reserva" in titulo_sel
                if is_selic and valor_investido <= 10_000.0:
                    st.success(
                        "**Isenção aplicada:** Tesouro Selic/Reserva até R$ 10.000 é isento (regra desde 2023).",
                        icon="✅",
                    )
                else:
                    custo_anual = resultado["mam"] * 0.002
                    custo_total = resultado["mam"] * (1 - (1 - 0.002) ** anos_restantes)
                    venc_ajustado = valor_vencimento * (1 - 0.002) ** anos_restantes
                    reducao_pct = (
                        (valor_vencimento - venc_ajustado) / valor_vencimento * 100
                    )
                    st.info(
                        f"- Custo anual (sobre MaM atual): **{formatar_brl(custo_anual)}/ano**\n"
                        f"- Custo total estimado até {data_vencimento.strftime('%d/%m/%Y')}: "
                        f"**{formatar_brl(custo_total)}** ({reducao_pct:.1f}% do resgate bruto)\n"
                        f"- Resgate estimado após custódia: **{formatar_brl(venc_ajustado)}**",
                        icon="💰",
                    )

        st.markdown("---")

        # Copiar análise
        st.markdown("#### Copiar Resumo da Análise")
        _pos_score_label = (
            "Sereno" if score >= 70 else "Atenção" if score >= 40 else "Risco de Pânico"
        )
        posicao_str = "ACIMA" if resultado["mam"] >= valor_investido else "ABAIXO"
        _taxa_tipo = "real" if _tipo_sel == "ipca_mais" else "nominal"
        resumo = (
            f"📊 RESUMO DA POSIÇÃO — Renda Fixa CF\n"
            f"{'─' * 40}\n"
            f"Título: {titulo_sel}\n"
            f"Capital investido: {formatar_brl(valor_investido)}\n"
            f"Taxa contratada: {taxa_contratada_pct:.2f}% a.a. {_taxa_tipo}\n"
            f"Data de compra: {data_compra.strftime('%d/%m/%Y')}\n"
            f"Vencimento: {data_vencimento.strftime('%d/%m/%Y')} ({anos_restantes} ano(s))\n"
            f"{'─' * 40}\n"
            f"MaM hoje: {formatar_brl(resultado['mam'])} ({posicao_str} do capital)\n"
            f"Se vender hoje: {formatar_brl(resultado['mam'])}\n"
            f"Se aguardar vencimento: {formatar_brl(valor_vencimento)}\n"
            f"Taxa de mercado atual: {taxa_mercado_pct:.2f}% a.a. {_taxa_tipo}\n"
            f"{'─' * 40}\n"
            f"Saúde da Posição: {score:.0f}/100 — {_pos_score_label}\n"
            f"  • Prazo: {prazo_score:.0f}/60 pts | Posição: {posicao_score:.0f}/40 pts\n"
            f"{'─' * 40}\n"
            f"Gerado em {date.today().strftime('%d/%m/%Y')} via Renda Fixa CF"
        )
        st.code(resumo, language=None)
        st.caption("Selecione o texto acima e copie com Ctrl+C / Cmd+C.")

        st.markdown("---")
        st.markdown("#### Exportar Portfólio")

        def _gerar_csv() -> str:
            rows = []
            for i, p in enumerate(portfolio):
                c = _calcs_port[i]
                if c is None:
                    continue
                var = (p["mam_cache"] - p["valor"]) / p["valor"] * 100
                rows.append(
                    {
                        "Título": p["titulo"],
                        "Tipo": p.get("tipo_asset", "ipca_mais"),
                        "Capital (R$)": p["valor"],
                        "Taxa Contratada (% a.a.)": p["taxa"],
                        "Data de Compra": p["data_compra"],
                        "Vencimento": p["vencimento"],
                        "Anos Restantes": c["anos_res"],
                        "MaM Hoje (R$)": round(p["mam_cache"], 2),
                        "Var. MaM (%)": round(var, 2),
                        "No Vencimento (R$)": round(p["carrego_cache"], 2),
                        "Saúde (0-100)": round(c["score"], 1),
                    }
                )
            return pd.DataFrame(rows).to_csv(index=False, sep=";", decimal=",")

        st.download_button(
            "Baixar portfólio (.csv)",
            data=_gerar_csv(),
            file_name=f"portfolio_renda_fixa_{date.today().isoformat()}.csv",
            mime="text/csv",
            icon=":material/download:",
            help="Exporta todas as posições com métricas calculadas. Abre no Excel — separador ';', decimal ','.",
        )

    # -----------------------------------------------------------------------
    # Persiste preferências
    # -----------------------------------------------------------------------
    salvar(
        {
            "dash_descontar_custodia": st.session_state.get(
                "dash_descontar_custodia", False
            ),
            "dash_choque_stress": st.session_state.get("dash_choque_stress", 2.0),
            "_portfolio": st.session_state.get("_portfolio", []),
            "_analysis_pos_idx": st.session_state.get("_analysis_pos_idx", 0),
            "venda_ipca_b": st.session_state.get("venda_ipca_b", 5.0),
            # Formulário de nova posição
            "port_cat": st.session_state.get("port_cat"),
            "port_titulo": st.session_state.get("port_titulo"),
            "port_valor": st.session_state.get("port_valor", 10_000.0),
            "port_taxa": st.session_state.get("port_taxa", 5.50),
            "port_data": st.session_state.get("port_data"),
            "port_vencimento": st.session_state.get("port_vencimento"),
            # Calculadora de Aportes Mensais
            "dash_calc_ipca": st.session_state.get("dash_calc_ipca", 5.0),
            "dash_calc_selic": st.session_state.get("dash_calc_selic", 14.75),
            "dash_calc_pre": st.session_state.get("dash_calc_pre", 14.5),
            "dash_calc_ipca_plus": st.session_state.get("dash_calc_ipca_plus", 7.0),
            "dash_calc_cdb": st.session_state.get("dash_calc_cdb", 14.0),
            "dash_calc_lci": st.session_state.get("dash_calc_lci", 11.5),
            "dash_calc_lca": st.session_state.get("dash_calc_lca", 11.2),
            "dash_calc_aporte": st.session_state.get("dash_calc_aporte", 500.0),
            "dash_calc_meta": st.session_state.get("dash_calc_meta", 200_000.0),
            "dash_calc_prazo_proj": st.session_state.get("dash_calc_prazo_proj", 5),
            "dash_calc_prazo_rev": st.session_state.get("dash_calc_prazo_rev", 5),
            "dash_calc_capital": st.session_state.get(
                "dash_calc_capital", valor_investido
            ),
            "dash_calc_cap_rev": st.session_state.get(
                "dash_calc_cap_rev", valor_investido
            ),
        }
    )
