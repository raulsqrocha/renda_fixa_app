"""
Módulo de visualizações — todos os gráficos Plotly do app.

Paleta de cores:
  Vermelho (#E53E3E) → alerta, volatilidade, MaM (Visão do Pânico)
  Verde   (#38A169) → segurança, carrego, vencimento (Visão da Resiliência)
  Azul    (#4299E1) → neutro, referência, DI Futuro
"""

import numpy as np
import plotly.graph_objects as go
import pandas as pd
from datetime import date

from core.financas import formatar_brl

# Paleta de cores
VERMELHO = "#E53E3E"
VERDE = "#38A169"
AZUL = "#4299E1"
LARANJA = "#DD6B20"
AMARELO = "#ECC94B"
FUNDO = "#0E1117"
FUNDO_SECUND = "#1C2331"
GRID = "#2D3748"
TEXTO = "#FAFAFA"
TEXTO_FRACO = "#718096"


def _layout_base(titulo: str, yaxis_prefix: str = "R$ ") -> dict:
    """Layout Plotly padrão para todos os gráficos do app."""
    return dict(
        title=dict(
            text=titulo,
            font=dict(size=15, color=TEXTO, family="Inter"),
            x=0,
            xanchor="left",
        ),
        paper_bgcolor=FUNDO,
        plot_bgcolor=FUNDO,
        font=dict(color=TEXTO, family="Inter"),
        xaxis=dict(gridcolor=GRID, linecolor=GRID, zeroline=False),
        yaxis=dict(
            gridcolor=GRID,
            linecolor=GRID,
            zeroline=False,
            tickprefix=yaxis_prefix,
            tickformat=",.0f",
        ),
        hovermode="x unified",
        separators=",.",
        legend=dict(
            bgcolor="rgba(0,0,0,0)", bordercolor=GRID, orientation="h", y=-0.18
        ),
        margin=dict(l=10, r=10, t=55, b=10),
    )


# ---------------------------------------------------------------------------
# Tela 1 — Gráfico do Paradoxo
# ---------------------------------------------------------------------------


def grafico_paradoxo(
    df: pd.DataFrame,
    data_compra: date | None = None,
    data_vencimento: date | None = None,
    datas_cupom: list | None = None,
) -> go.Figure:
    """
    Plota o paradoxo da renda fixa:
      - Linha vermelha tracejada → MaM (volatilidade percebida)
      - Linha verde sólida       → Carrego (segurança real até o vencimento)
    Timeline opcional: data_compra, data_vencimento, próximo cupom.
    """
    fig = go.Figure()

    # Área de preenchimento entre as curvas (zona de divergência percebida)
    fig.add_trace(
        go.Scatter(
            x=pd.concat([df["data"], df["data"][::-1]]),
            y=pd.concat([df["mam"], df["carrego"][::-1]]),
            fill="toself",
            fillcolor="rgba(229, 62, 62, 0.06)",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
        )
    )

    # Linha MaM — vermelha tracejada
    fig.add_trace(
        go.Scatter(
            x=df["data"],
            y=df["mam"],
            name="Marcação a Mercado (MaM)",
            line=dict(color=VERMELHO, dash="dash", width=2),
            hovertemplate="<b>MaM</b>: R$ %{y:,.2f}<br>%{x|%d/%m/%Y}<extra></extra>",
        )
    )

    # Linha Carrego — verde sólida
    fig.add_trace(
        go.Scatter(
            x=df["data"],
            y=df["carrego"],
            name="Carrego até o Vencimento",
            line=dict(color=VERDE, width=2.5),
            hovertemplate="<b>Carrego</b>: R$ %{y:,.2f}<br>%{x|%d/%m/%Y}<extra></extra>",
        )
    )

    # Anotação na zona de pânico (1/4 do caminho)
    idx_panico = len(df) // 4
    fig.add_annotation(
        x=df["data"].iloc[idx_panico],
        y=df["mam"].iloc[idx_panico] * 0.988,
        text="⚡ Zona de Pânico",
        font=dict(color=VERMELHO, size=11, family="Inter"),
        showarrow=False,
        bgcolor="rgba(229,62,62,0.12)",
        bordercolor=VERMELHO,
        borderwidth=1,
        borderpad=4,
    )

    # Anotação na linha de carrego (metade do caminho)
    idx_meio = len(df) // 2
    fig.add_annotation(
        x=df["data"].iloc[idx_meio],
        y=df["carrego"].iloc[idx_meio] * 1.01,
        text="🛡️ Blindagem do Capital",
        font=dict(color=VERDE, size=11, family="Inter"),
        showarrow=False,
        bgcolor="rgba(56,161,105,0.12)",
        bordercolor=VERDE,
        borderwidth=1,
        borderpad=4,
    )

    # Linha vertical "Dia de Hoje" — só renderiza se hoje estiver dentro do intervalo do gráfico
    hoje_ts = pd.Timestamp(date.today())
    if df["data"].min() <= hoje_ts <= df["data"].max():
        fig.add_shape(
            type="line",
            xref="x",
            yref="paper",
            x0=hoje_ts,
            x1=hoje_ts,
            y0=0,
            y1=1,
            line=dict(color=AMARELO, width=1.5, dash="dash"),
        )
        fig.add_annotation(
            x=hoje_ts,
            y=0.97,
            yref="paper",
            text="📍 Hoje",
            showarrow=False,
            font=dict(color=AMARELO, size=11, family="Inter"),
            bgcolor="rgba(236,201,75,0.10)",
            bordercolor=AMARELO,
            borderwidth=1,
            borderpad=4,
            xanchor="left",
            yanchor="top",
        )

    # ── Linha "Data de Compra" ──────────────────────────────────────────
    if data_compra is not None:
        compra_ts = pd.Timestamp(data_compra)
        if df["data"].min() <= compra_ts <= df["data"].max():
            fig.add_shape(
                type="line",
                xref="x",
                yref="paper",
                x0=compra_ts,
                x1=compra_ts,
                y0=0,
                y1=1,
                line=dict(color=AZUL, width=1.5, dash="dot"),
            )
            fig.add_annotation(
                x=compra_ts,
                y=0.12,
                yref="paper",
                text="📅 Compra",
                showarrow=False,
                font=dict(color=AZUL, size=10, family="Inter"),
                bgcolor="rgba(66,153,225,0.10)",
                bordercolor=AZUL,
                borderwidth=1,
                borderpad=4,
                xanchor="left",
                yanchor="bottom",
            )

    # ── Próximo cupom ───────────────────────────────────────────────────
    if datas_cupom:
        hoje_d = date.today()
        proximos = [d for d in datas_cupom if d > hoje_d]
        if proximos:
            prox_ts = pd.Timestamp(proximos[0])
            if df["data"].min() <= prox_ts <= df["data"].max():
                fig.add_shape(
                    type="line",
                    xref="x",
                    yref="paper",
                    x0=prox_ts,
                    x1=prox_ts,
                    y0=0,
                    y1=1,
                    line=dict(color=LARANJA, width=1, dash="dot"),
                )
                fig.add_annotation(
                    x=prox_ts,
                    y=0.27,
                    yref="paper",
                    text="💰 Cupom",
                    showarrow=False,
                    font=dict(color=LARANJA, size=10, family="Inter"),
                    bgcolor="rgba(221,107,32,0.10)",
                    bordercolor=LARANJA,
                    borderwidth=1,
                    borderpad=4,
                    xanchor="left",
                    yanchor="bottom",
                )

    # ── Anotação do vencimento ──────────────────────────────────────────
    if data_vencimento is not None:
        venc_ts = pd.Timestamp(data_vencimento)
        if venc_ts <= df["data"].max():
            fig.add_annotation(
                x=venc_ts,
                y=0.97,
                yref="paper",
                text="🏁 Vencimento",
                showarrow=False,
                font=dict(color=VERDE, size=10, family="Inter"),
                bgcolor="rgba(56,161,105,0.10)",
                bordercolor=VERDE,
                borderwidth=1,
                borderpad=4,
                xanchor="right",
                yanchor="top",
            )

    fig.update_layout(**_layout_base("O Paradoxo da Renda Fixa"))
    fig.update_layout(yaxis_title="Valor da Carteira (R$)", xaxis_title="")
    return fig


def grafico_score(score: float) -> go.Figure:
    """Gauge compacto do Índice de Serenidade do Investidor (0–100)."""
    if score >= 70:
        cor = VERDE
        label = "Sereno"
    elif score >= 40:
        cor = AMARELO
        label = "Atenção"
    else:
        cor = VERMELHO
        label = "Risco de Pânico"

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number",
            value=score,
            number={
                "suffix": " pts",
                "font": {"color": cor, "size": 26, "family": "Inter"},
            },
            title={
                "text": f"<b>{label}</b>",
                "font": {"color": TEXTO, "size": 13, "family": "Inter"},
            },
            gauge={
                "axis": {
                    "range": [0, 100],
                    "tickcolor": TEXTO_FRACO,
                    "tickfont": {"size": 9},
                    "nticks": 5,
                },
                "bar": {"color": cor, "thickness": 0.28},
                "bgcolor": FUNDO_SECUND,
                "borderwidth": 1,
                "bordercolor": GRID,
                "steps": [
                    {"range": [0, 40], "color": "rgba(229,62,62,0.15)"},
                    {"range": [40, 70], "color": "rgba(236,201,75,0.10)"},
                    {"range": [70, 100], "color": "rgba(56,161,105,0.12)"},
                ],
            },
        )
    )
    fig.update_layout(
        paper_bgcolor=FUNDO,
        font={"color": TEXTO, "family": "Inter"},
        height=210,
        margin=dict(l=15, r=15, t=40, b=5),
    )
    return fig


# ---------------------------------------------------------------------------
# Tela 2 — IPCA Histórico
# ---------------------------------------------------------------------------


def grafico_ipca_historico(df_ipca: pd.DataFrame) -> go.Figure:
    """
    Gráfico de barras com o IPCA acumulado anual.
    Barras coloridas por faixa:
      Verde  → IPCA < 5% (controlado)
      Laranja → IPCA 5%–8% (atenção)
      Vermelho → IPCA > 8% (crítico)
    """
    df = df_ipca.copy()
    df["ano"] = df["data"].dt.year
    df_anual = (
        df.groupby("ano")["valor"]
        .apply(lambda x: (np.prod(1 + x / 100) - 1) * 100)
        .reset_index(name="ipca_anual")
    )
    n_meses = df.groupby("ano")["valor"].count().rename("n_meses")
    df_anual = df_anual.join(n_meses, on="ano")

    cores = [
        VERMELHO if v >= 8 else LARANJA if v >= 5 else VERDE
        for v in df_anual["ipca_anual"]
    ]
    textos = [
        f"{v:.1f}%*" if n < 12 else f"{v:.1f}%"
        for v, n in zip(df_anual["ipca_anual"], df_anual["n_meses"])
    ]

    fig = go.Figure()
    fig.add_trace(
        go.Bar(
            x=df_anual["ano"],
            y=df_anual["ipca_anual"],
            marker_color=cores,
            text=textos,
            textposition="outside",
            textfont=dict(size=10),
            hovertemplate="<b>%{x}</b><br>IPCA: %{y:.2f}%<extra></extra>",
            name="IPCA Acumulado",
        )
    )

    anos_parciais = df_anual[df_anual["n_meses"] < 12]
    if not anos_parciais.empty:
        row = anos_parciais.iloc[-1]
        meses_nomes = [
            "Jan",
            "Fev",
            "Mar",
            "Abr",
            "Mai",
            "Jun",
            "Jul",
            "Ago",
            "Set",
            "Out",
            "Nov",
            "Dez",
        ]
        n = int(row["n_meses"])
        ate_mes = meses_nomes[n - 1] if n <= 12 else "Dez"
        fig.add_annotation(
            x=0.01,
            y=0.01,
            xref="paper",
            yref="paper",
            text=f"* Acumulado Jan–{ate_mes}/{int(row['ano'])} (parcial)",
            font=dict(size=9, color=TEXTO_FRACO),
            showarrow=False,
            align="left",
        )

    # Meta do Banco Central (3,0% para 2025 em diante)
    fig.add_hline(
        y=3.0,
        line_dash="dot",
        line_color="white",
        annotation_text="Meta BCB (3%)",
        annotation_position="top right",
        annotation_font_color="white",
        annotation_font_size=11,
    )

    # Marcos históricos
    marcos = {2015: "Crise fiscal<br>(10,67%)", 2021: "Ressurgência<br>pós-pandemia"}
    for ano, texto in marcos.items():
        linha = df_anual[df_anual["ano"] == ano]
        if not linha.empty:
            v = linha["ipca_anual"].values[0]
            fig.add_annotation(
                x=ano,
                y=v + 0.8,
                text=texto,
                font=dict(size=9, color=TEXTO_FRACO),
                showarrow=False,
                align="center",
            )

    fig.update_layout(
        **_layout_base("Retrospecto Histórico — IPCA Anual no Brasil", yaxis_prefix="")
    )
    fig.update_layout(
        yaxis=dict(ticksuffix="%", tickformat=".1f", title="IPCA Acumulado no Ano (%)"),
        xaxis_title="",
        showlegend=False,
    )
    return fig


# ---------------------------------------------------------------------------
# Tela 2 — Comparativo de Cenários
# ---------------------------------------------------------------------------


def grafico_cenarios(cenarios: dict, anos: int, valor_investido: float) -> go.Figure:
    """
    Gráfico duplo (barras + linha):
      - Barras: valor nominal final em cada cenário
      - Linha: ganho real acumulado (%) — idêntico em todos os cenários
               porque a taxa real é travada independente do IPCA
    """
    nomes = list(cenarios.keys())
    valores_nominais = [c["valor_final"] for c in cenarios.values()]
    ganhos_reais = [c["retorno_real_pct"] for c in cenarios.values()]

    cores_barra = []
    for nome in nomes:
        if "Estresse" in nome:
            cores_barra.append(VERMELHO)
        elif "Base" in nome:
            cores_barra.append(AZUL)
        else:
            cores_barra.append(VERDE)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Valor Nominal Final",
            x=nomes,
            y=valores_nominais,
            marker_color=cores_barra,
            text=[formatar_brl(v, 0) for v in valores_nominais],
            textposition="outside",
            hovertemplate="<b>%{x}</b><br>Valor Final: R$ %{y:,.2f}<extra></extra>",
            yaxis="y1",
        )
    )

    fig.add_trace(
        go.Scatter(
            name="Ganho Real Acumulado (%)",
            x=nomes,
            y=ganhos_reais,
            mode="markers+lines",
            yaxis="y2",
            marker=dict(color=TEXTO, size=12, symbol="diamond"),
            line=dict(color=TEXTO, dash="dot", width=2),
            hovertemplate="<b>Ganho Real</b>: %{y:.1f}%<extra></extra>",
        )
    )

    fig.add_hline(
        y=valor_investido,
        line_dash="dot",
        line_color=TEXTO_FRACO,
        annotation_text=f"Capital Inicial: {formatar_brl(valor_investido, 0)}",
        annotation_position="top left",
        annotation_font_color=TEXTO_FRACO,
        annotation_font_size=10,
    )

    fig.update_layout(**_layout_base(f"Projeção de Cenários — {anos} anos"))
    fig.update_layout(
        yaxis=dict(title="Valor Final (R$)", tickprefix="R$ ", tickformat=",.0f"),
        yaxis2=dict(
            title="Ganho Real Acumulado (%)",
            overlaying="y",
            side="right",
            ticksuffix="%",
            tickformat=".0f",
            showgrid=False,
        ),
    )
    return fig


# ---------------------------------------------------------------------------
# Tela 2 — Curva DI Futuro
# ---------------------------------------------------------------------------


def grafico_curva_di(dados_di: list) -> go.Figure:
    """
    Plota a curva de juros inserida manualmente pelo usuário (DI Futuro).
    """
    vencimentos = [d["vencimento"] for d in dados_di]
    taxas = [d["taxa"] for d in dados_di]

    fig = go.Figure()
    fig.add_trace(
        go.Scatter(
            x=vencimentos,
            y=taxas,
            mode="lines+markers+text",
            line=dict(color=AZUL, width=2.5),
            marker=dict(size=9, color=AZUL),
            text=[f"{t:.2f}%" for t in taxas],
            textposition="top center",
            textfont=dict(size=10),
            fill="tozeroy",
            fillcolor="rgba(66, 153, 225, 0.08)",
            hovertemplate="<b>DI %{x}</b><br>Taxa: %{y:.2f}% a.a.<extra></extra>",
            name="DI Futuro",
        )
    )

    fig.update_layout(
        **_layout_base("Curva de Juros Futuros — DI Futuro (B3)", yaxis_prefix="")
    )
    fig.update_layout(
        yaxis=dict(ticksuffix="%", tickformat=".2f", title="Taxa ao Ano (%)"),
        xaxis_title="Vencimento do Contrato",
    )
    return fig


# ---------------------------------------------------------------------------
# Tela 3 — Qual Tesouro é Melhor para Mim?
# ---------------------------------------------------------------------------

_TIPO_COR = {"selic": AZUL, "pre": LARANJA, "ipca_mais": VERDE}
_TIPO_NOME = {"selic": "Pós-Fixado (Selic)", "pre": "Pré-Fixado", "ipca_mais": "IPCA+"}

_CORES_ATIVO = [
    VERDE,
    AZUL,
    LARANJA,
    AMARELO,
    "#B794F4",
    "#F6AD55",
    "#68D391",
    "#63B3ED",
]


def _hex_to_rgb(hex_color: str) -> str:
    h = hex_color.lstrip("#")
    return ", ".join(str(int(h[i : i + 2], 16)) for i in (0, 2, 4))


def grafico_markowitz(
    analises: list, carteira_mix: dict | None = None, portfolios_mc: list | None = None
) -> go.Figure:
    """
    Fronteira de Markowitz educacional: Retorno Esperado vs. Risco de MaM.

    Cada ponto = um título. A fronteira eficiente teórica é desenhada como curva
    de referência — pontos acima/esquerda dela são mais eficientes.
    """
    fig = go.Figure()

    xs = [a["risco_std"] for a in analises]
    ys = [a["ret_neu"] for a in analises]

    # Nuvem Monte Carlo de portfólios aleatórios
    if portfolios_mc and len(portfolios_mc) > 2:
        xs_mc = [p["risco_std"] for p in portfolios_mc]
        ys_mc = [p["ret_neu"] for p in portfolios_mc]
        fig.add_trace(
            go.Scatter(
                x=xs_mc,
                y=ys_mc,
                mode="markers",
                marker=dict(size=4, color="rgba(255,255,255,0.10)", line=dict(width=0)),
                name="Portfólios possíveis",
                hoverinfo="skip",
                showlegend=True,
            )
        )

    # Fronteira eficiente teórica: parábola de (min_risco, min_ret) → (max_risco, max_ret)
    if len(xs) >= 2:
        x0, x1 = min(xs), max(xs)
        y0 = min(ys)
        y1 = max(ys)
        # Curva convexa via quadrática paramétrica
        ts = np.linspace(0, 1, 80)
        xf = x0 + (x1 - x0) * ts
        yf = y0 + (y1 - y0) * (ts**0.65)  # convexa — típica de Markowitz
        fig.add_trace(
            go.Scatter(
                x=xf,
                y=yf,
                mode="lines",
                line=dict(color="rgba(250,250,250,0.18)", dash="dot", width=2),
                name="Fronteira Eficiente (ref.)",
                hoverinfo="skip",
            )
        )
        # Região abaixo da fronteira (ineficiente)
        fig.add_trace(
            go.Scatter(
                x=np.concatenate([xf, xf[::-1]]),
                y=np.concatenate([yf, np.full(len(yf), y0 - 1)]),
                fill="toself",
                fillcolor="rgba(229,62,62,0.04)",
                line=dict(width=0),
                hoverinfo="skip",
                showlegend=False,
            )
        )

    # Pontos dos títulos agrupados por tipo (para legenda unificada)
    tipos_vistos: set = set()
    for a in analises:
        tipo = a["tipo"]
        nome_curto = a["nome"].replace("Tesouro ", "")
        cor = _TIPO_COR.get(tipo, AZUL)
        show_leg = tipo not in tipos_vistos
        tipos_vistos.add(tipo)

        fig.add_trace(
            go.Scatter(
                x=[a["risco_std"]],
                y=[a["ret_neu"]],
                mode="markers+text",
                marker=dict(size=14, color=cor, line=dict(color="white", width=1.5)),
                text=[nome_curto],
                textposition="top center",
                textfont=dict(size=9, color=TEXTO),
                name=_TIPO_NOME.get(tipo, tipo) if show_leg else None,
                legendgroup=tipo,
                showlegend=show_leg,
                hovertemplate=(
                    f"<b>{a['nome']}</b><br>"
                    f"Retorno esperado: %{{y:.2f}}% a.a.<br>"
                    f"Risco (dispersão): %{{x:.2f}}%<br>"
                    f"MaM: {a['risco_label']}<extra></extra>"
                ),
            )
        )

    # Ponto estrela ⭐ — Carteira Mista Otimizada (70/30)
    if carteira_mix:
        nome_p = carteira_mix["nome_principal"].replace("Tesouro ", "")
        nome_l = carteira_mix["nome_liquida"].replace("Tesouro ", "")
        wp_pct = int(carteira_mix["peso_principal"] * 100)
        wl_pct = int(carteira_mix["peso_liquida"] * 100)

        fig.add_trace(
            go.Scatter(
                x=[carteira_mix["risco_std"]],
                y=[carteira_mix["ret_neu"]],
                mode="markers+text",
                marker=dict(
                    size=20,
                    color=AMARELO,
                    symbol="star",
                    line=dict(color="white", width=1.5),
                ),
                text=["⭐ Mix"],
                textposition="top center",
                textfont=dict(size=10, color=AMARELO),
                name=f"Carteira Mista {wp_pct}/{wl_pct}",
                hovertemplate=(
                    f"<b>Carteira Mista {wp_pct}/{wl_pct}</b><br>"
                    f"{wp_pct}% {nome_p} + {wl_pct}% {nome_l}<br>"
                    f"Retorno neutro: %{{y:.2f}}% a.a.<br>"
                    f"Risco (σ): %{{x:.3f}}%"
                    f"<extra></extra>"
                ),
            )
        )

    fig.update_layout(
        **_layout_base(
            "Fronteira de Markowitz — Retorno vs. Risco de MaM", yaxis_prefix=""
        )
    )
    fig.update_layout(
        xaxis=dict(
            title="Risco de MaM — desvio dos cenários (%)",
            ticksuffix="%",
            tickformat=".2f",
            gridcolor=GRID,
        ),
        yaxis=dict(
            title="Retorno Esperado (% a.a.)",
            ticksuffix="%",
            tickformat=".2f",
            gridcolor=GRID,
            tickprefix="",
        ),
        separators=",.",
    )
    return fig


def grafico_cenarios_batalha(analises: list) -> go.Figure:
    """
    Barras agrupadas: três cenários (Adverso / Neutro / Favorável) por título.
    Expõe visualmente a amplitude de oscilação de cada instrumento.
    """
    nomes_curtos = [a["nome"].replace("Tesouro ", "") for a in analises]
    ret_adv = [a["ret_adv"] for a in analises]
    ret_neu = [a["ret_neu"] for a in analises]
    ret_fav = [a["ret_fav"] for a in analises]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="⚠️ Adverso (taxa +1 p.p.)",
            x=nomes_curtos,
            y=ret_adv,
            marker_color=VERMELHO,
            opacity=0.80,
            hovertemplate="<b>%{x}</b><br>Adverso: %{y:.2f}% a.a.<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="📊 Neutro (sem choque)",
            x=nomes_curtos,
            y=ret_neu,
            marker_color=AZUL,
            hovertemplate="<b>%{x}</b><br>Neutro: %{y:.2f}% a.a.<extra></extra>",
        )
    )
    fig.add_trace(
        go.Bar(
            name="✅ Favorável (taxa -1 p.p.)",
            x=nomes_curtos,
            y=ret_fav,
            marker_color=VERDE,
            opacity=0.85,
            hovertemplate="<b>%{x}</b><br>Favorável: %{y:.2f}% a.a.<extra></extra>",
        )
    )

    fig.update_layout(**_layout_base("Retorno por Cenário de Taxa", yaxis_prefix=""))
    fig.update_layout(
        barmode="group",
        yaxis=dict(
            title="Retorno Anualizado (% a.a.)",
            ticksuffix="%",
            tickformat=".1f",
            gridcolor=GRID,
            tickprefix="",
        ),
        xaxis_title="",
        separators=",.",
    )
    return fig


def grafico_retorno_por_horizonte(
    resultados_por_horizonte: dict, horizonte_atual: int
) -> go.Figure:
    """
    Linhas de retorno neutro por horizonte para cada título.
    Linha sólida = título ainda em carrego (antes do vencimento).
    Linha tracejada = título venceu, retorno inclui reinvestimento à Selic.
    """
    fig = go.Figure()
    horizons = sorted(resultados_por_horizonte.keys())
    if not horizons:
        return fig

    primeiros = resultados_por_horizonte[horizons[0]]
    tem_reinvest = False

    for idx, ref in enumerate(primeiros):
        nome = ref["nome"]
        cor = _CORES_ATIVO[idx % len(_CORES_ATIVO)]
        rgb = _hex_to_rgb(cor)
        nome_curto = nome.replace("Tesouro ", "")

        xs_m: list[float] = []
        ys_m: list[float] = []
        ys_adv, ys_fav = [], []
        xs_r, ys_r = [], []
        bridge_feito = False

        for h in horizons:
            a = next(
                (x for x in resultados_por_horizonte[h] if x["nome"] == nome), None
            )
            if not a:
                continue
            if a.get("reinvest"):
                tem_reinvest = True
                if not bridge_feito and xs_m:
                    xs_r.append(xs_m[-1])
                    ys_r.append(ys_m[-1])
                    bridge_feito = True
                xs_r.append(h)
                ys_r.append(a["ret_neu"])
            else:
                xs_m.append(h)
                ys_m.append(a["ret_neu"])
                ys_adv.append(a["ret_adv"])
                ys_fav.append(a["ret_fav"])

        # Banda adverso–favorável (apenas fase de carrego)
        if xs_m and ys_fav and ys_adv:
            fig.add_trace(
                go.Scatter(
                    x=xs_m + xs_m[::-1],
                    y=ys_fav + ys_adv[::-1],
                    fill="toself",
                    fillcolor=f"rgba({rgb}, 0.08)",
                    line=dict(width=0),
                    hoverinfo="skip",
                    showlegend=False,
                )
            )

        # Linha sólida — carrego normal
        if xs_m:
            fig.add_trace(
                go.Scatter(
                    x=xs_m,
                    y=ys_m,
                    name=nome_curto,
                    mode="lines+markers",
                    line=dict(color=cor, width=2.5, dash="solid"),
                    marker=dict(size=7, color=cor),
                    legendgroup=nome,
                    hovertemplate=(
                        f"<b>{nome_curto}</b><br>"
                        "Horizonte: %{x} anos<br>"
                        "Retorno neutro: %{y:.2f}% a.a.<extra></extra>"
                    ),
                )
            )

        # Linha tracejada — reinvestimento após vencimento
        if xs_r:
            fig.add_trace(
                go.Scatter(
                    x=xs_r,
                    y=ys_r,
                    name=nome_curto,
                    mode="lines",
                    line=dict(color=cor, width=1.5, dash="dot"),
                    legendgroup=nome,
                    showlegend=False,
                    hovertemplate=(
                        f"<b>{nome_curto}</b> (reinvest. Selic)<br>"
                        "Horizonte: %{x} anos<br>"
                        "Retorno: %{y:.2f}% a.a.<extra></extra>"
                    ),
                )
            )

    fig.add_vline(
        x=horizonte_atual,
        line_dash="dot",
        line_color=AMARELO,
        annotation_text=f"Seu horizonte ({horizonte_atual}a)",
        annotation_font_color=AMARELO,
        annotation_font_size=10,
        annotation_position="top right",
    )

    titulo = "Retorno por Horizonte de Saída"
    if tem_reinvest:
        titulo += "  ·  linha tracejada = reinvest. Selic após vencimento"

    fig.update_layout(**_layout_base(titulo, yaxis_prefix=""))
    fig.update_layout(
        xaxis=dict(title="Horizonte de saída (anos)", dtick=1, gridcolor=GRID),
        yaxis=dict(
            title="Retorno esperado (% a.a.)",
            ticksuffix="%",
            tickformat=".1f",
            tickprefix="",
            gridcolor=GRID,
        ),
        hovermode="x unified",
    )
    return fig
