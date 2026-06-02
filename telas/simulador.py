"""
Tela 2 — Simulador Avançado

Seções:
  1. Simulador de Cenários de Inflação — ganho real travado vs. valor nominal
  2. Simulador de MaM — retorno de venda antecipada por cenário e prazo
  3. DI Futuro — curva de juros inserida manualmente
  4. Retrospecto Histórico — IPCA mensal e anual (BCB)
"""

import streamlit as st
import pandas as pd
from datetime import date

from core.financas import retorno_cenario_ipca, retorno_mam_antecipado, formatar_brl
from core.dados import (
    obter_dados_completos,
    CATEGORIAS_TITULOS,
    TITULOS_CONFIG,
    timestamp_ultima_atualizacao,
    chave_cache_mercado,
)
from core.graficos import (
    grafico_ipca_historico,
    grafico_cenarios,
    grafico_curva_di,
)
from core.persistencia import carregar, salvar, inicializar_session

# Nomes dos cenários do simulador de MaM — do mais adverso ao mais favorável
_NOMES_CENARIOS = [
    "Péssimo",
    "Muito Desfavorável",
    "Desfavorável",
    "Neutro",
    "Moderado",
    "Favorável",
    "Muito Favorável",
    "Excelente",
    "Excepcional",
]

# Valores padrão inspirados na metodologia de análise de MaM
_CENARIOS_PADRAO = pd.DataFrame(
    {
        "Cenário": _NOMES_CENARIOS,
        "IPCA Futuro (%)": [9.0, 8.5, 6.5, 5.5, 5.0, 5.0, 5.0, 5.0, 5.0],
        "Taxa IPCA+ (%)": [9.0, 8.5, 8.0, 7.5, 7.0, 6.0, 5.0, 4.0, 3.0],
    }
)


def _cor_retorno(val: str) -> str:
    """Paleta de cores para as células da tabela de MaM."""
    try:
        v = float(str(val).replace("+", "").replace("%", "").replace(",", "."))
        if v < 0:
            return "background-color: #2d1515; color: #fc8181"
        if v < 30:
            return "background-color: #2d2a10; color: #f6e05e"
        if v < 100:
            return "background-color: #15291a; color: #68d391"
        return "background-color: #0e1f3a; color: #90cdf4"
    except Exception:
        return ""


def render():
    """Tela 3 — Simulador Avançado: cenários de IPCA, matriz MaM, curva DI e retrospecto histórico."""
    st.session_state["_page_id"] = "simulador"

    # Carrega preferências salvas antes de qualquer widget
    _prefs = carregar()
    inicializar_session(_prefs)

    # Garante que o título salvo é válido para a categoria salva
    _cat = st.session_state.get("sim_categoria")
    if _cat and _cat in CATEGORIAS_TITULOS:
        _titulos_validos = CATEGORIAS_TITULOS[_cat]
        if st.session_state.get("sim_titulo") not in _titulos_validos:
            st.session_state["sim_titulo"] = _titulos_validos[0]
    elif _cat and _cat not in CATEGORIAS_TITULOS:
        st.session_state.pop("sim_categoria", None)
        st.session_state.pop("sim_titulo", None)

    # -----------------------------------------------------------------------
    # Cabeçalho
    # -----------------------------------------------------------------------
    st.markdown(
        '<p class="titulo-principal">Simulador Avançado</p>'
        '<p class="subtitulo">Cenários de inflação, estratégias de MaM, curva DI Futuro '
        "e retrospecto histórico do IPCA no Brasil.</p>",
        unsafe_allow_html=True,
    )

    with st.spinner("Carregando dados..."):
        df_ipca, df_titulos, vna = obter_dados_completos()

    _ts = timestamp_ultima_atualizacao(chave_cache_mercado())
    if not df_titulos.empty:
        st.caption(
            f"✅ Dados ao vivo · carregados às **{_ts.strftime('%H:%M')}** (atualiza a cada 2h)"
        )
    else:
        st.caption("⚠️ Modo offline — usando dados de referência")

    st.divider()

    # -----------------------------------------------------------------------
    # Seletor duplo: Categoria → Título
    # -----------------------------------------------------------------------
    st.subheader(":material/search:  Selecione o Título")

    # Linha 1 — Seleção do título (inputs categóricos)
    col_cat, col_venc = st.columns([1, 2])

    with col_cat:
        categoria_sel = st.selectbox(
            "Categoria",
            options=list(CATEGORIAS_TITULOS.keys()),
            help="Selecione a família do título Tesouro",
            key="sim_categoria",
        )

    with col_venc:
        titulo = st.selectbox(
            "Vencimento",
            options=CATEGORIAS_TITULOS[categoria_sel],
            help="Selecione o ano de vencimento",
            key="sim_titulo",
        )

    # Resolve dados do título antes da Row 2 para exibir métricas no mesmo grid
    linha = (
        df_titulos[df_titulos["nome"] == titulo]
        if not df_titulos.empty
        else pd.DataFrame()
    )

    if not linha.empty:
        taxa_atual_pct = float(linha["taxa_compra"].values[0])
        data_vencimento = date.fromisoformat(str(linha["vencimento"].values[0])[:10])
    else:
        cfg_titulo = TITULOS_CONFIG.get(titulo, {})
        taxa_atual_pct = 7.50
        data_vencimento = cfg_titulo.get("vencimento", date(2035, 5, 15))

    anos_restantes = max(1, round((data_vencimento - date.today()).days / 365))

    # Linha 2 — Capital e métricas do título selecionado
    col_val, col_taxa_m, col_prazo = st.columns([1.8, 1, 1])

    with col_val:
        valor_sim = st.number_input(
            "Capital a Simular (R$)",
            min_value=100.0,
            max_value=500_000.0,
            value=10_000.0,
            step=500.0,
            format="%.2f",
            key="sim_valor",
        )

    with col_taxa_m:
        st.metric("Taxa Real de Mercado", f"{taxa_atual_pct:.2f}% a.a.")

    with col_prazo:
        st.metric("Prazo até Vencimento", f"{anos_restantes} anos")

    st.divider()

    # -----------------------------------------------------------------------
    # 1. Simulador de Cenários de Inflação
    # -----------------------------------------------------------------------
    st.subheader(":material/thermostat:  Simulador de Cenários de Inflação")

    col_s1, col_s2 = st.columns([1, 1])

    with col_s1:
        ipca_baixo = st.slider(
            "Inflação Baixa (IPCA % a.a.)",
            min_value=1.0,
            max_value=5.0,
            value=3.0,
            step=0.1,
            format="%.1f%%",
            help="Cenário otimista — inflação próxima ou abaixo da meta do BCB",
            key="sim_ipca_baixo",
        )
        ipca_base = st.slider(
            "Cenário Base (IPCA % a.a.)",
            min_value=3.0,
            max_value=8.0,
            value=4.5,
            step=0.1,
            format="%.1f%%",
            help="Cenário mais provável conforme expectativas do mercado (Focus/BCB)",
            key="sim_ipca_base",
        )
        ipca_estresse = st.slider(
            "Estresse / Hiperinflação (IPCA % a.a.)",
            min_value=6.0,
            max_value=20.0,
            value=9.0,
            step=0.5,
            format="%.1f%%",
            help="Cenário adverso — similar a 2015 ou crises de supply chain",
            key="sim_ipca_estresse",
        )

    with col_s2:
        cenarios = {
            f"Inflação Baixa ({ipca_baixo:.1f}%)": retorno_cenario_ipca(
                taxa_atual_pct / 100, ipca_baixo / 100, anos_restantes, valor_sim
            ),
            f"Cenário Base ({ipca_base:.1f}%)": retorno_cenario_ipca(
                taxa_atual_pct / 100, ipca_base / 100, anos_restantes, valor_sim
            ),
            f"Estresse ({ipca_estresse:.1f}%)": retorno_cenario_ipca(
                taxa_atual_pct / 100, ipca_estresse / 100, anos_restantes, valor_sim
            ),
        }

        st.markdown(f"**Resultados Projetados em {anos_restantes} anos:**")

        rows = []
        for nome, c in cenarios.items():
            rows.append(
                {
                    "Cenário": nome,
                    "Taxa Nominal a.a.": f"{c['taxa_nominal_aa']:.2f}%",
                    "Valor Final": formatar_brl(c["valor_final"]),
                    "Retorno Nominal Acumulado": f"{c['retorno_nominal_pct'] / 100 + 1:.1f}× o capital inicial"
                    if c["retorno_nominal_pct"] > 1000
                    else f"{c['retorno_nominal_pct']:.1f}%",
                    "Ganho Real ✅": f"+{c['retorno_real_pct']:.1f}%",
                }
            )

        st.dataframe(
            pd.DataFrame(rows),
            use_container_width=True,
            hide_index=True,
        )
        _mult_real = (1 + taxa_atual_pct / 100) ** anos_restantes
        st.caption(
            f"✅ *Ganho Real* = poder de compra cresce **{_mult_real:.1f}×** em {anos_restantes} anos — "
            "idêntico nos 3 cenários porque a taxa real é travada na compra. "
            "O IPCA só muda o valor nominal, não o quanto você compra com ele."
        )

    fig_cen = grafico_cenarios(cenarios, anos_restantes, valor_sim)
    st.plotly_chart(fig_cen, use_container_width=True)

    st.divider()

    # -----------------------------------------------------------------------
    # 2. Simulador de MaM — Venda Antecipada
    # -----------------------------------------------------------------------
    st.subheader(
        ":material/show_chart:  Simulador de MaM — Estratégia de Venda Antecipada"
    )

    with st.expander("Como funciona a estratégia de MaM?", expanded=False):
        col_exp1, col_exp2 = st.columns([3, 2])
        with col_exp1:
            st.markdown("""
A **Marcação a Mercado (MaM)** permite vender um título Tesouro antes do vencimento
pelo preço atual de mercado — que varia conforme as expectativas de juros futuros.

**A estratégia:** comprar um título longo (ex: RendA+ 2065, T≈40 anos) quando as taxas
estão altas e vender antes do vencimento quando as taxas caem. A queda nos juros
valoriza o preço do título, gerando ganho de capital expressivo.

**Por que títulos mais longos amplificam o ganho?**
Quanto maior o prazo restante (T−N), mais sensível o preço é à variação da taxa real —
o mesmo princípio da duração modificada em finanças.
            """)
        with col_exp2:
            st.markdown("""
**Fórmula do impacto de MaM:**

```
Retorno = [(1 + taxa_compra) /
           (1 + taxa_venda)]^(T−N) − 1
```

`T` = anos até vencimento
`N` = anos até a venda antecipada
`taxa_compra` = yield real travado na compra
`taxa_venda` = yield real projetado na saída

**O IPCA não entra na fórmula** — o VNA
cancela algebraicamente. A coluna IPCA é
contexto macroeconômico que explica por
que a taxa real mudou.
            """)

    col_m1, col_m2 = st.columns([2, 1])

    with col_m1:
        titulos_validos = [
            t for t, cfg in TITULOS_CONFIG.items() if cfg["vencimento"] > date.today()
        ]
        if not titulos_validos:
            st.warning("Nenhum título com vencimento futuro disponível no catálogo.")
            ativos_sel = []
        else:
            # Se não há valor salvo, inicializa com o título atual como padrão
            _fallback = [titulo] if titulo in titulos_validos else titulos_validos[:1]
            if (
                "sim_ativos_sel" not in st.session_state
                or not st.session_state["sim_ativos_sel"]
            ):
                st.session_state["sim_ativos_sel"] = _fallback
            # Filtra opções que possam ter saído da lista de títulos válidos
            else:
                st.session_state["sim_ativos_sel"] = [
                    a
                    for a in st.session_state["sim_ativos_sel"]
                    if a in titulos_validos
                ] or _fallback
            ativos_sel = st.multiselect(
                "Ativos para Simular",
                options=titulos_validos,
                help="Selecione os ativos a comparar. Cada ativo usa seu prazo correto (T) na fórmula.",
                key="sim_ativos_sel",
            )

    with col_m2:
        prazo_saida = st.radio(
            "Prazo de Saída",
            options=[3, 5, 10],
            index=0,
            format_func=lambda x: f"{x} anos",
            help="Horizonte de venda antecipada — N na fórmula MaM.",
            key="sim_prazo_saida",
        )

    if not ativos_sel:
        st.warning(
            "Selecione ao menos um ativo no campo acima para calcular os retornos de MaM.",
            icon="👆",
        )
    else:
        # Metadata por ativo: T (anos até vencimento) e taxa de compra de mercado
        ativos_meta = {}
        for ativo in ativos_sel:
            cfg_a = TITULOS_CONFIG[ativo]
            t_anos = max(1, round((cfg_a["vencimento"] - date.today()).days / 365))
            linha_a = (
                df_titulos[df_titulos["nome"] == ativo]
                if not df_titulos.empty
                else pd.DataFrame()
            )
            taxa_a = (
                float(linha_a["taxa_compra"].values[0]) if not linha_a.empty else 7.50
            )
            ativos_meta[ativo] = {"t_anos": t_anos, "taxa": taxa_a}

        # Sumário dos ativos selecionados (até 4 colunas)
        cols_meta = st.columns(min(len(ativos_sel), 4))
        for i, ativo in enumerate(ativos_sel[:4]):
            meta = ativos_meta[ativo]
            nome_curto = ativo.replace("Tesouro ", "")
            suficiente = prazo_saida < meta["t_anos"]
            delta_str = (
                f"T = {meta['t_anos']} anos"
                if suficiente
                else f"T = {meta['t_anos']} anos ⚠️"
            )
            help_str = (
                None
                if suficiente
                else f"Este título vence em {meta['t_anos']} ano(s), antes do prazo de saída "
                f"de {prazo_saida} ano(s) selecionado.\n\n"
                f"A MaM só existe quando você vende **antes** do vencimento. Como o título "
                f"já teria chegado ao fim do prazo, você receberia exatamente a taxa "
                f"contratada — sem ganho nem perda de preço.\n\n"
                f"Para simular MaM com este título, escolha um prazo de saída menor "
                f"que {meta['t_anos']} ano(s)."
            )
            with cols_meta[i]:
                st.metric(
                    nome_curto, f"{meta['taxa']:.2f}% a.a.", delta_str, help=help_str
                )

        # Aviso: fórmula de MaM é aproximação para títulos com cupons semestrais
        _cupom_sel = [a for a in ativos_sel if "Juros Semestrais" in a]
        if _cupom_sel:
            _nomes = ", ".join(a.replace("Tesouro ", "") for a in _cupom_sel)
            st.info(
                f"**{_nomes}** paga(m) cupons semestrais durante o período de holding. "
                "A tabela abaixo mostra apenas o **efeito de preço** (variação do PU com a taxa) — "
                "os cupons recebidos ao longo do caminho não estão incluídos. "
                "O retorno total real é **maior** do que os valores exibidos. "
                "Use como referência para o risco de MaM, não como retorno total.",
                icon="ℹ️",
            )

        with st.expander("Configurar cenários macroeconômicos", expanded=False):
            st.caption(
                "Edite o IPCA projetado (contexto) e a taxa real de saída para cada cenário. "
                "Recolha este painel após configurar — os resultados abaixo atualizam automaticamente."
            )
            df_edit = st.data_editor(
                _CENARIOS_PADRAO.copy(),
                use_container_width=True,
                num_rows="fixed",
                hide_index=True,
                disabled=["Cenário"],
                column_config={
                    "Cenário": st.column_config.TextColumn("Cenário", width="medium"),
                    "IPCA Futuro (%)": st.column_config.NumberColumn(
                        "IPCA Futuro (contexto)",
                        min_value=0.0,
                        max_value=30.0,
                        step=0.5,
                        format="%.1f",
                        help="Inflação projetada — contexto macroeconômico que explica a variação da taxa real. "
                        "Não entra diretamente no cálculo (VNA cancela na fórmula).",
                    ),
                    "Taxa IPCA+ (%)": st.column_config.NumberColumn(
                        "Taxa Real na Saída (% a.a.)",
                        min_value=0.0,
                        max_value=30.0,
                        step=0.5,
                        format="%.1f",
                        help="Yield real IPCA+ de mercado projetado no momento da venda. "
                        "Esta é a variável que determina o ganho ou perda de MaM.",
                    ),
                },
            )

            st.divider()
            st.markdown("**📐  Forma da Curva Real no Cenário de Saída**")
            _cv_col1, _cv_col2 = st.columns([2, 1])
            with _cv_col1:
                curva_slope = st.slider(
                    "Inclinação (p.p.)",
                    min_value=-4.0,
                    max_value=4.0,
                    value=0.0,
                    step=0.25,
                    format="%.2f",
                    help=(
                        "Define como a taxa de saída varia por prazo do título. "
                        "0 = choque paralelo (todos os prazos sobem/caem igual). "
                        "Positivo = curva normal (longos têm taxa maior). "
                        "Negativo = curva invertida (curtos têm taxa maior)."
                    ),
                    key="sim_curva_slope",
                )
            with _cv_col2:
                _sh = abs(curva_slope) / 2
                if abs(curva_slope) < 0.01:
                    st.info("Paralelo — mesma taxa em todos os prazos", icon="⚡")
                elif curva_slope > 0:
                    st.success(
                        f"Normal — curto −{_sh:.2f}p.p. / longo +{_sh:.2f}p.p.",
                        icon="📈",
                    )
                else:
                    st.warning(
                        f"Invertida — curto +{_sh:.2f}p.p. / longo −{_sh:.2f}p.p.",
                        icon="📉",
                    )
            st.caption(
                "Classificação por prazo restante (T): **curto** T < 5 anos · "
                "**médio** 5–15 anos · **longo** T > 15 anos. "
                "A taxa da tabela acima é o ponto central (médio). "
                "Curto e longo recebem ± metade da inclinação."
            )

        _curva_slope = st.session_state.get("sim_curva_slope", 0.0)

        # Resultados sempre visíveis — independem do estado do expander
        resultados: dict = {"Cenário": df_edit["Cenário"].tolist()}

        for ativo in ativos_sel:
            meta = ativos_meta[ativo]
            t = meta["t_anos"]
            taxa_c = meta["taxa"] / 100
            nome_curto = ativo.replace("Tesouro ", "")

            if prazo_saida >= t:
                resultados[nome_curto] = ["—"] * len(df_edit)
            else:
                # Yield curve slope: short (<5yr) → −slope/2, mid (5–15yr) → 0, long (>15yr) → +slope/2
                _bucket = 1 if t > 15 else (-1 if t < 5 else 0)
                _adj_pp = (_curva_slope / 2) * _bucket
                valores = []
                for _, row in df_edit.iterrows():
                    _taxa_v = max(
                        0.001, float(row["Taxa IPCA+ (%)"]) / 100 + _adj_pp / 100
                    )
                    ret = retorno_mam_antecipado(
                        taxa_compra=taxa_c,
                        taxa_venda=_taxa_v,
                        anos_saida=float(prazo_saida),
                        anos_vencimento=float(t),
                    )
                    valores.append("—" if ret != ret else f"{ret:+.2f}%")
                resultados[nome_curto] = valores

        df_result = pd.DataFrame(resultados)
        prazo_cols = [c for c in df_result.columns if c != "Cenário"]

        styled = df_result.style.map(_cor_retorno, subset=prazo_cols).set_properties(
            subset=["Cenário"], **{"font-weight": "600"}
        )

        st.markdown(f"**Impacto de MaM por Cenário — Saída em {prazo_saida} anos:**")
        st.dataframe(styled, use_container_width=True, hide_index=True)

        st.caption(
            "Retorno calculado sobre o preço ideal de carrego na data de saída. "
            "Taxa de compra = yield atual de mercado de cada ativo. "
            "⚠️ Simulação educacional — não considera IR, IOF nem corretagem."
        )
        if abs(_curva_slope) > 0.01:
            _adj_parts = []
            for _av in ativos_sel:
                _t = ativos_meta[_av]["t_anos"]
                if prazo_saida < _t:
                    _bk = 1 if _t > 15 else (-1 if _t < 5 else 0)
                    _ap = (_curva_slope / 2) * _bk
                    _label = (
                        "longo" if _bk == 1 else ("curto" if _bk == -1 else "médio")
                    )
                    _adj_parts.append(
                        f"**{_av.replace('Tesouro ', '')}** (T={_t}a, {_label}): {_ap:+.2f}p.p."
                    )
            if _adj_parts:
                st.caption("📐 Ajuste de curva aplicado: " + " · ".join(_adj_parts))

    st.divider()
    st.subheader(":material/menu_book:  Referência de Mercado")
    st.caption(
        "Dados de contexto para calibrar suas simulações. Não são gerados automaticamente — insira manualmente ou consulte sua corretora."
    )

    _aba_di, _aba_ipca = st.tabs(
        ["DI Futuro — Curva de Juros", "Retrospecto Histórico IPCA"]
    )

    with _aba_di:
        with st.expander("O que é o DI Futuro e por que ele importa?", expanded=True):
            col_exp1, col_exp2 = st.columns([3, 2])

            with col_exp1:
                st.markdown("""
O **DI Futuro** é o contrato mais líquido negociado na **B3** (Bolsa brasileira).
Ele representa a **expectativa coletiva do mercado** para a taxa de juros (CDI) em datas futuras.

**Como ele impacta o seu Tesouro IPCA+?**

Quando o mercado eleva as expectativas de juros futuros (DI Futuro sobe), o preço dos
títulos de renda fixa **cai** — porque os investidores passam a exigir um yield maior para
comprar esses títulos. É exatamente isso que gera a oscilação que você vê no extrato:
a famosa **Marcação a Mercado**.

Se você aguardar o vencimento, essa flutuação não tem efeito algum sobre o que receberá.

**Como encontrar as taxas atuais do DI Futuro:**
- 🌐 **B3**: b3.com.br → Mercados → Derivativos → DI de 1 Dia
- 📱 **Corretora**: aba Renda Fixa ou Derivativos da sua plataforma
- 📊 **Investing.com**: busque por "DI Futuro Brasil"
- 💼 **Bloomberg**: `DI1 <Cmdty>` ou `BZCR <Index>`
                """)

            with col_exp2:
                st.markdown("""
**Exemplo de leitura:**

| Contrato | Taxa Implícita |
|----------|----------------|
| DI Jan/27 | 13,20% a.a.  |
| DI Jan/29 | 13,55% a.a.  |
| DI Jan/33 | 13,85% a.a.  |

Uma curva **inclinada para cima** (como acima) indica que o mercado espera juros
mais altos no longo prazo — sinal de desconfiança fiscal ou inflação persistente.

Uma curva **plana ou invertida** sinaliza que o mercado espera queda de juros
no futuro — cenário positivo para quem detém títulos longos.
                """)

        st.markdown(
            "**Insira as taxas do DI Futuro (conforme dados mais recentes da B3):**"
        )

        vencimentos_di = ["Jan/27", "Jan/28", "Jan/29", "Jan/31", "Jan/33", "Jan/35"]
        _di_keys = [
            "sim_di_jan27",
            "sim_di_jan28",
            "sim_di_jan29",
            "sim_di_jan31",
            "sim_di_jan33",
            "sim_di_jan35",
        ]
        defaults_di = [14.75, 14.70, 14.65, 14.55, 14.40, 14.25]

        cols_di = st.columns(len(vencimentos_di))
        di_inputs = []

        for col, venc, default, dk in zip(
            cols_di, vencimentos_di, defaults_di, _di_keys
        ):
            with col:
                taxa = st.number_input(
                    f"DI {venc}",
                    min_value=5.0,
                    max_value=30.0,
                    value=default,
                    step=0.05,
                    format="%.2f",
                    key=dk,
                )
                di_inputs.append({"vencimento": venc, "taxa": taxa})

        fig_di = grafico_curva_di(di_inputs)
        st.plotly_chart(fig_di, use_container_width=True)

        st.caption(
            "⚠️ As taxas acima são inseridas manualmente. "
            "Atualize-as com os dados mais recentes da B3 para uma análise precisa."
        )

    with _aba_ipca:
        # -------------------------------------------------------------------
        # 4. Retrospecto Histórico — IPCA
        # -------------------------------------------------------------------
        st.subheader(":material/history:  Retrospecto Histórico — IPCA no Brasil")

        col_h1, col_h2 = st.columns([3, 2])

        with col_h1:
            fig_ipca = grafico_ipca_historico(df_ipca)
            st.plotly_chart(fig_ipca, use_container_width=True)

        with col_h2:
            st.markdown("### Marcos Históricos")
            st.markdown("""
**2015 — Crise Fiscal Brasileira (10,67%)**
Ajuste fiscal, desvalorização cambial e colapso das commodities elevaram a inflação
ao maior nível em 13 anos, forçando o BCB a subir a Selic para 14,25%.

---

**2018 — Greve dos Caminhoneiros (3,75%)**
Paralisação nacional causou desabastecimento pontual. O IPCA anual ficou controlado,
mas a volatilidade mensal foi expressiva em alimentos.

---

**2021 — Ressurgência Pós-Pandemia (10,06%)**
Gargalos globais de supply chain, crise hídrica (energia) e câmbio desvalorizado
empurraram o IPCA ao dobro da meta do BCB.

---

**2022 — Pressão persistente (5,79%)**
Mesmo com Selic em 13,75%, a inflação resistiu. Início do ciclo de desinflação
gradual que se estendeu até 2023.

---

💡 **Lição central:** a inflação oscila em ciclos. O **Tesouro IPCA+** protege
seu poder de compra em **todos** esses cenários — é exatamente para isso que ele existe.
            """)

        with st.expander("Ver série completa do IPCA (mensal)", expanded=False):
            df_display = df_ipca.copy()
            df_display["Mês/Ano"] = df_display["data"].dt.strftime("%b/%Y")
            df_display["IPCA (%)"] = df_display["valor"].map(lambda v: f"{v:.2f}%")
            st.dataframe(
                df_display[["Mês/Ano", "IPCA (%)"]].sort_values(
                    "Mês/Ano", ascending=False
                ),
                use_container_width=True,
                hide_index=True,
                height=300,
            )
            st.caption("Fonte: Banco Central do Brasil — SGS Série 433 (IPCA mensal).")

    # Persiste preferências do usuário para o próximo refresh
    salvar(
        {
            "sim_categoria": st.session_state.get("sim_categoria"),
            "sim_titulo": st.session_state.get("sim_titulo"),
            "sim_ativos_sel": st.session_state.get("sim_ativos_sel", []),
            "sim_valor": st.session_state.get("sim_valor", 10_000.0),
            "sim_ipca_baixo": st.session_state.get("sim_ipca_baixo", 3.0),
            "sim_ipca_base": st.session_state.get("sim_ipca_base", 4.5),
            "sim_ipca_estresse": st.session_state.get("sim_ipca_estresse", 9.0),
            "sim_prazo_saida": st.session_state.get("sim_prazo_saida", 3),
            "sim_curva_slope": st.session_state.get("sim_curva_slope", 0.0),
            "sim_di_jan27": st.session_state.get("sim_di_jan27", 14.75),
            "sim_di_jan28": st.session_state.get("sim_di_jan28", 14.70),
            "sim_di_jan29": st.session_state.get("sim_di_jan29", 14.65),
            "sim_di_jan31": st.session_state.get("sim_di_jan31", 14.55),
            "sim_di_jan33": st.session_state.get("sim_di_jan33", 14.40),
            "sim_di_jan35": st.session_state.get("sim_di_jan35", 14.25),
        }
    )
