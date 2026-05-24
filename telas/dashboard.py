"""
Tela 1 — Seu Dashboard

Portfólio como visão principal; análise detalhada como drill-down da posição selecionada.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from core.financas import (
    datas_cupom_ntnb,
    pu_ntnb,
    metricas_carteira,
    serie_paradoxo,
    formatar_brl,
    aliquota_iof_renda_fixa,
    aliquota_ir_renda_fixa,
    retorno_liquido_ir,
)
from core.dados import obter_dados_completos, CATEGORIAS_TITULOS, TITULOS_CONFIG, TITULOS_BATALHA
from core.persistencia import carregar, salvar, inicializar_session
from core.graficos import grafico_paradoxo, grafico_score
import plotly.graph_objects as go


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def _serie_cached(vna, taxa_contratada, taxa_mercado, compra, vencimento, qtd, tem_cupom):
    return serie_paradoxo(vna, taxa_contratada, taxa_mercado, compra, vencimento, qtd, tem_cupom)


def render():
    st.session_state["_page_id"] = "dashboard"

    _prefs = carregar()
    inicializar_session(_prefs)

    # -----------------------------------------------------------------------
    # Cabeçalho
    # -----------------------------------------------------------------------
    st.markdown("""
<div class="hero-banner">
  <div>
    <div class="hero-tag">Dashboard Principal</div>
    <h1 class="hero-title">Renda Fixa <span>CF</span></h1>
    <p class="hero-subtitle">Visualize o paradoxo da renda fixa: a volatilidade que você
    <em>sente</em> versus a segurança que você <em>tem</em>.</p>
  </div>
  <div class="hero-badge">📊 Tesouro Direto</div>
</div>
""", unsafe_allow_html=True)

    with st.spinner("Carregando dados do Tesouro Direto e BCB..."):
        df_ipca, df_titulos, vna = obter_dados_completos()

    fonte = "✅ Dados ao vivo — Tesouro Direto" if not df_titulos.empty else "⚠️ Modo offline — dados de referência"
    st.caption(fonte)

    # -----------------------------------------------------------------------
    # Helper: calcula todas as métricas de uma posição a partir dos inputs
    # -----------------------------------------------------------------------
    def _calcular(titulo: str, valor: float, taxa_pct: float, data_compra_str: str):
        dc   = date.fromisoformat(data_compra_str)
        linha = df_titulos[df_titulos["nome"] == titulo] if not df_titulos.empty else pd.DataFrame()
        if not linha.empty:
            taxa_mkt_pct = float(linha["taxa_compra"].values[0])
            taxa_vda_pct = float(linha["taxa_venda"].values[0]) if "taxa_venda" in linha.columns else None
            dv           = date.fromisoformat(str(linha["vencimento"].values[0])[:10])
        else:
            cfg          = TITULOS_CONFIG.get(titulo, {})
            taxa_mkt_pct = taxa_pct + 2.0
            taxa_vda_pct = None
            dv           = cfg.get("vencimento", date(2035, 5, 15))

        tc, tm = taxa_pct / 100, taxa_mkt_pct / 100
        cupom  = "Juros Semestrais" in titulo

        if dc >= dv:
            return None

        cpns_c = datas_cupom_ntnb(dc, dv) if cupom else []
        pu_c   = pu_ntnb(vna, tc, dc, dv, cpns_c)
        if pu_c <= 0:
            return None

        cpns_h = datas_cupom_ntnb(date.today(), dv) if cupom else []
        res    = metricas_carteira(
            valor_investido=valor, pu_na_compra=pu_c,
            taxa_real_contratada=tc, taxa_real_mercado=tm,
            vna=vna, data_hoje=date.today(), data_vencimento=dv,
            datas_cupom=cpns_h,
        )

        anos_tot = (dv - dc).days / 365
        anos_res = max(1, round((dv - date.today()).days / 365))
        vf       = valor * (1 + tc) ** anos_tot

        diff_pct = (res["mam"] - valor) / valor * 100
        ps       = min(60.0, 10.0 + anos_res * 7.0)
        poss     = max(0.0, min(40.0, 40.0 + diff_pct * 1.6))

        return dict(
            res=res, taxa_mkt_pct=taxa_mkt_pct, taxa_vda_pct=taxa_vda_pct,
            dv=dv, dc=dc, tc=tc, tm=tm, cupom=cupom,
            pu_c=pu_c, cpns_h=cpns_h, anos_tot=anos_tot, anos_res=anos_res,
            vf=vf, prazo_score=ps, posicao_score=poss, score=ps + poss,
            taxa_pct=taxa_pct,
        )

    # -----------------------------------------------------------------------
    # Portfólio
    # -----------------------------------------------------------------------
    if "_portfolio" not in st.session_state:
        st.session_state["_portfolio"] = []

    portfolio = st.session_state["_portfolio"]

    st.divider()
    st.subheader("💼  Seu Portfólio")

    # ---- Formulário de adicionar posição (código inline, keys consistentes) ----
    def _render_form():
        _fc = st.session_state.get("port_cat")
        if _fc and _fc in CATEGORIAS_TITULOS and st.session_state.get("port_titulo") not in CATEGORIAS_TITULOS[_fc]:
            st.session_state["port_titulo"] = CATEGORIAS_TITULOS[_fc][0]

        _fc1, _fc2 = st.columns([1, 2])
        with _fc1:
            _pcat = st.selectbox("Categoria", list(CATEGORIAS_TITULOS.keys()), key="port_cat")
        with _fc2:
            _ptit = st.selectbox("Título", CATEGORIAS_TITULOS[_pcat], key="port_titulo")

        _fc3, _fc4, _fc5 = st.columns([1.6, 1.2, 1.2])
        with _fc3:
            _pval = st.number_input(
                "Valor Investido (R$)", min_value=30.0, max_value=1_000_000.0,
                value=10_000.0, step=500.0, format="%.2f", key="port_valor",
            )
        with _fc4:
            _ptax = st.number_input(
                "Taxa Contratada (% a.a. real)", min_value=1.0, max_value=15.0,
                value=5.50, step=0.05, format="%.2f", key="port_taxa",
            )
        with _fc5:
            _pdat = st.date_input(
                "Data de Compra",
                value=date.today() - timedelta(days=365),
                max_value=date.today() - timedelta(days=1),
                key="port_data",
            )

        if st.button("Adicionar ao portfólio", type="primary", key="port_btn"):
            c = _calcular(_ptit, _pval, _ptax, _pdat.isoformat())
            if c is None:
                st.error("Data de compra deve ser anterior ao vencimento do título.")
            else:
                chave = (_ptit, _pval, _ptax, _pdat.isoformat())
                if any((p["titulo"], p["valor"], p["taxa"], p["data_compra"]) == chave
                       for p in st.session_state["_portfolio"]):
                    st.info("Esta posição já está no portfólio.")
                else:
                    st.session_state["_portfolio"].append(dict(
                        titulo=_ptit, valor=_pval, taxa=_ptax,
                        data_compra=_pdat.isoformat(),
                        mam_cache=c["res"]["mam"], carrego_cache=c["vf"],
                        vencimento=c["dv"].isoformat(), anos=c["anos_res"],
                    ))
                    st.session_state["_analysis_pos_idx"] = len(st.session_state["_portfolio"]) - 1
                    st.rerun()

    # ---- Estado vazio ----
    if not portfolio:
        st.info(
            "**Bem-vindo!** Ainda não há posições no portfólio. "
            "Adicione sua primeira posição abaixo ou carregue um exemplo.",
            icon="👋",
        )
        if st.button("📋  Carregar Exemplo: Tesouro IPCA+ 2032 comprado em 20/05/2026", type="secondary"):
            c_ex = _calcular("Tesouro IPCA+ 2032", 15_000.0, 7.50, "2026-05-20")
            if c_ex:
                st.session_state["_portfolio"] = [dict(
                    titulo="Tesouro IPCA+ 2032", valor=15_000.0, taxa=7.50,
                    data_compra="2026-05-20",
                    mam_cache=c_ex["res"]["mam"], carrego_cache=c_ex["vf"],
                    vencimento=c_ex["dv"].isoformat(), anos=c_ex["anos_res"],
                )]
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
            c = _calcular(p["titulo"], p["valor"], p["taxa"], p["data_compra"])
            if c is not None:
                p["mam_cache"]     = c["res"]["mam"]
                p["carrego_cache"] = c["vf"]
                p["anos"]          = c["anos_res"]
            _calcs_port.append(c)

        # Métricas consolidadas
        total_cap     = sum(p["valor"]         for p in portfolio)
        total_mam     = sum(p["mam_cache"]     for p in portfolio)
        total_carrego = sum(p["carrego_cache"] for p in portfolio)
        var_total     = (total_mam - total_cap) / total_cap * 100

        _scores = [c["score"] for c in _calcs_port if c is not None]
        score_medio = sum(_scores) / len(_scores) if _scores else 0.0
        score_label = "🟢 Sereno" if score_medio >= 70 else "🟡 Atenção" if score_medio >= 40 else "🔴 Risco"

        _mc1, _mc2, _mc3, _mc4 = st.columns(4)
        with _mc1:
            st.metric("Capital Investido", formatar_brl(total_cap), f"{len(portfolio)} posição(ões)")
        with _mc2:
            st.metric("MaM Consolidado", formatar_brl(total_mam),
                      f"{var_total:+.1f}% vs capital",
                      delta_color="normal",
                      help=(
                          "**Marcação a Mercado (MaM):** valor que você receberia se vendesse "
                          "todas as posições hoje, calculado com base nas taxas atuais do mercado. "
                          "Pode estar abaixo do capital investido quando as taxas sobem — "
                          "mas isso não afeta o que você recebe se aguardar o vencimento."
                      ))
        with _mc3:
            st.metric("No Vencimento", formatar_brl(total_carrego),
                      f"+{(total_carrego / total_cap - 1) * 100:.1f}% vs capital",
                      help=(
                          "**Carrego consolidado:** soma do valor que cada posição pagará "
                          "se mantida até o vencimento, calculado pela taxa contratada na compra. "
                          "Este é o valor garantido — independente das oscilações de mercado."
                      ))
        with _mc4:
            st.metric("Saúde da Carteira", f"{score_medio:.0f}/100", score_label, delta_color="off",
                      help=(
                          "**Índice de Saúde (0–100):** mede o quanto sua carteira está bem "
                          "posicionada para atravessar a volatilidade sem precisar vender.\n\n"
                          "- **⏳ Prazo (até 60 pts):** quanto mais tempo até o vencimento, "
                          "mais fácil aguardar.\n"
                          "- **📊 Posição (até 40 pts):** quanto mais próximo do capital investido "
                          "estiver o MaM, menor o desconforto.\n\n"
                          "**70–100 🟢 Saudável · 40–69 🟡 Atenção · 0–39 🔴 Risco**"
                      ))

        # Tabela
        rows_p = []
        for i, p in enumerate(portfolio):
            var = (p["mam_cache"] - p["valor"]) / p["valor"] * 100
            rows_p.append({
                "#":             i + 1,
                "Título":        p["titulo"].replace("Tesouro ", ""),
                "Capital":       formatar_brl(p["valor"]),
                "Taxa":          f"{p['taxa']:.2f}%",
                "MaM Hoje":      formatar_brl(p["mam_cache"]),
                "Var. %":        f"{var:+.1f}%",
                "Vence em":      formatar_brl(p["carrego_cache"]),
                "Vencimento":    p["vencimento"],
            })
        st.dataframe(pd.DataFrame(rows_p), hide_index=True, use_container_width=True)

        # Controles de remoção
        _nomes_r = [
            f"#{i+1} — {p['titulo'].replace('Tesouro ', '')} | {formatar_brl(p['valor'])} | compra {p['data_compra']}"
            for i, p in enumerate(portfolio)
        ]
        _rc1, _rc2, _rc3 = st.columns([4, 1, 1])
        with _rc1:
            _rem_i = st.selectbox(
                "Remover", range(len(portfolio)),
                format_func=lambda i: _nomes_r[i],
                key="port_rem_idx", label_visibility="collapsed",
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
            st.caption("Preencha os dados e clique em Adicionar — sem precisar sair desta seção.")
            _render_form()

    # -----------------------------------------------------------------------
    # Análise Detalhada (só renderiza se há posições)
    # -----------------------------------------------------------------------
    if not portfolio:
        salvar({
            "dash_descontar_custodia": st.session_state.get("dash_descontar_custodia", False),
            "dash_choque_stress":      st.session_state.get("dash_choque_stress", 2.0),
            "_portfolio":              [],
            "_analysis_pos_idx":       0,
        })
        return

    st.divider()
    st.subheader("🔍  Análise Detalhada")

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

    pos  = portfolio[sel_idx]
    calc = _calcular(pos["titulo"], pos["valor"], pos["taxa"], pos["data_compra"])

    if calc is None:
        st.error("⛔ Não foi possível calcular esta posição. Verifique se a data de compra é válida.")
        return

    titulo_sel          = pos["titulo"]
    valor_investido     = pos["valor"]
    taxa_contratada_pct = pos["taxa"]
    data_compra         = calc["dc"]
    data_vencimento     = calc["dv"]
    taxa_mercado_pct    = calc["taxa_mkt_pct"]
    taxa_venda_pct      = calc["taxa_vda_pct"]
    taxa_contratada     = calc["tc"]
    taxa_mercado        = calc["tm"]
    tem_cupom           = calc["cupom"]
    pu_compra           = calc["pu_c"]
    cpns_hoje           = calc["cpns_h"]
    resultado           = calc["res"]
    anos_restantes      = calc["anos_res"]
    anos_totais         = calc["anos_tot"]
    valor_vencimento    = calc["vf"]
    prazo_score         = calc["prazo_score"]
    posicao_score       = calc["posicao_score"]
    score               = calc["score"]

    st.session_state["_dash_pos"] = {
        "titulo":    titulo_sel,
        "mam":       resultado["mam"],
        "carrego":   valor_vencimento,
        "data_venc": data_vencimento,
        "score":     score,
    }

    # -----------------------------------------------------------------------
    # Abas
    # -----------------------------------------------------------------------
    tab_pos, tab_sim, tab_port, tab_util = st.tabs([
        "📊  Posição",
        "⚡  Simulações",
        "📈  Portfólio",
        "🛠️  Utilitários",
    ])

    # ============================= ABA 1: POSIÇÃO ============================
    with tab_pos:
        # IOF ativo — aviso prioritário
        dias_investido = (date.today() - data_compra).days
        if 0 < dias_investido < 30:
            aliq_iof     = aliquota_iof_renda_fixa(dias_investido)
            lucro_bruto  = max(0.0, resultado["mam"] - valor_investido)
            iof_estimado = lucro_bruto * aliq_iof
            st.warning(
                f"**IOF Regressivo Ativo** — {dias_investido} dia(s) de aplicação. "
                f"Alíquota: **{aliq_iof*100:.0f}%** · IOF estimado: **{formatar_brl(iof_estimado)}**. "
                f"Zera daqui a **{30 - dias_investido} dia(s)**.",
                icon="🔴",
            )

        # KPI cards
        col1, col2, col3 = st.columns(3)
        variacao = resultado["variacao_dia"]

        with col1:
            st.metric(
                "Variação do Dia (MaM)", f"{variacao:+.2f}%", f"{variacao:.2f}%",
                delta_color="normal",
                help="Oscilação estimada do PU de mercado hoje vs. ontem",
            )

        with col2:
            delta_vs = resultado["mam"] - valor_investido
            delta_str = (
                f"-{formatar_brl(abs(delta_vs))} vs. capital"
                if delta_vs < 0
                else f"+{formatar_brl(delta_vs)} vs. capital"
            )
            st.metric(
                "💸  Resgate Antecipado Hoje", formatar_brl(resultado["mam"]),
                delta_str, delta_color="normal",
                help="Valor que você receberia se vender hoje — sujeito à MaM",
            )
            if taxa_venda_pct and taxa_venda_pct > taxa_mercado_pct:
                spread_bps   = (taxa_venda_pct - taxa_mercado_pct) * 100
                pu_venda_est = pu_ntnb(vna, taxa_venda_pct / 100, date.today(), data_vencimento, cpns_hoje)
                spread_rs    = (resultado["pu_hoje"] - pu_venda_est) * resultado["quantidade"]
                st.caption(
                    f"⚠️ Spread bid-ask: {spread_bps:.0f} bps — impacto estimado: "
                    f"{formatar_brl(spread_rs)} a menos no resgate real."
                )

        with col3:
            ganho_real_pct = (valor_vencimento / valor_investido - 1) * 100
            if "RendA+" in titulo_sel:
                lbl = "🏦  Capital Acumulado (RendA+)"
            elif "Educar+" in titulo_sel:
                lbl = "🎓  Capital Acumulado (Educar+)"
            else:
                lbl = "🛡️  Resgate no Vencimento"
            st.metric(lbl, formatar_brl(valor_vencimento),
                      f"+{ganho_real_pct:.1f}% real acumulado", delta_color="normal")

        # Banner comportamental + saúde
        col_b, col_g = st.columns([1.8, 1])
        with col_b:
            if resultado["mam"] < valor_investido:
                st.markdown("""
        <div class="alerta-mercado">
            ⚠️ <strong>Por que minha carteira aparece "negativa"?</strong><br>
            <small>A Marcação a Mercado reflete o preço que o mercado pagaria <em>agora</em>.
            Quando as taxas sobem, esse preço cai — mas não afeta o que você receberá no vencimento.
            Se você <strong>não vender antes</strong>, receberá exatamente a taxa contratada,
            corrigida pelo IPCA.</small>
        </div>""", unsafe_allow_html=True)
            else:
                st.markdown("""
        <div class="badge-seguranca">
            ✅ <strong>Sua posição está acima do capital investido.</strong><br>
            <small>As taxas caíram desde sua compra, valorizando o título. Você pode resgatar
            antecipadamente com ganho — ou manter até o vencimento para receber a taxa integral.</small>
        </div>""", unsafe_allow_html=True)

        with col_g:
            st.metric(
                "Saúde da Posição", "",
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
        st.markdown("#### 📈  O Gráfico do Paradoxo")
        col_graf, col_leg = st.columns([3, 1])

        with st.spinner("Calculando série temporal..."):
            df_paradoxo = _serie_cached(
                vna, taxa_contratada, taxa_mercado,
                data_compra, data_vencimento, resultado["quantidade"], tem_cupom,
            )

        with col_graf:
            st.plotly_chart(
                grafico_paradoxo(
                    df_paradoxo, data_compra=data_compra,
                    data_vencimento=data_vencimento,
                    datas_cupom=cpns_hoje if tem_cupom else None,
                ),
                use_container_width=True,
            )

        with col_leg:
            st.markdown("**O que estou vendo?**")
            padrao_c = (
                "Oscila em **dente de serra** a cada semestre — reflexo dos cupons."
                if tem_cupom else "Curva **exponencial lisa** — sem cupons."
            )
            st.markdown(f"""
**🔴 MaM** — preço de mercado dia a dia.
É o que você recebe **se vender hoje**.

---

**🟢 Carrego** — trajetória pela taxa de
**{taxa_contratada_pct:.2f}% a.a.** contratada.
{padrao_c}
É o que você recebe **se aguardar
{data_vencimento.strftime('%d/%m/%Y')}**.

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

    # =========================== ABA 2: SIMULAÇÕES ===========================
    with tab_sim:
        # Stress Test
        st.markdown("#### ⚡  Choque de Taxa — Adverso e Favorável")
        st.caption("O carrego permanece inalterado em ambos os cenários.")

        choque_stress = st.slider(
            "Magnitude do Choque (p.p.)",
            min_value=0.0, max_value=5.0, value=2.0, step=0.25,
            format="%.2f p.p.", key="dash_choque_stress",
        )

        taxa_adv = taxa_mercado + choque_stress / 100
        res_adv  = metricas_carteira(
            valor_investido=valor_investido, pu_na_compra=pu_compra,
            taxa_real_contratada=taxa_contratada, taxa_real_mercado=taxa_adv,
            vna=vna, data_hoje=date.today(), data_vencimento=data_vencimento,
            datas_cupom=cpns_hoje,
        )
        taxa_fav = max(0.001, taxa_mercado - choque_stress / 100)
        res_fav  = metricas_carteira(
            valor_investido=valor_investido, pu_na_compra=pu_compra,
            taxa_real_contratada=taxa_contratada, taxa_real_mercado=taxa_fav,
            vna=vna, data_hoje=date.today(), data_vencimento=data_vencimento,
            datas_cupom=cpns_hoje,
        )
        tombo_adv     = res_adv["mam"] - resultado["mam"]
        tombo_adv_pct = (tombo_adv / resultado["mam"] * 100) if resultado["mam"] > 0 else 0.0
        ganho_fav     = res_fav["mam"] - resultado["mam"]
        ganho_fav_pct = (ganho_fav / resultado["mam"] * 100) if resultado["mam"] > 0 else 0.0

        st.markdown("**🔴 Cenário Adverso — Taxa Sobe**")
        ca1, ca2, ca3 = st.columns(3)
        with ca1:
            st.metric("Taxa de Mercado", f"{taxa_adv*100:.2f}% a.a.",
                      f"+{choque_stress:.2f} p.p.", delta_color="inverse")
        with ca2:
            st.metric("Resgate Antecipado", formatar_brl(res_adv["mam"]),
                      formatar_brl(tombo_adv), delta_color="inverse")
        with ca3:
            st.metric("Impacto", f"{tombo_adv_pct:+.1f}%")
            st.caption(f"🛡️ Carrego no vencimento: **{formatar_brl(valor_vencimento)}** — inalterado")

        st.markdown("""<div class="alerta-mercado" style="margin-bottom:0.8rem">
🧠 <strong>Este tombo é real — mas temporário.</strong>
Vender agora cristaliza o prejuízo. Aguardar o vencimento o elimina completamente.
</div>""", unsafe_allow_html=True)

        st.markdown("**🟢 Cenário Favorável — Taxa Cai**")
        cf1, cf2, cf3 = st.columns(3)
        with cf1:
            st.metric("Taxa de Mercado", f"{taxa_fav*100:.2f}% a.a.",
                      f"-{choque_stress:.2f} p.p.", delta_color="normal")
        with cf2:
            st.metric("Resgate Antecipado", formatar_brl(res_fav["mam"]),
                      f"+{formatar_brl(ganho_fav)}", delta_color="normal")
        with cf3:
            st.metric("Ganho de Capital", f"{ganho_fav_pct:+.1f}%",
                      "Vender agora captura este ganho", delta_color="normal")

        st.markdown("""<div class="badge-seguranca">
💡 <strong>Oportunidade de MaM:</strong> Quando taxas caem, você pode vender com ganho
— ou manter e receber a taxa contratada integral.
</div>""", unsafe_allow_html=True)

        st.markdown("---")

        # Calculadora Reversa
        st.markdown("#### 🔢  Calculadora Reversa")
        st.caption("Quanto preciso investir hoje para ter R$ X no vencimento?")
        cr1, cr2 = st.columns(2)
        with cr1:
            meta_brl = st.number_input("Meta no vencimento (R$)", min_value=1_000.0,
                                        max_value=10_000_000.0, value=100_000.0,
                                        step=5_000.0, format="%.2f", key="calc_meta")
            taxa_rev = st.number_input("Taxa real contratada (% a.a.)", min_value=1.0,
                                        max_value=20.0, value=taxa_contratada_pct,
                                        step=0.05, format="%.2f", key="calc_taxa")
        with cr2:
            anos_rev = st.number_input("Prazo (anos)", min_value=1, max_value=40,
                                        value=anos_restantes, step=1, key="calc_anos")
            ipca_rev = st.number_input("IPCA projetado (% a.a.)", min_value=1.0,
                                        max_value=15.0, value=5.0, step=0.1,
                                        format="%.1f", key="calc_ipca")

        taxa_nom_rev = (1 + taxa_rev / 100) * (1 + ipca_rev / 100) - 1
        cap_nec      = meta_brl / (1 + taxa_nom_rev) ** anos_rev
        meta_real    = meta_brl / (1 + ipca_rev / 100) ** anos_rev

        rr1, rr2, rr3 = st.columns(3)
        with rr1:
            st.metric("Capital Necessário Hoje", formatar_brl(cap_nec),
                      f"Para ter {formatar_brl(meta_brl)} em {anos_rev}a")
        with rr2:
            st.metric("Valor Real da Meta (hoje)", formatar_brl(meta_real),
                      "Poder de compra equivalente")
        with rr3:
            st.metric("Taxa Nominal Equiv.", f"{taxa_nom_rev*100:.2f}% a.a.",
                      f"{taxa_rev:.2f}% real + {ipca_rev:.1f}% IPCA")

        st.markdown("---")

        # Estou Pensando em Vender
        st.markdown("#### 🤔  Estou Pensando em Vender — Qual o Custo Real?")
        cv1, cv2 = st.columns(2)
        with cv1:
            mam_input    = st.number_input("Resgate antecipado hoje (R$)", min_value=1.0,
                                            max_value=10_000_000.0,
                                            value=float(round(resultado["mam"], 2)),
                                            step=100.0, format="%.2f", key="venda_mam")
            anos_venda   = st.number_input("Você aguardaria quantos anos?", min_value=1,
                                            max_value=anos_restantes,
                                            value=min(3, anos_restantes), step=1,
                                            key="venda_anos")
        with cv2:
            taxa_reinv   = st.number_input("Taxa de reinvestimento (% a.a.)", min_value=1.0,
                                            max_value=25.0,
                                            value=float(round(taxa_mercado_pct, 2)),
                                            step=0.1, format="%.2f", key="venda_reinv")
            ir_venda     = st.checkbox("Considerar IR na venda", value=True, key="venda_ir")

        lucro_v = max(0.0, mam_input - valor_investido)
        if ir_venda:
            dias_tot  = (date.today() - data_compra).days
            aliq_ir_v = aliquota_ir_renda_fixa(dias_tot / 365)
            ir_dev    = lucro_v * aliq_ir_v
        else:
            ir_dev, aliq_ir_v = 0.0, 0.0

        liq_venda     = mam_input - ir_dev
        val_reinvest  = liq_venda * (1 + taxa_reinv / 100) ** anos_venda
        val_aguardar  = valor_investido * (1 + taxa_contratada) ** anos_venda * (1.05 ** anos_venda)
        diferenca     = val_reinvest - val_aguardar

        st.markdown(f"**Comparação: vender agora vs. aguardar {anos_venda} ano(s)**")
        cv_c1, cv_c2, cv_c3 = st.columns(3)
        with cv_c1:
            st.metric("Cenário A — Vender e Reinvestir", formatar_brl(val_reinvest),
                      f"Líquido: {formatar_brl(liq_venda)} → {taxa_reinv:.1f}% a.a.",
                      delta_color="normal" if diferenca >= 0 else "inverse")
        with cv_c2:
            st.metric("Cenário B — Aguardar (carrego)", formatar_brl(val_aguardar),
                      f"{taxa_contratada_pct:.2f}% real + IPCA 5% aprox.", delta_color="off")
        with cv_c3:
            st.metric("Diferença A−B", formatar_brl(diferenca),
                      "Vender compensa" if diferenca > 0 else "Aguardar compensa",
                      delta_color="normal" if diferenca > 0 else "inverse")

        if ir_dev > 0:
            st.caption(f"IR estimado: {formatar_brl(ir_dev)} ({aliq_ir_v*100:.1f}% sobre lucro de {formatar_brl(lucro_v)}).")
        st.caption("⚠️ IPCA do Cenário B aproximado em 5% a.a.")

    # =========================== ABA 3: PORTFÓLIO ============================
    with tab_port:
        st.caption("Visão estatística de toda a carteira — independente da posição selecionada acima.")

        _tipo_map  = {"selic": "Pós-Fixado (Selic)", "pre": "Pré-Fixado", "ipca_mais": "IPCA+/RendA+/Educar+"}
        _cor_tipo  = {"Pós-Fixado (Selic)": "#4fc3f7", "Pré-Fixado": "#ef9a9a", "IPCA+/RendA+/Educar+": "#a5d6a7"}

        # Detecta tipo de cada posição usando TITULOS_CONFIG
        _port_stats = []
        for i, p in enumerate(_calcs_port):
            if p is None:
                continue
            pos_p = portfolio[i]
            cfg   = TITULOS_BATALHA.get(pos_p["titulo"], {})
            tipo  = cfg.get("tipo", "ipca_mais")
            tipo_label = _tipo_map.get(tipo, "IPCA+/RendA+/Educar+")
            _port_stats.append({
                "nome":       pos_p["titulo"].replace("Tesouro ", ""),
                "capital":    pos_p["valor"],
                "mam":        pos_p["mam_cache"],
                "carrego":    pos_p["carrego_cache"],
                "taxa":       pos_p["taxa"],
                "anos":       pos_p["anos"],
                "score":      p["score"],
                "tipo":       tipo_label,
                "var_pct":    (pos_p["mam_cache"] - pos_p["valor"]) / pos_p["valor"] * 100,
            })

        if not _port_stats:
            st.info("Nenhuma posição calculável no portfólio.")
        else:
            total_cap = sum(s["capital"] for s in _port_stats)

            # Métricas ponderadas
            taxa_pond = sum(s["taxa"] * s["capital"] for s in _port_stats) / total_cap
            dur_pond  = sum(s["anos"] * s["capital"] for s in _port_stats) / total_cap
            score_pond = sum(s["score"] * s["capital"] for s in _port_stats) / total_cap

            pm1, pm2, pm3 = st.columns(3)
            with pm1:
                st.metric("Taxa Média Ponderada", f"{taxa_pond:.2f}% a.a. real",
                          "Média por capital investido")
            with pm2:
                st.metric("Duração Média Ponderada", f"{dur_pond:.1f} anos",
                          "Prazo médio restante da carteira")
            with pm3:
                lbl_s = "🟢 Serena" if score_pond >= 70 else "🟡 Atenção" if score_pond >= 40 else "🔴 Risco"
                st.metric("Saúde Ponderada", f"{score_pond:.0f}/100", lbl_s, delta_color="off")

            st.markdown("---")

            # Alocação por tipo
            col_g1, col_g2 = st.columns(2)

            with col_g1:
                st.markdown("**Alocação por título**")
                _palette    = ["#4fc3f7","#a5d6a7","#ef9a9a","#fff176","#ce93d8",
                               "#ffcc80","#80cbc4","#f48fb1","#b0bec5","#bcaaa4"]
                _labels_pie = [s["nome"] for s in _port_stats]
                _values_pie = [s["capital"] for s in _port_stats]
                _cores_pie  = [_palette[i % len(_palette)] for i in range(len(_port_stats))]
                fig_pie = go.Figure(go.Pie(
                    labels=_labels_pie,
                    values=_values_pie,
                    hole=0.45,
                    marker_colors=_cores_pie,
                    textinfo="label+percent",
                    hovertemplate="%{label}<br>R$ %{value:,.0f}<br>%{percent}<extra></extra>",
                ))
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
                _nomes_s  = [s["nome"] for s in _port_stats]
                _scores_s = [s["score"] for s in _port_stats]
                _cores_s  = [_palette[i % len(_palette)] for i in range(len(_port_stats))]
                fig_bar = go.Figure(go.Bar(
                    x=_scores_s, y=_nomes_s, orientation="h",
                    marker_color=_cores_s,
                    text=[f"{sc:.0f}" for sc in _scores_s],
                    textposition="inside",
                ))
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
            _n   = [s["nome"]    for s in _port_stats]
            _mam = [s["mam"]     for s in _port_stats]
            _car = [s["carrego"] for s in _port_stats]
            _cap = [s["capital"] for s in _port_stats]

            fig_cmp = go.Figure()
            fig_cmp.add_trace(go.Bar(name="Capital Investido", x=_n, y=_cap,
                                     marker_color="#90caf9"))
            fig_cmp.add_trace(go.Bar(name="MaM Hoje",          x=_n, y=_mam,
                                     marker_color="#ef9a9a"))
            fig_cmp.add_trace(go.Bar(name="Carrego Vencimento", x=_n, y=_car,
                                     marker_color="#a5d6a7"))
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
            _df_tab = pd.DataFrame([{
                "Título":       s["nome"],
                "Tipo":         s["tipo"],
                "Capital":      formatar_brl(s["capital"]),
                "Taxa (% a.a.)": f"{s['taxa']:.2f}%",
                "Prazo (anos)": s["anos"],
                "MaM Hoje":     formatar_brl(s["mam"]),
                "Var. %":       f"{s['var_pct']:+.1f}%",
                "Carrego":      formatar_brl(s["carrego"]),
                "Saúde":        f"{s['score']:.0f}/100",
            } for s in _port_stats])
            st.dataframe(_df_tab, hide_index=True, use_container_width=True)

    # =========================== ABA 4: UTILITÁRIOS ==========================
    with tab_util:
        # Custódia B3
        st.markdown("#### 🏦  Taxa de Custódia B3")
        descontar_custodia = st.checkbox(
            "Simular impacto da taxa de custódia B3 (0,20% a.a.)",
            value=False, key="dash_descontar_custodia",
        )
        if descontar_custodia:
            is_selic = "Selic" in titulo_sel or "Reserva" in titulo_sel
            if is_selic and valor_investido <= 10_000.0:
                st.success(
                    "**Isenção aplicada:** Tesouro Selic/Reserva até R$ 10.000 é isento (regra desde 2023).",
                    icon="✅",
                )
            else:
                custo_anual   = resultado["mam"] * 0.002
                custo_total   = resultado["mam"] * (1 - (1 - 0.002) ** anos_restantes)
                venc_ajustado = valor_vencimento * (1 - 0.002) ** anos_restantes
                reducao_pct   = (valor_vencimento - venc_ajustado) / valor_vencimento * 100
                st.info(
                    f"- Custo anual (sobre MaM atual): **{formatar_brl(custo_anual)}/ano**\n"
                    f"- Custo total estimado até {data_vencimento.strftime('%d/%m/%Y')}: "
                    f"**{formatar_brl(custo_total)}** ({reducao_pct:.1f}% do resgate bruto)\n"
                    f"- Resgate estimado após custódia: **{formatar_brl(venc_ajustado)}**",
                    icon="💰",
                )

        st.markdown("---")

        # Copiar análise
        st.markdown("#### 📋  Copiar Resumo da Análise")
        score_label = "Sereno" if score >= 70 else "Atenção" if score >= 40 else "Risco de Pânico"
        posicao_str = "ACIMA" if resultado["mam"] >= valor_investido else "ABAIXO"
        resumo = (
            f"📊 RESUMO DA POSIÇÃO — Renda Fixa CF\n"
            f"{'─' * 40}\n"
            f"Título: {titulo_sel}\n"
            f"Capital investido: {formatar_brl(valor_investido)}\n"
            f"Taxa contratada: {taxa_contratada_pct:.2f}% a.a. real\n"
            f"Data de compra: {data_compra.strftime('%d/%m/%Y')}\n"
            f"Vencimento: {data_vencimento.strftime('%d/%m/%Y')} ({anos_restantes} ano(s))\n"
            f"{'─' * 40}\n"
            f"MaM hoje: {formatar_brl(resultado['mam'])} ({posicao_str} do capital)\n"
            f"Se vender hoje: {formatar_brl(resultado['mam'])}\n"
            f"Se aguardar vencimento: {formatar_brl(valor_vencimento)}\n"
            f"Taxa de mercado atual: {taxa_mercado_pct:.2f}% a.a. real\n"
            f"{'─' * 40}\n"
            f"Saúde da Posição: {score:.0f}/100 — {score_label}\n"
            f"  • Prazo: {prazo_score:.0f}/60 pts | Posição: {posicao_score:.0f}/40 pts\n"
            f"{'─' * 40}\n"
            f"Gerado em {date.today().strftime('%d/%m/%Y')} via Renda Fixa CF"
        )
        st.code(resumo, language=None)
        st.caption("Selecione o texto acima e copie com Ctrl+C / Cmd+C.")

    # -----------------------------------------------------------------------
    # Persiste preferências
    # -----------------------------------------------------------------------
    salvar({
        "dash_descontar_custodia": st.session_state.get("dash_descontar_custodia", False),
        "dash_choque_stress":      st.session_state.get("dash_choque_stress", 2.0),
        "_portfolio":              st.session_state.get("_portfolio", []),
        "_analysis_pos_idx":       st.session_state.get("_analysis_pos_idx", 0),
    })
