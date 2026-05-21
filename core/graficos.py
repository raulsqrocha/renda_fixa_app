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

# Paleta de cores
VERMELHO      = "#E53E3E"
VERDE         = "#38A169"
AZUL          = "#4299E1"
LARANJA       = "#DD6B20"
FUNDO         = "#0E1117"
FUNDO_SECUND  = "#1C2331"
GRID          = "#2D3748"
TEXTO         = "#FAFAFA"
TEXTO_FRACO   = "#718096"


def _layout_base(titulo: str, yaxis_prefix: str = "R$ ") -> dict:
    """Layout Plotly padrão para todos os gráficos do app."""
    return dict(
        title=dict(text=titulo, font=dict(size=15, color=TEXTO, family="Inter"), x=0, xanchor="left"),
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
        legend=dict(bgcolor="rgba(0,0,0,0)", bordercolor=GRID, orientation="h", y=-0.15),
        margin=dict(l=10, r=10, t=55, b=10),
    )


# ---------------------------------------------------------------------------
# Tela 1 — Gráfico do Paradoxo
# ---------------------------------------------------------------------------

def grafico_paradoxo(df: pd.DataFrame) -> go.Figure:
    """
    Plota o paradoxo da renda fixa:
      - Linha vermelha tracejada → MaM (volatilidade percebida)
      - Linha verde sólida       → Carrego (segurança real até o vencimento)
    """
    fig = go.Figure()

    # Área de preenchimento entre as curvas (zona de divergência percebida)
    fig.add_trace(go.Scatter(
        x=pd.concat([df["data"], df["data"][::-1]]),
        y=pd.concat([df["mam"], df["carrego"][::-1]]),
        fill="toself",
        fillcolor="rgba(229, 62, 62, 0.06)",
        line=dict(width=0),
        hoverinfo="skip",
        showlegend=False,
    ))

    # Linha MaM — vermelha tracejada
    fig.add_trace(go.Scatter(
        x=df["data"],
        y=df["mam"],
        name="Marcação a Mercado (MaM)",
        line=dict(color=VERMELHO, dash="dash", width=2),
        hovertemplate="<b>MaM</b>: R$ %{y:,.2f}<br>%{x|%d/%m/%Y}<extra></extra>",
    ))

    # Linha Carrego — verde sólida
    fig.add_trace(go.Scatter(
        x=df["data"],
        y=df["carrego"],
        name="Carrego até o Vencimento",
        line=dict(color=VERDE, width=2.5),
        hovertemplate="<b>Carrego</b>: R$ %{y:,.2f}<br>%{x|%d/%m/%Y}<extra></extra>",
    ))

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

    fig.update_layout(**_layout_base("O Paradoxo da Renda Fixa"))
    fig.update_layout(yaxis_title="Valor da Carteira (R$)", xaxis_title="")
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

    cores = [
        VERMELHO if v >= 8 else LARANJA if v >= 5 else VERDE
        for v in df_anual["ipca_anual"]
    ]

    fig = go.Figure()
    fig.add_trace(go.Bar(
        x=df_anual["ano"],
        y=df_anual["ipca_anual"],
        marker_color=cores,
        text=[f"{v:.1f}%" for v in df_anual["ipca_anual"]],
        textposition="outside",
        textfont=dict(size=10),
        hovertemplate="<b>%{x}</b><br>IPCA: %{y:.2f}%<extra></extra>",
        name="IPCA Acumulado",
    ))

    # Meta do Banco Central (3,0% para 2025 em diante)
    fig.add_hline(
        y=3.0, line_dash="dot", line_color="white",
        annotation_text="Meta BCB (3%)",
        annotation_position="top right",
        annotation_font_color="white",
        annotation_font_size=11,
    )

    # Marcos históricos
    marcos = {2015: "Crise fiscal\n(10,67%)", 2021: "Ressurgência\npós-pandemia"}
    for ano, texto in marcos.items():
        linha = df_anual[df_anual["ano"] == ano]
        if not linha.empty:
            v = linha["ipca_anual"].values[0]
            fig.add_annotation(
                x=ano, y=v + 0.8,
                text=texto,
                font=dict(size=9, color=TEXTO_FRACO),
                showarrow=False,
                align="center",
            )

    fig.update_layout(**_layout_base("Retrospecto Histórico — IPCA Anual no Brasil", yaxis_prefix=""))
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
    nomes            = list(cenarios.keys())
    valores_nominais = [c["valor_final"]       for c in cenarios.values()]
    ganhos_reais     = [c["retorno_real_pct"]  for c in cenarios.values()]

    cores_barra = []
    for nome in nomes:
        if "Estresse" in nome:
            cores_barra.append(VERMELHO)
        elif "Base" in nome:
            cores_barra.append(AZUL)
        else:
            cores_barra.append(VERDE)

    fig = go.Figure()

    fig.add_trace(go.Bar(
        name="Valor Nominal Final",
        x=nomes,
        y=valores_nominais,
        marker_color=cores_barra,
        text=[f"R$ {v:,.0f}" for v in valores_nominais],
        textposition="outside",
        hovertemplate="<b>%{x}</b><br>Valor Final: R$ %{y:,.2f}<extra></extra>",
        yaxis="y1",
    ))

    fig.add_trace(go.Scatter(
        name="Ganho Real Acumulado (%)",
        x=nomes,
        y=ganhos_reais,
        mode="markers+lines",
        yaxis="y2",
        marker=dict(color=TEXTO, size=12, symbol="diamond"),
        line=dict(color=TEXTO, dash="dot", width=2),
        hovertemplate="<b>Ganho Real</b>: %{y:.1f}%<extra></extra>",
    ))

    fig.add_hline(
        y=valor_investido, line_dash="dot", line_color=TEXTO_FRACO,
        annotation_text=f"Capital Inicial: R$ {valor_investido:,.0f}",
        annotation_position="top left",
        annotation_font_color=TEXTO_FRACO,
        annotation_font_size=10,
    )

    fig.update_layout(**_layout_base(f"Projeção de Cenários — {anos} anos"))
    fig.update_layout(
        yaxis=dict(title="Valor Final (R$)", tickprefix="R$ ", tickformat=",.0f"),
        yaxis2=dict(
            title="Ganho Real Acumulado (%)",
            overlaying="y", side="right",
            ticksuffix="%", tickformat=".0f", showgrid=False,
        ),
        legend=dict(orientation="h", y=-0.2),
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
    taxas       = [d["taxa"]       for d in dados_di]

    fig = go.Figure()
    fig.add_trace(go.Scatter(
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
    ))

    fig.update_layout(**_layout_base("Curva de Juros Futuros — DI Futuro (B3)", yaxis_prefix=""))
    fig.update_layout(
        yaxis=dict(ticksuffix="%", tickformat=".2f", title="Taxa ao Ano (%)"),
        xaxis_title="Vencimento do Contrato",
    )
    return fig
