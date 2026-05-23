"""CSS global compartilhado entre todas as páginas do app."""

import streamlit as st

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

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

[data-testid="metric-container"] {
    background-color: #1C2331;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 1rem 1.2rem;
}

.alerta-mercado {
    background: linear-gradient(135deg, #1a0808, #2d1515);
    border: 1px solid #E53E3E;
    border-left: 4px solid #E53E3E;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 0.8rem 0;
    font-size: 0.92rem;
}

.badge-seguranca {
    background: linear-gradient(135deg, #081a0a, #152d18);
    border: 1px solid #38A169;
    border-left: 4px solid #38A169;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 0.8rem 0;
    font-size: 0.92rem;
}

[data-testid="stSidebar"] {
    background-color: #0D1117;
    border-right: 1px solid #21262D;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #8B949E;
}

.block-container {
    padding-top: 2rem;
}

hr { border-color: #2D3748 !important; }
</style>
"""


def aplicar_estilo_global() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_info() -> None:
    with st.sidebar:
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
