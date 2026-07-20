"""
Calculadora de Aportes Mensais — extraída de dashboard.py para reduzir o
tamanho do módulo principal. Usada na tela vazia do Dashboard e na aba
"Simulações" da Análise Detalhada.
"""

from typing import cast

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.financas import aliquota_ir_renda_fixa, formatar_brl, fv_mensal, pmt_para_meta
from core.graficos import _aplicar_tema


def renderizar(df_titulos: pd.DataFrame, default_cap: float) -> None:
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
            _sl_live = df_titulos[df_titulos["nome"].str.contains("Selic", na=False)]
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
        st.dataframe(_dc_df_p, hide_index=True, width="stretch")

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
        _aplicar_tema(_dc_fig_p)
        _dc_fig_p.update_layout(
            yaxis=dict(
                title=dict(text="Valor Final (R$)", standoff=12),
                gridcolor="rgba(255,255,255,0.06)",
                tickprefix="R$ ",
                tickformat=",.0f",
            ),
            xaxis=dict(title="Anos", gridcolor="rgba(255,255,255,0.04)"),
            legend=dict(bgcolor="rgba(0,0,0,0)", orientation="h", y=-0.18),
            margin=dict(t=10, b=60, l=75, r=20),
            height=320,
        )
        st.plotly_chart(_dc_fig_p, width="stretch", theme=None)

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
        st.dataframe(_dc_df_r, hide_index=True, width="stretch")

        if _dc_rows_r:
            _dc_best = _dc_rows_r[0]
            _dc_worst = _dc_rows_r[-1]
            _dc_diff = cast(float, _dc_worst["_pmt"]) - cast(float, _dc_best["_pmt"])
            _dc_juros = _dc_meta - (_dc_cap_r + cast(float, _dc_best["_pmt"]) * _dc_n_r)
            st.info(
                f"**{_dc_best['Produto']}** exige o menor aporte: "
                f"**{formatar_brl(cast(float, _dc_best['_pmt']))}/mês** para atingir "
                f"{formatar_brl(_dc_meta)} em {_dc_prazo_r} ano(s).\n\n"
                f"Você economiza **{formatar_brl(_dc_diff)}/mês** vs. "
                f"**{_dc_worst['Produto']}** ({formatar_brl(cast(float, _dc_worst['_pmt']))}/ mês). "
                f"Os juros cobrem **{formatar_brl(_dc_juros)}** do seu objetivo.",
                icon="💡",
            )
