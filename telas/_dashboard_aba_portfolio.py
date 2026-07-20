"""
Aba "Portfólio" da Análise Detalhada do Dashboard — extraída de dashboard.py.

Visão estatística de toda a carteira: métricas ponderadas, alertas de
concentração, alocação por título/saúde, tabela consolidada por título e
choque de curva (estilo COPOM) sobre o portfólio inteiro.
"""

from datetime import date

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from core.financas import formatar_brl, metricas_carteira
from core.graficos import _aplicar_tema


def renderizar(portfolio: list, calcs_port: list, vna: float) -> None:
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
    for i, p in enumerate(calcs_port):
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
                "var_pct": (pos_p["mam_cache"] - pos_p["valor"]) / pos_p["valor"] * 100,
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
            _por_tipo_cap[s["tipo"]] = _por_tipo_cap.get(s["tipo"], 0.0) + s["capital"]

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
            _cores_pie = [_palette[i % len(_palette)] for i in range(len(_port_stats))]
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
            _aplicar_tema(fig_pie)
            fig_pie.update_layout(
                margin=dict(t=10, b=10, l=40, r=40),
                showlegend=False,
                height=260,
            )
            st.plotly_chart(fig_pie, width="stretch", theme=None)

        with col_g2:
            st.markdown("**Saúde por posição**")
            _nomes_s = [s["nome"] for s in _port_stats]
            _scores_s = [s["score"] for s in _port_stats]
            _cores_s = [_palette[i % len(_palette)] for i in range(len(_port_stats))]
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
            _aplicar_tema(fig_bar)
            fig_bar.update_layout(
                xaxis=dict(range=[0, 100], showgrid=False),
                yaxis=dict(autorange="reversed"),
                margin=dict(t=10, b=10, l=130, r=20),
                height=260,
            )
            st.plotly_chart(fig_bar, width="stretch", theme=None)

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
        fig_cmp.add_trace(go.Bar(name="MaM Hoje", x=_n, y=_mam, marker_color="#ef9a9a"))
        fig_cmp.add_trace(
            go.Bar(name="Carrego Vencimento", x=_n, y=_car, marker_color="#a5d6a7")
        )
        _aplicar_tema(fig_cmp)
        fig_cmp.update_layout(
            barmode="group",
            margin=dict(t=10, b=60, l=80, r=20),
            legend=dict(orientation="h", y=-0.2),
            height=300,
            yaxis=dict(tickprefix="R$ ", separatethousands=True),
        )
        st.plotly_chart(fig_cmp, width="stretch", theme=None)

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
        st.dataframe(_df_tab, hide_index=True, width="stretch")

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
            st.dataframe(pd.DataFrame(_rows_cons), hide_index=True, width="stretch")

        # ---- Choque de Curva — Portfólio Inteiro (estilo COPOM) ----
        st.markdown("---")
        st.markdown("**Choque de Curva — Portfólio Inteiro**")
        st.caption(
            "Simula uma alta/queda uniforme na taxa real sobre os títulos IPCA+/RendA+/"
            "Educar+ da carteira — os únicos com MaM sensível a taxa neste app. Selic, "
            "Prefixado, CDB, LCI e LCA são modelados por accrual (taxa contratada) nesta "
            "visão do Dashboard e não entram na simulação."
        )

        _posicoes_ipca = [
            (portfolio[i], calcs_port[i])
            for i in range(len(portfolio))
            if calcs_port[i] is not None and not calcs_port[i].get("is_simples")
        ]

        if not _posicoes_ipca:
            st.info(
                "Nenhum título IPCA+/RendA+/Educar+ na carteira para simular.", icon="ℹ️"
            )
        else:

            def _mam_a_taxa(pos: dict, calc: dict, taxa_mercado: float) -> float:
                res = metricas_carteira(
                    valor_investido=pos["valor"],
                    pu_na_compra=calc["pu_c"],
                    taxa_real_contratada=calc["tc"],
                    taxa_real_mercado=taxa_mercado,
                    vna=vna,
                    data_hoje=date.today(),
                    data_vencimento=calc["dv"],
                    datas_cupom=calc["cpns_h"],
                )
                return res["mam"]

            choque_copom = st.slider(
                "Magnitude do choque na taxa real (p.p.)",
                min_value=0.0,
                max_value=3.0,
                value=1.0,
                step=0.25,
                format="%.2f p.p.",
                key="port_choque_copom",
            )

            _mam_hoje = sum(p["mam_cache"] for p, _ in _posicoes_ipca)
            _mam_adv = sum(
                _mam_a_taxa(p, c, max(0.001, c["tm"] + choque_copom / 100))
                for p, c in _posicoes_ipca
            )
            _mam_fav = sum(
                _mam_a_taxa(p, c, max(0.001, c["tm"] - choque_copom / 100))
                for p, c in _posicoes_ipca
            )
            _delta_adv = _mam_adv - _mam_hoje
            _delta_fav = _mam_fav - _mam_hoje

            cc1, cc2, cc3 = st.columns(3)
            with cc1:
                st.metric(
                    f"Hoje ({len(_posicoes_ipca)} posição(ões) IPCA+)",
                    formatar_brl(_mam_hoje),
                )
            with cc2:
                st.metric(
                    f"Se subir {choque_copom:.2f} p.p.",
                    formatar_brl(_mam_adv),
                    formatar_brl(_delta_adv),
                    delta_color="inverse",
                )
            with cc3:
                st.metric(
                    f"Se cair {choque_copom:.2f} p.p.",
                    formatar_brl(_mam_fav),
                    formatar_brl(_delta_fav),
                    delta_color="normal",
                )

            _pct_adv = (_delta_adv / _mam_hoje * 100) if _mam_hoje > 0 else 0.0
            st.caption(
                f"Um choque de +{choque_copom:.2f} p.p. na taxa real reduziria o valor de "
                f"resgate hoje em {formatar_brl(abs(_delta_adv))} ({abs(_pct_adv):.1f}%) — "
                "sem afetar o que você recebe se aguardar o vencimento de cada título."
            )
