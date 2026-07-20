"""
Tela 3 — Qual Ativo Escolher?

Responde a pergunta prática do investidor: dado o meu horizonte de saída,
qual título do Tesouro Direto oferece o melhor retorno real pelo menor risco de MaM?
"""

import streamlit as st
import pandas as pd

from core.dados import (
    obter_dados_completos,
    montar_catalogo_batalha,
    timestamp_ultima_atualizacao,
    chave_cache_mercado,
)
from core.persistencia import carregar, salvar, inicializar_session
from core.batalha import carteira_mista, gerar_portfolios_aleatorios
from core.financas import (
    analise_batalha,
    formatar_brl,
    aliquota_ir_renda_fixa,
    retorno_liquido_ir,
    retorno_saida_antecipada,
    retorno_hold_to_mat_reinvestido,
)
from core.graficos import (
    grafico_markowitz,
    grafico_cenarios_batalha,
    grafico_retorno_por_horizonte,
)


@st.cache_data(ttl=300, show_spinner=False)
def _analise_cached(
    nome, tipo, taxa, anos_total, anos_saida, ipca, choque, com_ir, selic
):
    """Wrapper para analise_batalha; isolado para facilitar cache no Streamlit."""
    return analise_batalha(
        nome=nome,
        tipo=tipo,
        taxa=taxa,
        anos_total=anos_total,
        anos_saida=anos_saida,
        ipca=ipca,
        choque=choque,
        com_ir=com_ir,
        selic=selic,
    )


_TIPO_NOME = {
    "selic": "Pós-Fixado (Selic)",
    "pre": "Pré-Fixado",
    "ipca_mais": "IPCA+ / RendA+ / Educar+",
}

_DEFAULTS = [
    "Tesouro Selic 2031",
    "Tesouro Prefixado 2029",
    "Tesouro Prefixado 2032",
    "Tesouro IPCA+ 2032",
    "Tesouro IPCA+ 2040",
]

_RISCO_MAP = {
    0: "🟢 Nenhuma",
    1: "🟡 Baixa",
    2: "🟠 Média",
    3: "🔴 Alta",
}


def _risco_expo(tipo, anos_expo):
    """Converte anos de exposição a MaM em rótulo de risco textual."""
    if tipo == "selic" or anos_expo == 0:
        return _RISCO_MAP[0]
    if anos_expo <= 2:
        return _RISCO_MAP[1]
    if anos_expo <= 5:
        return _RISCO_MAP[2]
    return _RISCO_MAP[3]


def _winner(analises: list) -> dict:
    """Retorna o título com melhor índice retorno/risco (Sharpe simplificado)."""
    return max(analises, key=lambda a: a["ret_neu"] / max(a["risco_std"], 0.01))


_PERFIS = ["Conservador", "Moderado", "Arrojado"]

_PERFIL_HELP = (
    "**Conservador 🟢** — minimiza o risco de Marcação a Mercado. "
    "Prefere o título com menor volatilidade entre os cenários.\n\n"
    "**Moderado 🟡** — melhor relação retorno/risco (índice Sharpe). "
    "Padrão recomendado para a maioria dos investidores.\n\n"
    "**Arrojado 🔴** — maximiza o retorno no cenário favorável. "
    "Aceita maior volatilidade em troca do maior potencial de ganho."
)

_PERFIL_EMOJI = {"Conservador": "🟢", "Moderado": "🟡", "Arrojado": "🔴"}


def _winner_por_perfil(analises: list, perfil: str) -> dict:
    """Seleciona o título vencedor segundo o perfil de risco do usuário."""
    if perfil == "Conservador":
        return min(analises, key=lambda a: a["risco_std"])
    if perfil == "Arrojado":
        return max(analises, key=lambda a: a["ret_fav"])
    return _winner(analises)


def _insight_texto(w: dict, horizonte: int, ipca: float, com_ir: bool) -> str:
    """Gera o parágrafo de insight para o título vencedor, adaptado ao tipo e perfil."""
    nome = w["nome"].replace("Tesouro ", "")
    tipo = w["tipo"]
    expo = w["anos_expo"]
    ret = w["ret_neu"]
    ir_obs = " (líquido de IR)" if com_ir else ""

    if tipo == "selic":
        return (
            f"**{nome}** é o mais indicado para seu horizonte de **{horizonte} ano(s)**{ir_obs}. "
            f"Como pós-fixado, ele não sofre Marcação a Mercado — você pode sair a qualquer "
            f"momento sem surpresas de preço. Retorno esperado: **{ret:.1f}% a.a.** "
            f"Atenção: se a Selic cair, o rendimento cai junto — a taxa não é travada."
        )
    reinvest = w.get("reinvest", False)

    if tipo == "pre":
        if reinvest:
            return (
                f"**{nome}** vence antes do seu horizonte{ir_obs}. "
                f"Retorno combinado de **{ret:.1f}% a.a.**: Fase 1 no Prefixado até o vencimento "
                f"+ Fase 2 reinvestindo a Selic. Cenário adverso (Selic cai): "
                f"**{w['ret_adv']:.1f}% a.a.** — ainda sem risco de MaM."
            )
        if expo == 0:
            return (
                f"**{nome}** vence dentro do seu horizonte{ir_obs} — você recebe os "
                f"**{ret:.1f}% a.a.** com certeza, sem exposição à MaM. "
                f"Taxa nominal travada acima da inflação projetada de {ipca:.1f}%: "
                f"ganho real de **{w['ret_real']:.1f}% a.a.**"
            )
        return (
            f"**{nome}** oferece **{ret:.1f}% a.a.**{ir_obs}, mas você sairá "
            f"**{expo:.1f} anos antes do vencimento**. No cenário adverso "
            f"(taxas +1 p.p.), o retorno cai para **{w['ret_adv']:.1f}%** — avalie "
            f"se essa amplitude de risco é aceitável para o seu perfil."
        )
    if reinvest:
        return (
            f"**{nome}** vence antes do seu horizonte{ir_obs}. "
            f"Retorno combinado de **{ret:.1f}% a.a.**: Fase 1 no IPCA+ com proteção "
            f"real de {w['ret_real']:.1f}% a.a. + Fase 2 reinvestindo a Selic. "
            f"Cenário adverso (Selic cai): **{w['ret_adv']:.1f}% a.a.**"
        )
    if expo == 0:
        return (
            f"**{nome}** é o vencedor{ir_obs}: taxa real travada, proteção total contra "
            f"inflação e vencimento alinhado ao horizonte. Ganho real: "
            f"**{w['ret_real']:.1f}% a.a.** garantido independente do IPCA projetado ({ipca:.1f}%)."
        )
    return (
        f"**{nome}** oferece o melhor equilíbrio retorno/risco{ir_obs}. "
        f"Taxa real de **{w['ret_real']:.1f}% a.a.** protege o poder de compra, "
        f"com {expo:.1f} anos de exposição à MaM. Cenário adverso: "
        f"**{w['ret_adv']:.1f}%** — ainda positivo em termos reais."
    )


def render():
    """Tela 2 — Qual Ativo Escolher?: comparativo de cenários, Markowitz e retorno por horizonte."""
    st.session_state["_page_id"] = "batalha"

    # Carrega preferências salvas antes de qualquer widget
    _prefs = carregar()
    inicializar_session(_prefs)

    # -----------------------------------------------------------------------
    # Cabeçalho
    # -----------------------------------------------------------------------
    st.markdown(
        '<p class="titulo-principal">Qual Ativo Escolher?</p>'
        '<p class="subtitulo">Informe quando precisa do dinheiro — o simulador compara '
        "cada título Tesouro pelo retorno real e pelo risco de Marcação a Mercado "
        "no <em>seu</em> horizonte.</p>",
        unsafe_allow_html=True,
    )

    with st.spinner("Consultando carteira de títulos do Tesouro Direto..."):
        _, df_titulos, _ = obter_dados_completos()

    _ts = timestamp_ultima_atualizacao(chave_cache_mercado())
    if not df_titulos.empty:
        st.caption(
            f"✅ Dados ao vivo · carregados às **{_ts.strftime('%H:%M')}** (atualiza a cada 2h)"
        )
    else:
        st.caption("⚠️ Modo offline — usando dados de referência")

    # -----------------------------------------------------------------------
    # Inputs — antes dos expanders para que o painel dinâmico use os valores
    # -----------------------------------------------------------------------
    st.subheader(":material/tune:  Configure sua Situação")

    with st.expander("Premissas Macroeconômicas", expanded=False):
        st.caption(
            "Defaults calibrados para o cenário atual. Ajuste se quiser simular trajetórias diferentes."
        )
        _mc1, _mc2, _mc3 = st.columns(3)
        with _mc1:
            ipca_pct = st.slider(
                "IPCA Projetado (% a.a.)",
                1.0,
                15.0,
                5.0,
                0.1,
                format="%.1f%%",
                key="bat_ipca",
                help=(
                    "Estimativa de inflação média anual ao longo do horizonte simulado.\n\n"
                    "Não afeta o ganho real do IPCA+ (travado no contrato) — muda apenas o valor nominal."
                ),
            )
        with _mc2:
            selic_pct = st.slider(
                "Selic Projetada (% a.a.)",
                2.0,
                25.0,
                14.75,
                0.25,
                format="%.2f%%",
                key="bat_selic",
                help=(
                    "Estimativa da Selic média ao longo do horizonte simulado.\n\n"
                    "Usada pelo Tesouro Selic e pela fase de reinvestimento quando um título vence antes do horizonte."
                ),
            )
        with _mc3:
            choque_pp = st.slider(
                "Choque de Taxa (p.p.)",
                0.25,
                3.0,
                1.0,
                0.25,
                format="%.2f p.p.",
                key="bat_choque",
                help=(
                    "Magnitude do choque aplicado nos cenários adverso (+) e favorável (−).\n\n"
                    "O Tesouro Selic não sofre esse efeito por ser pós-fixado."
                ),
            )

    col_h, col_sel = st.columns([1, 1.8])

    with col_h:
        st.markdown("**Quando precisa do dinheiro?**")
        horizonte = st.slider(
            "Horizonte de saída (anos)",
            min_value=1,
            max_value=15,
            value=3,
            key="bat_horizonte",
        )
        capital = st.number_input(
            "Capital Inicial (R$)",
            min_value=100.0,
            max_value=1_000_000.0,
            value=10_000.0,
            step=500.0,
            format="%.2f",
            key="bat_capital",
        )
        com_ir = st.checkbox(
            "Calcular com IR regressivo",
            value=True,
            help="Alíquota regressiva sobre o lucro nominal: 22,5% (≤6m) → 20% (≤1a) → 17,5% (≤2a) → 15% (>2a)",
            key="bat_com_ir",
        )
        if com_ir:
            aliq = aliquota_ir_renda_fixa(horizonte)
            st.caption(
                f"IR aplicado: **{aliq * 100:.1f}%** sobre o lucro (horizonte = {horizonte} ano(s))"
            )

        st.markdown("**Perfil de Risco**")
        perfil = st.radio(
            "Perfil",
            options=_PERFIS,
            captions=[
                "Minimiza risco de MaM — prefere Selic e curto prazo",
                "Melhor retorno/risco (Índice Sharpe) — recomendado",
                "Maximiza potencial de ganho — aceita volatilidade",
            ],
            index=_PERFIS.index(st.session_state.get("bat_perfil", "Moderado")),
            horizontal=False,
            key="bat_perfil",
            label_visibility="collapsed",
        )

    with col_sel:
        st.markdown("**Títulos a Comparar**")
        catalogo = montar_catalogo_batalha(df_titulos, selic_pct)
        opcoes = [t["nome"] for t in catalogo]

        if not opcoes:
            st.warning(
                "Nenhum título disponível no catálogo. Verifique a conexão com os dados.",
                icon="⚠️",
            )
            selecionados = []
        else:
            # Garante que bat_selecionados sempre tem itens válidos do catálogo atual
            _bat_fallback = [d for d in _DEFAULTS if d in opcoes] or opcoes[:5]
            if (
                "bat_selecionados" not in st.session_state
                or not st.session_state["bat_selecionados"]
            ):
                st.session_state["bat_selecionados"] = _bat_fallback
            else:
                st.session_state["bat_selecionados"] = [
                    a for a in st.session_state["bat_selecionados"] if a in opcoes
                ] or _bat_fallback

            selecionados = st.multiselect(
                "Selecione os títulos",
                options=opcoes,
                help="Todos os títulos disponíveis — IPCA+, RendA+, Educar+, Prefixado e Selic.",
                key="bat_selecionados",
            )

    # -----------------------------------------------------------------------
    # Painel Educativo Dinâmico
    # -----------------------------------------------------------------------
    H = float(horizonte)
    ip = ipca_pct / 100
    sl = selic_pct / 100

    pre_ex = next((t for t in catalogo if t["tipo"] == "pre"), None)
    ipca_ex = next(
        (t for t in catalogo if t["tipo"] == "ipca_mais" and "IPCA+" in t["nome"]), None
    )
    renda_ex = next((t for t in catalogo if "RendA+" in t["nome"]), None)
    educar_ex = next((t for t in catalogo if "Educar+" in t["nome"]), None)

    st.divider()
    with st.expander(
        "Entenda como cada título se comporta no seu cenário", expanded=True
    ):
        st.caption(
            f"Exemplos calculados para: IPCA {ipca_pct:.1f}% · Selic {selic_pct:.1f}% · "
            f"Horizonte {horizonte} ano(s) · {formatar_brl(capital)}"
            + (" · com IR" if com_ir else " · sem IR")
        )

        col_d1, col_d2, col_d3 = st.columns(3)

        # ---- Selic ----
        with col_d1:
            st.markdown("#### Tesouro Selic — Pós-Fixado")
            vf_sl = capital * (1 + sl) ** H
            vf_sl_l = (
                capital * (1 + retorno_liquido_ir(sl, H)) ** H if com_ir else vf_sl
            )
            real_sl = ((1 + sl) / (1 + ip)) ** H - 1
            vf_adv = capital * (1 + max(sl - choque_pp / 100, 0.001)) ** H

            st.metric(
                "Retorno estimado",
                f"{selic_pct:.2f}% a.a.",
                f"Real projetado: {real_sl * 100:.1f}% acima do IPCA",
                help=(
                    "Pós-fixado: rende a Selic dia a dia, sem risco de MaM.\n\n"
                    "Risco de reinvestimento: se a Selic cair, o rendimento cai junto — sem proteção de taxa.\n\n"
                    "Use quando precisar de liquidez imediata ou não souber quando vai sacar."
                ),
            )
            st.markdown(
                f"{formatar_brl(capital)} → **{formatar_brl(vf_sl_l)}** em {horizonte} ano(s)"
                f"{' (líquido IR)' if com_ir else ''} · "
                f"adverso: **{formatar_brl(vf_adv)}**"
            )

        # ---- Prefixado ----
        with col_d2:
            st.markdown("#### Tesouro Prefixado — Pré-Fixado")
            if pre_ex:
                tp = pre_ex["taxa"] / 100
                T_pre = pre_ex["anos_total"]
                expo_pre = max(0.0, T_pre - H)
                ck = choque_pp / 100
                _reinvest_pre = H > T_pre and sl > 0

                if _reinvest_pre:
                    r_neu_pre = retorno_hold_to_mat_reinvestido(
                        tp, T_pre, H, "pre", ip, sl, com_ir
                    )
                    r_adv_pre = retorno_hold_to_mat_reinvestido(
                        tp, T_pre, H, "pre", ip, max(sl - ck, 0.001), com_ir
                    )
                    vf_pr_l = capital * (1 + r_neu_pre) ** H
                    vf_adv_p = capital * (1 + r_adv_pre) ** H
                    delta_str = f"{r_neu_pre * 100:.1f}% a.a. combinado"
                else:
                    r_neu_pre = tp
                    vf_pr_l = (
                        capital * (1 + retorno_liquido_ir(tp, H)) ** H
                        if com_ir
                        else capital * (1 + tp) ** H
                    )
                    real_pre = ((1 + tp) / (1 + ip)) ** H - 1
                    r_adv_p = retorno_saida_antecipada(tp, tp + ck, T_pre, H, "pre")
                    if com_ir:
                        r_adv_p = retorno_liquido_ir(r_adv_p, H)
                    vf_adv_p = capital * (1 + r_adv_p) ** H
                    delta_str = f"Real projetado: {real_pre * 100:.1f}% acima do IPCA"

                st.metric(
                    f"Taxa travada — {pre_ex['nome'].replace('Tesouro ', '')}",
                    f"{pre_ex['taxa']:.2f}% a.a.",
                    delta_str,
                    help="Taxa nominal garantida no contrato. Use quando quiser travar uma taxa alta — tolerando reinvestir a Selic se o título vencer antes do horizonte, ou apostando na queda da Selic.",
                )

                if _reinvest_pre:
                    anos_rest_pre = H - T_pre
                    st.markdown(
                        f"F1 ({T_pre:.1f}a): {pre_ex['taxa']:.1f}% a.a. · "
                        f"F2 ({anos_rest_pre:.1f}a): Selic {selic_pct:.1f}%\n\n"
                        f"{formatar_brl(capital)} → **{formatar_brl(vf_pr_l)}** em {horizonte} ano(s)"
                        f"{' (líquido IR)' if com_ir else ''} · "
                        f"adverso: **{formatar_brl(vf_adv_p)}**"
                    )
                else:
                    _adv_pre = (
                        "✅ Vence dentro do horizonte."
                        if expo_pre == 0
                        else f"⚠️ Adverso (+{choque_pp:.2f} p.p.): **{formatar_brl(vf_adv_p)}** ({r_adv_p * 100:.1f}% a.a.)"
                    )
                    st.markdown(
                        f"{formatar_brl(capital)} → **{formatar_brl(vf_pr_l)}** em {horizonte} ano(s)"
                        f"{' (líquido IR)' if com_ir else ''}\n\n"
                        f"MaM: {expo_pre:.1f}a → {_risco_expo('pre', expo_pre)}\n\n"
                        f"{_adv_pre}"
                    )
            else:
                st.info("Nenhum Prefixado disponível no catálogo.")

        # ---- IPCA+ ----
        with col_d3:
            st.markdown("#### Tesouro IPCA+ — Híbrido")
            if ipca_ex:
                tr = ipca_ex["taxa"] / 100
                T_ip = ipca_ex["anos_total"]
                expo_ip = max(0.0, T_ip - H)
                ck = choque_pp / 100
                _reinvest_ip = H > T_ip and sl > 0

                if _reinvest_ip:
                    r_neu_ip = retorno_hold_to_mat_reinvestido(
                        tr, T_ip, H, "ipca_mais", ip, sl, com_ir
                    )
                    r_adv_ip = retorno_hold_to_mat_reinvestido(
                        tr, T_ip, H, "ipca_mais", ip, max(sl - ck, 0.001), com_ir
                    )
                    vf_ip_l = capital * (1 + r_neu_ip) ** H
                    vf_adv_ip = capital * (1 + r_adv_ip) ** H
                    delta_str_ip = f"{r_neu_ip * 100:.1f}% a.a. combinado"
                else:
                    nom_ip = (1 + tr) * (1 + ip) - 1
                    vf_ip = capital * (1 + nom_ip) ** H
                    vf_ip_l = (
                        capital * (1 + retorno_liquido_ir(nom_ip, H)) ** H
                        if com_ir
                        else vf_ip
                    )
                    r_adv_ip = retorno_saida_antecipada(
                        tr, tr + ck, T_ip, H, "ipca_mais", ip
                    )
                    if com_ir:
                        r_adv_ip = retorno_liquido_ir(r_adv_ip, H)
                    vf_adv_ip = capital * (1 + r_adv_ip) ** H
                    delta_str_ip = (
                        f"Nominal: ~{nom_ip * 100:.1f}% com IPCA {ipca_pct:.1f}%"
                    )

                st.metric(
                    f"Taxa real travada — {ipca_ex['nome'].replace('Tesouro ', '')}",
                    f"IPCA + {ipca_ex['taxa']:.2f}% a.a.",
                    delta_str_ip,
                    help="Taxa real garantida no contrato, acima da inflação — qualquer que seja o IPCA futuro. Use quando quiser proteger o poder de compra no longo prazo.",
                )

                if _reinvest_ip:
                    anos_rest_ip = H - T_ip
                    st.markdown(
                        f"F1 ({T_ip:.1f}a): IPCA + {ipca_ex['taxa']:.2f}% · "
                        f"F2 ({anos_rest_ip:.1f}a): Selic {selic_pct:.1f}%\n\n"
                        f"{formatar_brl(capital)} → **{formatar_brl(vf_ip_l)}** em {horizonte} ano(s)"
                        f"{' (líquido IR)' if com_ir else ''} · "
                        f"adverso: **{formatar_brl(vf_adv_ip)}**"
                    )
                else:
                    _adv_ip = (
                        "✅ Vence dentro do horizonte."
                        if expo_ip == 0
                        else f"⚠️ Adverso (+{choque_pp:.2f} p.p.): **{formatar_brl(vf_adv_ip)}** ({r_adv_ip * 100:.1f}% a.a.)"
                    )
                    st.markdown(
                        f"{formatar_brl(capital)} → **{formatar_brl(vf_ip_l)}** em {horizonte} ano(s)"
                        f"{' (líquido IR)' if com_ir else ''}\n\n"
                        f"MaM: {expo_ip:.1f}a → {_risco_expo('ipca_mais', expo_ip)}\n\n"
                        f"{_adv_ip}"
                    )
            else:
                st.info("Nenhum IPCA+ disponível no catálogo.")

        # ---- RendA+ e Educar+ ----
        st.markdown("---")
        col_d4, col_d5 = st.columns(2)

        with col_d4:
            st.markdown("#### Tesouro RendA+ — Aposentadoria Extra")
            if renda_ex:
                tr_r = renda_ex["taxa"] / 100
                T_r = renda_ex["anos_total"]
                expo_r = max(0.0, T_r - H)
                nom_r = (1 + tr_r) * (1 + ip) - 1
                vf_r = capital * (1 + nom_r) ** min(H, T_r)
                vf_r_l = (
                    capital
                    * (1 + retorno_liquido_ir(nom_r, min(H, T_r))) ** min(H, T_r)
                    if com_ir
                    else vf_r
                )
                st.metric(
                    f"Taxa real — {renda_ex['nome'].replace('Tesouro ', '')}",
                    f"IPCA + {renda_ex['taxa']:.2f}% a.a.",
                    f"Nominal: ~{nom_r * 100:.1f}% com IPCA {ipca_pct:.1f}%",
                    help=(
                        "Acumulação até o vencimento: cresce a IPCA + taxa, igual a um IPCA+ convencional.\n\n"
                        "Após o vencimento: pagamento mensal vitalício proporcional ao capital acumulado.\n\n"
                        "Uso avançado: por ter o prazo mais longo do mercado (até 2065), é o título mais "
                        "sensível a variações de taxa — queda de 1 p.p. gera ganho expressivo via MaM.\n\n"
                        "Use quando: quiser transformar patrimônio em renda vitalícia corrigida pela inflação."
                    ),
                )
                st.markdown(
                    f"{formatar_brl(capital)} → **{formatar_brl(vf_r_l)}** até {renda_ex['vencimento'].strftime('%d/%m/%Y')}"
                    f"{' (aprox., com IR)' if com_ir else ''}\n\n"
                    f"MaM: {expo_r:.1f}a → {_risco_expo('ipca_mais', expo_r)}\n\n"
                    "⚠️ Liquidez restrita após início da renda · IR em cada parcela mensal"
                )
            else:
                st.info("Nenhum RendA+ disponível no catálogo.")

        with col_d5:
            st.markdown("#### Tesouro Educar+ — Educação dos Filhos")
            if educar_ex:
                tr_e = educar_ex["taxa"] / 100
                T_e = educar_ex["anos_total"]
                expo_e = max(0.0, T_e - H)
                nom_e = (1 + tr_e) * (1 + ip) - 1
                vf_e = capital * (1 + nom_e) ** min(H, T_e)
                vf_e_l = (
                    capital
                    * (1 + retorno_liquido_ir(nom_e, min(H, T_e))) ** min(H, T_e)
                    if com_ir
                    else vf_e
                )
                st.metric(
                    f"Taxa real — {educar_ex['nome'].replace('Tesouro ', '')}",
                    f"IPCA + {educar_ex['taxa']:.2f}% a.a.",
                    f"Nominal: ~{nom_e * 100:.1f}% com IPCA {ipca_pct:.1f}%",
                    help=(
                        "Acumulação até o vencimento: cresce a IPCA + taxa, igual a um IPCA+ convencional.\n\n"
                        "Após o vencimento: 60 parcelas mensais (5 anos), ideal para mensalidades universitárias.\n\n"
                        "Liquidez restrita após início dos pagamentos — sem resgate antecipado do saldo.\n\n"
                        "Use quando: quiser financiar os estudos dos filhos com proteção contra inflação e taxa garantida."
                    ),
                )
                st.markdown(
                    f"{formatar_brl(capital)} → **{formatar_brl(vf_e_l)}** até {educar_ex['vencimento'].strftime('%d/%m/%Y')}"
                    f"{' (aprox., com IR)' if com_ir else ''}\n\n"
                    f"MaM: {expo_e:.1f}a → {_risco_expo('ipca_mais', expo_e)}\n\n"
                    "⚠️ Liquidez restrita após início dos pagamentos · IR em cada parcela"
                )
            else:
                st.info("Nenhum Educar+ disponível no catálogo.")

        # ---- Tabela de exposição por horizonte ----
        st.markdown("---")
        st.markdown(
            f"**📅 Exposição ao risco de MaM no horizonte de {horizonte} ano(s):**"
        )

        bonds_expo = [
            t
            for t in catalogo
            if t["nome"] in (selecionados if selecionados else _DEFAULTS)
        ]
        if bonds_expo:
            rows_exp = []
            for t in bonds_expo:
                expo = max(0.0, t["anos_total"] - H)
                rows_exp.append(
                    {
                        "Título": t["nome"].replace("Tesouro ", ""),
                        "Tipo": _TIPO_NOME[t["tipo"]],
                        "Vence em": t["vencimento"].strftime("%d/%m/%Y"),
                        "Anos após saída": f"{expo:.1f}",
                        "Exposição MaM": _risco_expo(t["tipo"], expo),
                    }
                )
            st.dataframe(
                pd.DataFrame(rows_exp),
                hide_index=True,
                width="stretch",
                height=220,
            )

    st.divider()

    # -----------------------------------------------------------------------
    # Cálculos principais
    # -----------------------------------------------------------------------
    if not selecionados:
        st.warning(
            "Selecione ao menos um título na seção **Títulos a Comparar** acima para ver a análise completa.",
            icon="👆",
        )
        return

    titulos_sel = [t for t in catalogo if t["nome"] in selecionados]
    analises = [
        _analise_cached(
            nome=t["nome"],
            tipo=t["tipo"],
            taxa=t["taxa"],
            anos_total=t["anos_total"],
            anos_saida=H,
            ipca=ipca_pct,
            choque=choque_pp,
            com_ir=com_ir,
            selic=selic_pct,
        )
        for t in titulos_sel
    ]

    vencedor = _winner_por_perfil(analises, perfil)
    aliq_str = f"{aliquota_ir_renda_fixa(H) * 100:.1f}%" if com_ir else "bruto"

    # Carteira Mista: só para perfil Moderado (Conservador e Arrojado não misturam)
    selic_analise = next((a for a in analises if a["tipo"] == "selic"), None)
    if perfil == "Moderado" and selic_analise and vencedor["tipo"] != "selic":
        mix = carteira_mista(vencedor, selic_analise, peso_principal=0.70)
    else:
        mix = None

    # Monte Carlo para fronteira eficiente real
    portfolios_mc = gerar_portfolios_aleatorios(analises, n=400)

    # -----------------------------------------------------------------------
    # Mensagens Adaptativas por Cenário
    # -----------------------------------------------------------------------
    _todos_tipos = {a["tipo"] for a in analises}
    _exposicoes = [a["anos_expo"] for a in analises if a["tipo"] != "selic"]
    _alta_expo = sum(1 for e in _exposicoes if e > 3)

    if horizonte <= 2 and _alta_expo == len(_exposicoes) and _exposicoes:
        st.warning(
            f"⚠️ **Horizonte curto ({horizonte} ano(s)) + todos os títulos selecionados têm alta exposição ao MaM.** "
            "Considere adicionar o **Tesouro Selic** à comparação — é o único título sem risco de "
            "Marcação a Mercado para prazos curtos.",
            icon="⚡",
        )
    elif ipca_pct > selic_pct:
        st.warning(
            f"📉 **Selic real negativa:** com IPCA projetado em {ipca_pct:.1f}% e Selic em {selic_pct:.2f}%, "
            "o Tesouro Selic **perde poder de compra**. "
            "O Tesouro IPCA+ é mais indicado para preservar o valor real do patrimônio neste cenário.",
            icon="🌡️",
        )
    elif horizonte > 7 and "selic" in _todos_tipos and len(_todos_tipos) == 1:
        st.info(
            f"💡 **Horizonte longo ({horizonte} anos) com apenas Selic selecionado.** "
            "Para prazos acima de 5 anos, títulos com taxa **travada** (IPCA+ ou Prefixado) "
            "costumam entregar retorno real superior ao Selic. Adicione um IPCA+ à comparação.",
            icon="🔍",
        )
    elif len(_todos_tipos) == 1 and "ipca_mais" in _todos_tipos and horizonte <= 3:
        st.info(
            f"💡 **Apenas títulos IPCA+ selecionados para {horizonte} ano(s).** "
            "Para horizontes curtos, IPCA+ pode ter risco significativo de MaM. "
            "Considere comparar com o **Tesouro Selic** como alternativa sem volatilidade de preço.",
            icon="🔍",
        )

    # Aviso: fórmula de saída antecipada é aproximação para títulos com cupons semestrais
    _cupom_selecionados = [
        a["nome"] for a in analises if "Juros Semestrais" in a["nome"]
    ]
    if _cupom_selecionados:
        _nomes_cupom = ", ".join(n.replace("Tesouro ", "") for n in _cupom_selecionados)
        st.info(
            f"**{_nomes_cupom}** paga(m) cupons semestrais durante o período de holding. "
            "O retorno exibido captura apenas o **efeito de preço** (variação do PU quando a taxa muda) — "
            "os cupons recebidos ao longo do caminho não estão computados. "
            "O retorno total real desses títulos é **maior** do que os valores mostrados. "
            "Use os números para comparar o risco de Marcação a Mercado, não como retorno total.",
            icon="ℹ️",
        )

    # -----------------------------------------------------------------------
    # Semáforo de Risco
    # -----------------------------------------------------------------------
    ir_label = " (líquido de IR)" if com_ir else ""
    st.subheader(
        f":material/bar_chart:  Análise para Horizonte de {horizonte} Ano(s){ir_label}"
    )

    cols = st.columns(min(len(analises), 6))
    for col, a in zip(cols, analises):
        nome_curto = a["nome"].replace("Tesouro ", "")
        venc_date = next(
            t["vencimento"].strftime("%d/%m/%Y")
            for t in titulos_sel
            if t["nome"] == a["nome"]
        )
        with col:
            st.metric(
                label=f"{nome_curto}{' 🏆' if a['nome'] == vencedor['nome'] else ''}",
                value=f"{a['ret_neu']:.2f}% a.a.",
                delta=a["risco_label"],
                delta_color="off",
                help=f"Venc: {venc_date} · {a['anos_expo']:.1f}a de exposição MaM",
            )
            st.caption(
                f"Adv: **{a['ret_adv']:.1f}%** · "
                f"Fav: **{a['ret_fav']:.1f}%** · "
                f"Real: **{a['ret_real']:.1f}%**"
            )
            vf_neu = capital * (1 + a["ret_neu"] / 100) ** H
            st.markdown(
                f"<div style='margin-top:0.4rem; padding:0.45rem 0.6rem; "
                f"background:#0e1c12; border-left:3px solid #38A169; border-radius:4px;'>"
                f"<span style='font-size:0.7rem; color:#718096;'>resgate estimado (neutro)</span><br>"
                f"<span style='font-size:0.72rem; color:#a0aec0;'>{formatar_brl(capital)}</span>"
                f"<span style='font-size:0.8rem; color:#718096;'> → </span>"
                f"<span style='font-size:0.95rem; font-weight:700; color:#68D391;'>{formatar_brl(vf_neu)}</span>"
                f"</div>",
                unsafe_allow_html=True,
            )

    if len(analises) > 6:
        st.caption(
            f"Mostrando os primeiros 6 de {len(analises)} títulos selecionados nos cards acima."
        )

    st.divider()

    # -----------------------------------------------------------------------
    # Fronteira de Markowitz + Barras de Cenário
    # -----------------------------------------------------------------------
    col_g1, col_g2 = st.columns(2)
    with col_g1:
        st.plotly_chart(
            grafico_markowitz(analises, carteira_mix=mix, portfolios_mc=portfolios_mc),
            width="stretch",
            theme=None,
        )
    with col_g2:
        st.plotly_chart(grafico_cenarios_batalha(analises), width="stretch", theme=None)

    # -----------------------------------------------------------------------
    # Análise por Horizonte
    # -----------------------------------------------------------------------
    st.divider()
    st.subheader(
        ":material/trending_up:  Qual Título Performa Melhor em Cada Horizonte?"
    )
    st.caption(
        "Retorno neutro esperado para cada título em diferentes horizontes de saída. "
        "A banda sombreada mostra o intervalo entre o cenário adverso e favorável."
    )

    _HORIZONS = [1, 2, 3, 5, 7, 10, 15]
    _res_horizonte: dict = {}
    for _h in _HORIZONS:
        _res_horizonte[_h] = [
            _analise_cached(
                nome=t["nome"],
                tipo=t["tipo"],
                taxa=t["taxa"],
                anos_total=t["anos_total"],
                anos_saida=float(_h),
                ipca=ipca_pct,
                choque=choque_pp,
                com_ir=com_ir,
                selic=selic_pct,
            )
            for t in titulos_sel
        ]

    st.plotly_chart(
        grafico_retorno_por_horizonte(_res_horizonte, horizonte),
        width="stretch",
        theme=None,
    )
    st.caption(
        "Linha sólida: título ainda em carrego — taxa original garantida. "
        "Linha tracejada (···): título já venceu nesse horizonte — retorno é uma mistura da taxa original "
        "até o vencimento + Selic pelo período restante. "
        "Pontos de cruzamento revelam quando um título passa a ser melhor que outro."
    )

    st.divider()

    # -----------------------------------------------------------------------
    # Recomendação
    # -----------------------------------------------------------------------
    st.subheader(":material/flag:  Recomendação")
    st.caption(
        f"Critério ativo: {_PERFIL_EMOJI[perfil]} **{perfil}** — "
        + (
            "minimiza risco de MaM"
            if perfil == "Conservador"
            else "maximiza retorno no cenário favorável"
            if perfil == "Arrojado"
            else "melhor relação retorno/risco (Sharpe)"
        )
    )
    st.markdown(
        f'<div class="badge-seguranca">💡 {_insight_texto(vencedor, horizonte, ipca_pct, com_ir)}</div>',
        unsafe_allow_html=True,
    )

    # -----------------------------------------------------------------------
    # Carteira Mista Otimizada (3.2)
    # -----------------------------------------------------------------------
    if mix:
        st.markdown("#### Carteira Mista Otimizada — Asset Allocation de Renda Fixa")

        nome_p = mix["nome_principal"].replace("Tesouro ", "")
        nome_l = mix["nome_liquida"].replace("Tesouro ", "")
        wp_pct = int(mix["peso_principal"] * 100)
        wl_pct = int(mix["peso_liquida"] * 100)

        col_mix1, col_mix2, col_mix3, col_mix4 = st.columns(4)
        with col_mix1:
            st.metric(
                "Alocação Principal",
                f"{wp_pct}%  {nome_p}",
                f"Retorno neutro: {vencedor['ret_neu']:.2f}% a.a.",
            )
        with col_mix2:
            st.metric(
                "Alocação Liquidez",
                f"{wl_pct}%  {nome_l}",
                f"Retorno neutro: {selic_analise['ret_neu']:.2f}% a.a.",
            )
        with col_mix3:
            st.metric(
                "Retorno Mix (neutro)",
                f"{mix['ret_neu']:.2f}% a.a.",
                f"Adv: {mix['ret_adv']:.1f}% · Fav: {mix['ret_fav']:.1f}%",
            )
        with col_mix4:
            reducao_risco = vencedor["risco_std"] - mix["risco_std"]
            st.metric(
                "Redução de Risco (σ)",
                f"{mix['risco_std']:.3f}%",
                f"−{reducao_risco:.3f}% vs. 100% {nome_p}",
            )

        st.markdown(
            f'<div class="badge-seguranca">'
            f"⭐ <strong>Carteira Mista sugerida:</strong> "
            f"<strong>{wp_pct}% {nome_p}</strong> (oportunidade/retorno) + "
            f"<strong>{wl_pct}% {nome_l}</strong> (liquidez/reserva). "
            f"O ponto ⭐ no gráfico de Markowitz acima demonstra que essa combinação "
            f"reduz a dispersão de cenários em <strong>{reducao_risco:.3f} p.p.</strong> "
            f"mantendo retorno competitivo de <strong>{mix['ret_neu']:.2f}% a.a.</strong>. "
            f"Inclua um Tesouro Selic na seleção para ativar essa análise."
            f"</div>",
            unsafe_allow_html=True,
        )
    elif vencedor["tipo"] != "selic":
        st.caption(
            "💡 Adicione um **Tesouro Selic** na seleção acima para ver a "
            "sugestão de Carteira Mista Otimizada (70/30)."
        )

    st.divider()

    # -----------------------------------------------------------------------
    # Tabela Comparativa
    # -----------------------------------------------------------------------
    st.subheader(":material/table_rows:  Detalhamento Completo")

    linhas = []
    for a in analises:
        venc_str = next(
            t["vencimento"].strftime("%d/%m/%Y")
            for t in titulos_sel
            if t["nome"] == a["nome"]
        )
        score = a["ret_neu"] / max(a["risco_std"], 0.01)
        linhas.append(
            {
                "Título": a["nome"].replace("Tesouro ", "")
                + (" 🏆" if a["nome"] == vencedor["nome"] else ""),
                "Vencimento": venc_str,
                "Retorno Neutro": a["ret_neu"],
                "Retorno Adverso": a["ret_adv"],
                "Retorno Favorável": a["ret_fav"],
                "Ganho Real (%)": a["ret_real"],
                "Valor Final (R$)": capital * (1 + a["ret_neu"] / 100) ** H,
                "Risco (σ)": a["risco_std"],
                "Score": score,
                "Exposição MaM": a["risco_label"],
            }
        )

    df_tab = pd.DataFrame(linhas)
    idx_vencedor = next(
        i for i, a in enumerate(analises) if a["nome"] == vencedor["nome"]
    )

    def _cor(row):
        if row.name == idx_vencedor:
            return ["background-color: #2d2310; color: #fbd38d"] * len(row)
        return ["background-color: #1C2331; color: #FAFAFA"] * len(row)

    pct_cols = [
        "Retorno Neutro",
        "Retorno Adverso",
        "Retorno Favorável",
        "Ganho Real (%)",
        "Risco (σ)",
    ]
    fmt = {c: lambda v: f"{v:+.2f}%" for c in pct_cols}
    fmt["Valor Final (R$)"] = lambda v: f"R$ {v:,.0f}".replace(",", ".")
    fmt["Score"] = lambda v: f"{v:.2f}"

    styled = df_tab.style.apply(_cor, axis=1).format(fmt)
    st.dataframe(styled, width="stretch", hide_index=True)

    vf_neutro = capital * (1 + vencedor["ret_neu"] / 100) ** horizonte
    st.info(
        f"💵 **{formatar_brl(capital)}** em **{vencedor['nome'].replace('Tesouro ', '')}** "
        f"por {horizonte} ano(s) → **{formatar_brl(vf_neutro)}** no cenário neutro "
        f"({vencedor['ret_neu']:.2f}% a.a. · IR {aliq_str})",
        icon="📈",
    )

    ir_nota = (
        f"IR {aliquota_ir_renda_fixa(H) * 100:.1f}% aplicado sobre o lucro nominal."
        if com_ir
        else "Cálculo bruto (sem IR)."
    )
    st.caption(
        f"⚠️ {ir_nota} Não considera IOF nem corretagem. "
        "Taxas Prefixado são referências — confira os valores atuais no Tesouro Direto. "
        "RendA+ e Educar+ têm regras específicas de IR na fase de renda (simplificado aqui)."
    )

    # -----------------------------------------------------------------------
    # Persiste preferências
    # -----------------------------------------------------------------------
    salvar(
        {
            "bat_horizonte": st.session_state.get("bat_horizonte", 3),
            "bat_capital": st.session_state.get("bat_capital", 10_000.0),
            "bat_com_ir": st.session_state.get("bat_com_ir", True),
            "bat_ipca": st.session_state.get("bat_ipca", 5.0),
            "bat_selic": st.session_state.get("bat_selic", 14.75),
            "bat_choque": st.session_state.get("bat_choque", 1.0),
            "bat_selecionados": st.session_state.get("bat_selecionados", _DEFAULTS),
            "bat_perfil": st.session_state.get("bat_perfil", "Moderado"),
        }
    )
