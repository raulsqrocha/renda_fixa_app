"""
Aba "Utilitários" da Análise Detalhada do Dashboard — extraída de dashboard.py.

Custódia B3, resumo copiável da posição e exportação do portfólio em CSV.
"""

from datetime import date

import pandas as pd
import streamlit as st

from core.financas import formatar_brl


def renderizar(pos: dict, calc: dict, portfolio: list, calcs_port: list) -> None:
    _tipo_sel = pos.get("tipo_asset", "ipca_mais")
    titulo_sel = pos["titulo"]
    valor_investido = pos["valor"]
    taxa_contratada_pct = pos["taxa"]
    data_compra = calc["dc"]
    data_vencimento = calc["dv"]
    taxa_mercado_pct = calc["taxa_mkt_pct"]
    resultado = calc["res"]
    anos_restantes = calc["anos_res"]
    valor_vencimento = calc["vf"]
    prazo_score = calc["prazo_score"]
    posicao_score = calc["posicao_score"]
    score = calc["score"]

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
            c = calcs_port[i]
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
