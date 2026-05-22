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

from core.financas import formatar_brl

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
        separators=",.",
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
        text=[formatar_brl(v, 0) for v in valores_nominais],
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


# ---------------------------------------------------------------------------
# Tela 3 — Batalha de Cenários
# ---------------------------------------------------------------------------

# ---------------------------------------------------------------------------
# Tela 3 — Qual Tesouro é Melhor para Mim?
# ---------------------------------------------------------------------------

_TIPO_COR = {"selic": AZUL, "pre": LARANJA, "ipca_mais": VERDE}
_TIPO_NOME = {"selic": "Pós-Fixado (Selic)", "pre": "Pré-Fixado", "ipca_mais": "IPCA+"}


def grafico_markowitz(analises: list) -> go.Figure:
    """
    Fronteira de Markowitz educacional: Retorno Esperado vs. Risco de MaM.

    Cada ponto = um título. A fronteira eficiente teórica é desenhada como curva
    de referência — pontos acima/esquerda dela são mais eficientes.
    """
    fig = go.Figure()

    xs = [a["risco_std"] for a in analises]
    ys = [a["ret_neu"]   for a in analises]

    # Fronteira eficiente teórica: parábola de (min_risco, min_ret) → (max_risco, max_ret)
    if len(xs) >= 2:
        x0, x1 = min(xs), max(xs)
        y0 = min(ys)
        y1 = max(ys)
        # Curva convexa via quadrática paramétrica
        ts = np.linspace(0, 1, 80)
        xf = x0 + (x1 - x0) * ts
        yf = y0 + (y1 - y0) * (ts ** 0.65)  # convexa — típica de Markowitz
        fig.add_trace(go.Scatter(
            x=xf, y=yf,
            mode="lines",
            line=dict(color="rgba(250,250,250,0.18)", dash="dot", width=2),
            name="Fronteira Eficiente (ref.)",
            hoverinfo="skip",
        ))
        # Região abaixo da fronteira (ineficiente)
        fig.add_trace(go.Scatter(
            x=np.concatenate([xf, xf[::-1]]),
            y=np.concatenate([yf, np.full(len(yf), y0 - 1)]),
            fill="toself",
            fillcolor="rgba(229,62,62,0.04)",
            line=dict(width=0),
            hoverinfo="skip",
            showlegend=False,
        ))

    # Pontos dos títulos agrupados por tipo (para legenda unificada)
    tipos_vistos: set = set()
    for a in analises:
        tipo = a["tipo"]
        nome_curto = a["nome"].replace("Tesouro ", "")
        cor = _TIPO_COR[tipo]
        show_leg = tipo not in tipos_vistos
        tipos_vistos.add(tipo)

        fig.add_trace(go.Scatter(
            x=[a["risco_std"]],
            y=[a["ret_neu"]],
            mode="markers+text",
            marker=dict(size=14, color=cor, line=dict(color="white", width=1.5)),
            text=[nome_curto],
            textposition="top center",
            textfont=dict(size=9, color=TEXTO),
            name=_TIPO_NOME[tipo] if show_leg else None,
            legendgroup=tipo,
            showlegend=show_leg,
            hovertemplate=(
                f"<b>{a['nome']}</b><br>"
                f"Retorno esperado: %{{y:.2f}}% a.a.<br>"
                f"Risco (dispersão): %{{x:.2f}}%<br>"
                f"MaM: {a['risco_label']}<extra></extra>"
            ),
        ))

    fig.update_layout(**_layout_base("Fronteira de Markowitz — Retorno vs. Risco de MaM", yaxis_prefix=""))
    fig.update_layout(
        xaxis=dict(title="Risco de MaM — desvio dos cenários (%)", ticksuffix="%",
                   tickformat=".2f", gridcolor=GRID),
        yaxis=dict(title="Retorno Esperado (% a.a.)", ticksuffix="%",
                   tickformat=".2f", gridcolor=GRID, tickprefix=""),
        legend=dict(orientation="h", y=-0.22),
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

    fig.add_trace(go.Bar(
        name="⚠️ Adverso (taxa +1 p.p.)",
        x=nomes_curtos, y=ret_adv,
        marker_color=VERMELHO, opacity=0.80,
        hovertemplate="<b>%{x}</b><br>Adverso: %{y:.2f}% a.a.<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="📊 Neutro (sem choque)",
        x=nomes_curtos, y=ret_neu,
        marker_color=AZUL,
        hovertemplate="<b>%{x}</b><br>Neutro: %{y:.2f}% a.a.<extra></extra>",
    ))
    fig.add_trace(go.Bar(
        name="✅ Favorável (taxa -1 p.p.)",
        x=nomes_curtos, y=ret_fav,
        marker_color=VERDE, opacity=0.85,
        hovertemplate="<b>%{x}</b><br>Favorável: %{y:.2f}% a.a.<extra></extra>",
    ))

    fig.update_layout(**_layout_base("Retorno por Cenário de Taxa", yaxis_prefix=""))
    fig.update_layout(
        barmode="group",
        yaxis=dict(title="Retorno Anualizado (% a.a.)", ticksuffix="%",
                   tickformat=".1f", gridcolor=GRID, tickprefix=""),
        xaxis_title="",
        legend=dict(orientation="h", y=-0.22),
        separators=",.",
    )
    return fig


# ---------------------------------------------------------------------------
# Tela 3 — Batalha de Cenários (versão antiga — mantida para compatibilidade)
# ---------------------------------------------------------------------------

_CORES_BATALHA = {
    "selic":     AZUL,
    "pre":       LARANJA,
    "ipca_mais": VERDE,
}

_NOMES_BATALHA = {
    "selic":     "💰 Tesouro Selic (Pós)",
    "pre":       "📌 Tesouro Prefixado (Pré)",
    "ipca_mais": "🛡️ Tesouro IPCA+ (Híbrido)",
}

_CHAVES_BATALHA = ["selic", "pre", "ipca_mais"]


def grafico_batalha_barras(resultados: dict, capital: float) -> go.Figure:
    """
    Barras verticais comparando o valor final acumulado dos três instrumentos.
    A barra vencedora recebe opacidade total; as demais ficam suavizadas.
    """
    valores = [resultados[k]["valor_final"] for k in _CHAVES_BATALHA]
    vencedor = _CHAVES_BATALHA[valores.index(max(valores))]

    fig = go.Figure()
    for k in _CHAVES_BATALHA:
        vf = resultados[k]["valor_final"]
        fig.add_trace(go.Bar(
            name=_NOMES_BATALHA[k],
            x=[_NOMES_BATALHA[k]],
            y=[vf],
            marker=dict(color=_CORES_BATALHA[k], opacity=1.0 if k == vencedor else 0.45),
            showlegend=False,
            text=[formatar_brl(vf)],
            textposition="outside",
            textfont=dict(size=12, color=TEXTO),
            hovertemplate=(
                f"<b>{_NOMES_BATALHA[k]}</b>"
                "<br>Valor Final: R$ %{y:,.2f}<extra></extra>"
            ),
        ))

    fig.add_hline(
        y=capital, line_dash="dot", line_color=TEXTO_FRACO,
        annotation_text=f"Capital Inicial: {formatar_brl(capital, 0)}",
        annotation_position="top left",
        annotation_font_color=TEXTO_FRACO,
        annotation_font_size=10,
    )

    fig.update_layout(**_layout_base("Valor Final Acumulado por Instrumento"))
    fig.update_layout(
        showlegend=False,
        yaxis=dict(title="Valor Acumulado (R$)", tickprefix="R$ ", tickformat=",.0f"),
        xaxis_title="",
        bargap=0.4,
    )
    return fig


def grafico_batalha_trajetoria(df) -> go.Figure:
    """
    Linhas anuais mostrando a trajetória de crescimento de cada instrumento.
    Revela como a vantagem se acumula (ou inverte) ao longo do tempo.
    """
    configs = [
        ("selic",     "solid"),
        ("pre",       "dash"),
        ("ipca_mais", "dot"),
    ]

    fig = go.Figure()
    for k, dash in configs:
        fig.add_trace(go.Scatter(
            x=df["ano"],
            y=df[k],
            name=_NOMES_BATALHA[k],
            mode="lines+markers",
            line=dict(color=_CORES_BATALHA[k], width=2.5, dash=dash),
            marker=dict(size=6),
            hovertemplate=(
                f"<b>{_NOMES_BATALHA[k]}</b>"
                "<br>Ano %{x}: R$ %{y:,.2f}<extra></extra>"
            ),
        ))

    fig.update_layout(**_layout_base("Trajetória Anual dos Investimentos"))
    fig.update_layout(
        yaxis=dict(title="Valor Acumulado (R$)", tickprefix="R$ ", tickformat=",.0f"),
        xaxis=dict(title="Ano", tickmode="linear", dtick=1, gridcolor=GRID),
        legend=dict(orientation="h", y=-0.22),
    )
    return fig
