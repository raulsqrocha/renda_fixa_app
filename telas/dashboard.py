"""
Tela 1 — Seu Dashboard

Objetivo psicológico: mostrar o contraste entre a volatilidade percebida (MaM)
e a segurança real (carrego até o vencimento) para combater o viés do presente.
"""

import streamlit as st
import pandas as pd
from datetime import date, timedelta

from core.financas import (
    datas_cupom_ntnb,
    pu_ntnb,
    metricas_carteira,
    serie_paradoxo,
    formatar_brl,
)
from core.dados import obter_dados_completos, CATEGORIAS_TITULOS, TITULOS_CONFIG
from core.graficos import grafico_paradoxo


# Cache da série do paradoxo — evita recálculo a cada interação de widget
@st.cache_data(ttl=3600 * 6, show_spinner=False)
def _serie_cached(vna, taxa_contratada, taxa_mercado, compra, vencimento, qtd, tem_cupom):
    return serie_paradoxo(vna, taxa_contratada, taxa_mercado, compra, vencimento, qtd, tem_cupom)


def render():
    # -----------------------------------------------------------------------
    # Cabeçalho
    # -----------------------------------------------------------------------
    st.markdown(
        '<p class="titulo-principal">Seu Dashboard</p>'
        '<p class="subtitulo">Visualize o paradoxo da renda fixa: a volatilidade que você '
        '<em>sente</em> versus a segurança que você <em>tem</em>.</p>',
        unsafe_allow_html=True,
    )

    with st.spinner("Carregando dados do Tesouro Direto e BCB..."):
        df_ipca, df_titulos, vna = obter_dados_completos()

    # Indicador de fonte dos dados
    fonte = "✅ Dados ao vivo — Tesouro Direto" if not df_titulos.empty else "⚠️ Modo offline — dados de referência"
    st.caption(fonte)
    st.divider()

    # -----------------------------------------------------------------------
    # Configuração da posição
    # -----------------------------------------------------------------------
    st.subheader("⚙️  Configure sua posição")

    col_a, col_a2, col_b, col_c, col_d = st.columns([1.5, 1.5, 1, 1, 1])

    with col_a:
        categoria_sel = st.selectbox(
            "Categoria",
            options=list(CATEGORIAS_TITULOS.keys()),
            help="Selecione a família do título Tesouro",
        )

    with col_a2:
        titulo_sel = st.selectbox(
            "Vencimento",
            options=CATEGORIAS_TITULOS[categoria_sel],
            help="Selecione o ano de vencimento do título",
        )

    with col_b:
        valor_investido = st.number_input(
            "Valor Investido (R$)",
            min_value=30.0, max_value=1_000_000.0,
            value=10_000.0, step=500.0, format="%.2f",
        )

    with col_c:
        taxa_contratada_pct = st.number_input(
            "Taxa Contratada (% a.a. real)",
            min_value=1.0, max_value=15.0,
            value=5.50, step=0.05, format="%.2f",
            help="Taxa real IPCA+ que você travou na data da compra",
        )

    with col_d:
        data_compra = st.date_input(
            "Data de Compra",
            value=date.today() - timedelta(days=365 * 2),
            max_value=date.today() - timedelta(days=1),
        )

    st.divider()

    # -----------------------------------------------------------------------
    # Resolve dados do título selecionado
    # -----------------------------------------------------------------------
    linha = df_titulos[df_titulos["nome"] == titulo_sel] if not df_titulos.empty else pd.DataFrame()

    if not linha.empty:
        taxa_mercado_pct = float(linha["taxa_compra"].values[0])
        data_vencimento  = date.fromisoformat(str(linha["vencimento"].values[0])[:10])
    else:
        # Fallback: usa TITULOS_CONFIG para vencimento e simula taxa 200 bps acima da contratada
        cfg_titulo       = TITULOS_CONFIG.get(titulo_sel, {})
        taxa_mercado_pct = taxa_contratada_pct + 2.0
        data_vencimento  = cfg_titulo.get("vencimento", date(2035, 5, 15))

    taxa_contratada = taxa_contratada_pct / 100
    taxa_mercado    = taxa_mercado_pct    / 100

    # Determina se o título paga cupons semestrais pelo nome
    tem_cupom = "Juros Semestrais" in titulo_sel

    # Valida: data de compra não pode ser após o vencimento
    if data_compra >= data_vencimento:
        st.error("⛔ A data de compra deve ser anterior ao vencimento do título.")
        return

    # PU na data de compra — base para calcular quantidade de títulos
    # Títulos Principal passam lista vazia: sem fluxo de cupons intermediários
    cpns_compra = datas_cupom_ntnb(data_compra, data_vencimento) if tem_cupom else []
    pu_compra   = pu_ntnb(vna, taxa_contratada, data_compra, data_vencimento, cpns_compra)

    if pu_compra <= 0:
        st.error("Não foi possível calcular o PU na data de compra. Verifique os parâmetros.")
        return

    # Métricas do dia com cupons futuros a partir de hoje
    cpns_hoje = datas_cupom_ntnb(date.today(), data_vencimento) if tem_cupom else []
    resultado = metricas_carteira(
        valor_investido=valor_investido,
        pu_na_compra=pu_compra,
        taxa_real_contratada=taxa_contratada,
        taxa_real_mercado=taxa_mercado,
        vna=vna,
        data_hoje=date.today(),
        data_vencimento=data_vencimento,
        datas_cupom=cpns_hoje,
    )

    # round() evita truncamento de piso (ex: 2.98 anos → 3, não 2)
    anos_restantes = max(1, round((data_vencimento - date.today()).days / 365))

    # Projeção do vencimento: Capital × (1 + r)^anos_totais contratados
    # Usa anos_totais (compra → vencimento) para refletir o contrato integral firmado
    anos_totais      = (data_vencimento - data_compra).days / 365
    valor_vencimento = valor_investido * (1 + taxa_contratada) ** anos_totais

    # -----------------------------------------------------------------------
    # Cards de KPI
    # -----------------------------------------------------------------------
    st.subheader("📊  Situação da Carteira")

    col1, col2, col3 = st.columns(3)
    variacao = resultado["variacao_dia"]

    with col1:
        st.metric(
            label="Variação do Dia (MaM)",
            value=f"{variacao:+.2f}%",
            delta=f"{variacao:.2f}%",
            delta_color="normal",
            help="Oscilação estimada do Preço Unitário de mercado hoje vs. ontem",
        )

    with col2:
        delta_vs_investido = resultado["mam"] - valor_investido
        # O sinal deve ser o primeiro caractere para o Streamlit detectar a cor corretamente
        if delta_vs_investido < 0:
            delta_mam_str = f"-{formatar_brl(abs(delta_vs_investido))} vs. capital investido"
        else:
            delta_mam_str = f"+{formatar_brl(delta_vs_investido)} vs. capital investido"
        st.metric(
            label="💸  Resgate Antecipado Hoje",
            value=formatar_brl(resultado['mam']),
            delta=delta_mam_str,
            delta_color="normal",
            help="Valor que você receberia se vender hoje — sujeito à Marcação a Mercado",
        )

    with col3:
        ganho_real_pct = (valor_vencimento / valor_investido - 1) * 100
        if "RendA+" in titulo_sel:
            label_venc = "🏦  Capital Acumulado (RendA+)"
            help_venc  = (
                f"Capital estimado acumulado até {data_vencimento.strftime('%d/%m/%Y')}, "
                f"quando iniciam os pagamentos mensais por 20 anos. "
                f"Taxa contratada: {taxa_contratada_pct:.2f}% a.a. real."
            )
        elif "Educar+" in titulo_sel:
            label_venc = "🎓  Capital Acumulado (Educar+)"
            help_venc  = (
                f"Capital estimado acumulado até {data_vencimento.strftime('%d/%m/%Y')}, "
                f"quando iniciam os pagamentos mensais por 5 anos (60 parcelas). "
                f"Taxa contratada: {taxa_contratada_pct:.2f}% a.a. real."
            )
        else:
            label_venc = "🛡️  Resgate no Vencimento"
            help_venc  = (
                f"Valor estimado em {data_vencimento.strftime('%d/%m/%Y')} pela taxa contratada "
                f"de {taxa_contratada_pct:.2f}% a.a. — imune às oscilações de mercado"
            )
        st.metric(
            label=label_venc,
            value=formatar_brl(valor_vencimento),
            delta=f"+{ganho_real_pct:.1f}% real acumulado",
            delta_color="normal",
            help=help_venc,
        )

    # Banner explicativo — aparece quando MaM < capital investido
    if resultado["mam"] < valor_investido:
        st.markdown("""
        <div class="alerta-mercado">
            ⚠️ <strong>Por que minha carteira aparece "negativa"?</strong><br>
            <small>
            A Marcação a Mercado (MaM) reflete o preço que o mercado pagaria <em>agora</em> pelo
            seu título. Quando as taxas de juros sobem, esse preço cai — mas isso não afeta em nada
            o que você receberá no vencimento. Se você <strong>não vender antes</strong>, receberá
            exatamente a taxa real que contratou, corrigida pelo IPCA, independente de qualquer
            oscilação pelo caminho.
            </small>
        </div>
        """, unsafe_allow_html=True)
    else:
        st.markdown("""
        <div class="badge-seguranca">
            ✅ <strong>Sua posição está acima do capital investido.</strong><br>
            <small>
            As taxas de juros caíram desde sua compra, valorizando seu título no mercado secundário.
            Você pode resgatar antecipadamente com ganho — ou manter até o vencimento para receber
            a taxa contratada integralmente.
            </small>
        </div>
        """, unsafe_allow_html=True)

    st.divider()

    # -----------------------------------------------------------------------
    # Gráfico do Paradoxo
    # -----------------------------------------------------------------------
    st.subheader("📈  O Gráfico do Paradoxo")

    col_graf, col_legenda = st.columns([3, 1])

    with st.spinner("Calculando série temporal..."):
        df_paradoxo = _serie_cached(
            vna, taxa_contratada, taxa_mercado,
            data_compra, data_vencimento, resultado["quantidade"], tem_cupom,
        )

    with col_graf:
        fig = grafico_paradoxo(df_paradoxo)
        st.plotly_chart(fig, use_container_width=True)

    with col_legenda:
        st.markdown("### O que estou vendo?")
        padrao_carrego = (
            "Oscila em **dente de serra** a cada semestre — reflexo dos cupons pagos."
            if tem_cupom
            else "Curva **exponencial lisa** — sem cupons intermediários."
        )
        st.markdown(f"""
**🔴 Linha Vermelha — MaM**
Preço de mercado dia a dia. Oscila com as expectativas de juros futuros (DI Futuro).
É o que você recebe **se vender hoje**.

---

**🟢 Linha Verde — Carrego**
Trajetória pela taxa real de **{taxa_contratada_pct:.2f}% a.a.** que você contratou.
{padrao_carrego}
É o que você recebe **se aguardar {data_vencimento.strftime('%d/%m/%Y')}**.

---

ℹ️ As duas linhas **convergem no vencimento** — no prazo final, o mercado precifica o
título pelo seu valor intrínseco (VNA + cupons acumulados), eliminando qualquer divergência.
        """)

    # Rodapé informativo
    st.info(
        f"📅 **Vencimento:** {data_vencimento.strftime('%d/%m/%Y')}  ·  "
        f"**Anos restantes:** {anos_restantes}  ·  "
        f"**VNA estimado (BCB):** {formatar_brl(vna)}  ·  "
        f"**Taxa de mercado:** {taxa_mercado_pct:.2f}% a.a. real  ·  "
        f"**Quantidade:** {resultado['quantidade']:.4f} títulos",
    )
