"""
Tela 1 — Seu Dashboard

Portfólio como visão principal; análise detalhada como drill-down da posição selecionada.
"""

import streamlit as st
import pandas as pd
import base64
from pathlib import Path
from datetime import date, timedelta

from core.financas import (
    formatar_brl,
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
from core.graficos import (
    TEXTO as _GRAF_TEXTO,
    _aplicar_tema,
)
import plotly.graph_objects as go

from telas._dashboard_metricas import calcular_posicao_ntnb, calcular_posicao_simples
from telas import (
    _dashboard_aba_portfolio,
    _dashboard_aba_posicao,
    _dashboard_aba_simulacoes,
    _dashboard_aba_utilitarios,
    _dashboard_calculadora,
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

    with st.spinner("Sincronizando taxas com o Tesouro Direto e Banco Central..."):
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
                with st.spinner("Consultando taxa Selic histórica no Banco Central..."):
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
                margin=dict(t=36, b=40, l=10, r=10),
                height=210,
                legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.12),
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
                _aplicar_tema(_fig_t)
                _fig_t.update_layout(
                    **_dl,
                    title=dict(
                        text="Alocação por Tipo",
                        font=dict(size=12, color=_GRAF_TEXTO),
                        x=0.5,
                        xanchor="center",
                    ),
                )
                st.plotly_chart(_fig_t, width="stretch", theme=None)
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
                _aplicar_tema(_fig_p)
                _fig_p.update_layout(
                    **_dl,
                    title=dict(
                        text="Alocação por Prazo",
                        font=dict(size=12, color=_GRAF_TEXTO),
                        x=0.5,
                        xanchor="center",
                    ),
                )
                st.plotly_chart(_fig_p, width="stretch", theme=None)

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
            width="stretch",
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
        _dashboard_calculadora.renderizar(df_titulos, 10_000.0)
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

    # As demais chaves de calc/pos (taxas, datas de compra, prazo/posição score etc.)
    # são consumidas dentro de cada aba extraída — aqui só o necessário para o
    # resumo de sidebar (_dash_pos) e o valor_investido usado no salvar() abaixo.
    titulo_sel = pos["titulo"]
    valor_investido = pos["valor"]
    data_vencimento = calc["dv"]
    resultado = calc["res"]
    valor_vencimento = calc["vf"]
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
        _dashboard_aba_posicao.renderizar(pos, calc, vna)

    # =========================== ABA 2: SIMULAÇÕES ===========================
    with tab_sim:
        _dashboard_aba_simulacoes.renderizar(pos, calc, vna, df_titulos)

    # =========================== ABA 3: PORTFÓLIO ============================
    with tab_port:
        _dashboard_aba_portfolio.renderizar(portfolio, _calcs_port, vna)

    # =========================== ABA 4: UTILITÁRIOS ==========================
    with tab_util:
        _dashboard_aba_utilitarios.renderizar(pos, calc, portfolio, _calcs_port)

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
