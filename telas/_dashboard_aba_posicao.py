"""
Aba "Posição" da Análise Detalhada do Dashboard — extraída de dashboard.py.

Mostra o estado atual da posição selecionada: vista simplificada (Selic,
Pré-Fixado, CDB, LCI, LCA) ou vista completa com o Gráfico do Paradoxo
(Tesouro IPCA+/RendA+/Educar+).
"""

import calendar as _cal
from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.dados import buscar_historico_titulos_tesouro, historico_titulo
from core.financas import (
    aliquota_iof_renda_fixa,
    formatar_brl,
    metricas_carteira,
    pu_ntnb,
    serie_paradoxo,
)
from core.graficos import _aplicar_tema, grafico_paradoxo, grafico_score


@st.cache_data(ttl=3600 * 6, show_spinner=False)
def _serie_cached(
    vna, taxa_contratada, taxa_mercado, compra, vencimento, qtd, tem_cupom
):
    return serie_paradoxo(
        vna, taxa_contratada, taxa_mercado, compra, vencimento, qtd, tem_cupom
    )


def _mam_real(titulo: str, data_compra: date, quantidade: float) -> pd.DataFrame:
    """
    MaM real observada (Tesouro Transparente) para `titulo` entre a compra e
    hoje. Retorna DataFrame vazio se não houver histórico disponível — o
    Tesouro Direto adiciona/descontinua títulos ao longo do tempo, então nem
    toda posição tem dado real cobrindo todo o período desde a compra.
    """
    df_hist = buscar_historico_titulos_tesouro()
    df_titulo = historico_titulo(df_hist, titulo, data_compra, date.today())
    if df_titulo.empty:
        return df_titulo
    return pd.DataFrame(
        {
            "data": df_titulo["data"],
            "mam": quantidade * df_titulo["pu_compra"],
        }
    )


def renderizar(pos: dict, calc: dict, vna: float) -> None:
    titulo_sel = pos["titulo"]
    valor_investido = pos["valor"]
    taxa_contratada_pct = pos["taxa"]
    _tipo_sel = pos.get("tipo_asset", "ipca_mais")
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
            _aplicar_tema(fig_proj)
            fig_proj.update_layout(
                margin=dict(t=10, b=65, l=75, r=10),
                yaxis=dict(
                    tickprefix="R$ ",
                    separatethousands=True,
                    range=[valor_investido - _y_pad, max(_meses_y) + _y_pad],
                    gridcolor="rgba(255,255,255,0.06)",
                ),
                xaxis=dict(gridcolor="rgba(255,255,255,0.04)", tickangle=-30),
                legend=dict(orientation="h", y=-0.20, x=0),
                height=290,
            )
            st.plotly_chart(fig_proj, width="stretch", theme=None)
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
            st.plotly_chart(grafico_score(score), width="stretch", theme=None)

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
            st.plotly_chart(grafico_score(score), width="stretch", theme=None)

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
            df_mam_real = _mam_real(titulo_sel, data_compra, resultado["quantidade"])

        with col_graf:
            st.plotly_chart(
                grafico_paradoxo(
                    df_paradoxo,
                    data_compra=data_compra,
                    data_vencimento=data_vencimento,
                    datas_cupom=cpns_hoje if tem_cupom else None,
                    df_historico_real=df_mam_real,
                ),
                width="stretch",
                theme=None,
            )
            if not df_mam_real.empty:
                _desde = df_mam_real["data"].min().strftime("%d/%m/%Y")
                st.caption(
                    f"📡 Linha branca: MaM **real** observada no Tesouro Transparente, "
                    f"disponível desde {_desde}. Antes disso e após hoje, a linha vermelha "
                    "é uma projeção ilustrativa (o Tesouro Direto adiciona e descontinua "
                    "títulos ao longo do tempo, então nem todo período tem dado real)."
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
