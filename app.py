"""
Renda Fixa — Marcação a Mercado
Entrypoint do app: configura a página e registra a navegação explicitamente.

Páginas:
  pages/0_Dashboard.py     → Tela 1: Dashboard Principal
  pages/1_Simulador_MaM.py → Tela 2: Simulador Avançado (MaM)
  pages/2_Qual_Ativo.py    → Tela 3: Fronteira de Markowitz e Recomendações
"""

import streamlit as st
from core.estilos import aplicar_estilo_global

st.set_page_config(
    page_title="Renda Fixa | Marcação a Mercado",
    page_icon="📊",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilo_global()

pg = st.navigation([
    st.Page("pages/0_Dashboard.py",     title="🏠  Seu Dashboard",            default=True),
    st.Page("pages/1_Simulador_MaM.py", title="🔬  Simulador Avançado (MaM)"),
    st.Page("pages/2_Qual_Ativo.py",    title="🎯  Qual Ativo Escolher?"),
])

pg.run()
