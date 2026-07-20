"""
Aba "Simulações" da Análise Detalhada do Dashboard — extraída de dashboard.py.

Choque de taxa adverso/favorável, Calculadora de Aportes Mensais e o
comparador "Estou Pensando em Vender — Qual o Custo Real?".
"""

from datetime import date

import pandas as pd
import streamlit as st

from core.financas import (
    aliquota_ir_renda_fixa,
    formatar_brl,
    metricas_carteira,
)
from telas import _dashboard_calculadora


def renderizar(pos: dict, calc: dict, vna: float, df_titulos: pd.DataFrame) -> None:
    valor_investido = pos["valor"]
    taxa_contratada_pct = pos["taxa"]
    _tipo_sel = pos.get("tipo_asset", "ipca_mais")
    data_compra = calc["dc"]
    data_vencimento = calc["dv"]
    taxa_mercado_pct = calc["taxa_mkt_pct"]
    taxa_contratada = calc["tc"]
    taxa_mercado = calc["tm"]
    pu_compra = calc["pu_c"]
    cpns_hoje = calc["cpns_h"]
    resultado = calc["res"]
    anos_restantes = calc["anos_res"]
    valor_vencimento = calc["vf"]

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

    _dashboard_calculadora.renderizar(df_titulos, valor_investido)

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
    vf_bruto_b = mam_input * (1 + taxa_contratada) ** anos_venda * (_ipca_b**anos_venda)
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
