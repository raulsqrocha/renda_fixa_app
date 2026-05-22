"""
Renda Fixa — Marcação a Mercado
Aplicativo Streamlit sobre Finanças Comportamentais e Tesouro IPCA+

Estrutura:
  app.py          → entrada, CSS global, roteamento da sidebar
  core/financas   → fórmulas de precificação NTN-B
  core/dados      → acesso às APIs (BCB, Tesouro Direto) com cache inteligente
  core/graficos   → visualizações Plotly
  telas/dashboard → Tela 1: carteira e gráfico do paradoxo
  telas/simulador → Tela 2: cenários de inflação, DI Futuro, IPCA histórico
"""

import streamlit as st
from telas import dashboard, simulador, batalha

st.set_page_config(
    page_title="Renda Fixa | Marcação a Mercado",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ---------------------------------------------------------------------------
# CSS Global
# ---------------------------------------------------------------------------
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* Títulos das telas */
.titulo-principal {
    font-size: 1.9rem;
    font-weight: 700;
    color: #FAFAFA;
    margin-bottom: 0.15rem;
    line-height: 1.2;
}
.subtitulo {
    font-size: 0.95rem;
    color: #718096;
    margin-bottom: 1.5rem;
}

/* Cards de métricas */
[data-testid="metric-container"] {
    background-color: #1C2331;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 1rem 1.2rem;
}

/* Banner de alerta MaM (vermelho) */
.alerta-mercado {
    background: linear-gradient(135deg, #1a0808, #2d1515);
    border: 1px solid #E53E3E;
    border-left: 4px solid #E53E3E;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 0.8rem 0;
    font-size: 0.92rem;
}

/* Badge de segurança (verde) */
.badge-seguranca {
    background: linear-gradient(135deg, #081a0a, #152d18);
    border: 1px solid #38A169;
    border-left: 4px solid #38A169;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 0.8rem 0;
    font-size: 0.92rem;
}

/* Sidebar */
[data-testid="stSidebar"] {
    background-color: #0D1117;
    border-right: 1px solid #21262D;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #8B949E;
}

/* Remove padding excessivo do topo */
.block-container {
    padding-top: 2rem;
}

/* Divisor */
hr { border-color: #2D3748 !important; }
</style>
""", unsafe_allow_html=True)

# ---------------------------------------------------------------------------
# Sidebar — Navegação
# ---------------------------------------------------------------------------
with st.sidebar:
    st.markdown("## 📊 Renda Fixa")
    st.markdown("*Finanças Comportamentais*  \n*& Marcação a Mercado*")
    st.divider()

    pagina = st.radio(
        "Navegação",
        options=["🏠   Seu Dashboard", "🔬   Simulador Avançado (MaM)", "🎯   Qual ativo escolher?"],
        label_visibility="collapsed",
    )

    st.divider()

    st.markdown("""
**Sobre os dados**

🏦 Preços: Tesouro Direto
📈 IPCA: Banco Central (SGS 433)
🔄 Atualização: diária, às 14h BRT

---

**Sobre o VNA**

Calculado via BCB (aproximação).
Para o VNA oficial ANBIMA, configure
as credenciais em `secrets.toml`.

---
    """)

    st.caption("v1.0 · Streamlit · Plotly")

# ---------------------------------------------------------------------------
# Roteamento
# ---------------------------------------------------------------------------
if "Dashboard" in pagina:
    dashboard.render()
elif "Simulador" in pagina:
    simulador.render()
else:
    batalha.render()
