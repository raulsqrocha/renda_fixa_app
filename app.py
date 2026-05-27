"""
Renda Fixa — Marcação a Mercado
Entrypoint do app: configura a página e registra a navegação explicitamente.

Páginas:
  pages/0_Dashboard.py    → Tela 1: Dashboard Principal
  pages/1_Qual_Ativo.py   → Tela 2: Qual Ativo Escolher?
  pages/2_Simulador_MaM.py → Tela 3: Simulador Avançado (MaM)
  pages/3_Comparar_Produtos.py → Tela 4: Comparar Produtos
"""

import streamlit as st
from core.estilos import aplicar_estilo_global

st.set_page_config(
    page_title="Renda Fixa | Marcação a Mercado",
    page_icon=":material/analytics:",
    layout="wide",
    initial_sidebar_state="expanded",
)

aplicar_estilo_global()

pg = st.navigation([
    st.Page("pages/0_Dashboard.py",          title="Minha Carteira",            icon=":material/account_balance_wallet:", default=True),
    st.Page("pages/1_Qual_Ativo.py",         title="Qual Ativo Escolher?",      icon=":material/help:"),
    st.Page("pages/2_Comparar_Produtos.py",  title="Comparar Produtos",         icon=":material/bar_chart:"),
    st.Page("pages/3_Simulador_MaM.py",      title="Simulador Avançado (MaM)",  icon=":material/show_chart:"),
])

pg.run()
