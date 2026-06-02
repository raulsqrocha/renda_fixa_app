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

st.sidebar.markdown(
    """
<div style="margin-bottom:1.2rem; padding-bottom:1rem; border-bottom:1px solid #2D3748;">
    <span style="font-size:0.72rem; font-weight:600; letter-spacing:0.08em;
                 color:#38A169; text-transform:uppercase;">Protótipo</span><br>
    <span style="font-size:1.05rem; font-weight:700; color:#FAFAFA;">Renda Fixa CF</span><br>
    <span style="font-size:0.72rem; color:#718096; letter-spacing:0.02em;">por Raul Rocha</span>
</div>
""",
    unsafe_allow_html=True,
)

pg = st.navigation(
    [
        st.Page(
            "pages/0_Dashboard.py",
            title="Minha Carteira",
            icon=":material/account_balance_wallet:",
            default=True,
        ),
        st.Page(
            "pages/1_Qual_Ativo.py",
            title="Qual Ativo Escolher?",
            icon=":material/help:",
        ),
        st.Page(
            "pages/2_Comparar_Produtos.py",
            title="Comparar Produtos",
            icon=":material/bar_chart:",
        ),
        st.Page(
            "pages/3_Simulador_MaM.py",
            title="Simulador Avançado (MaM)",
            icon=":material/show_chart:",
        ),
    ]
)

with st.sidebar:
    st.page_link(
        "pages/0_Dashboard.py",
        label="Minha Carteira",
        icon=":material/account_balance_wallet:",
    )
    st.page_link(
        "pages/1_Qual_Ativo.py", label="Qual Ativo Escolher?", icon=":material/help:"
    )
    st.page_link(
        "pages/2_Comparar_Produtos.py",
        label="Comparar Produtos",
        icon=":material/bar_chart:",
    )
    st.page_link(
        "pages/3_Simulador_MaM.py",
        label="Simulador Avançado (MaM)",
        icon=":material/show_chart:",
    )
    st.markdown(
        "<hr style='border-color:#2D3748; margin:0.8rem 0;'>", unsafe_allow_html=True
    )

pg.run()
