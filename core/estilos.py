"""CSS global compartilhado entre todas as páginas do app."""

import streamlit as st
from core.financas import formatar_brl

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Hero Banner ───────────────────────────────────────────────────── */
.hero-banner {
    background: linear-gradient(135deg, #0D1117 0%, #152238 55%, #0D1117 100%);
    border: 1px solid #2D3748;
    border-radius: 16px;
    padding: 1.6rem 2rem;
    margin-bottom: 1.5rem;
    display: flex;
    align-items: center;
    justify-content: space-between;
    gap: 1rem;
}
.hero-tag {
    font-size: 0.7rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    color: #38A169;
    text-transform: uppercase;
    margin-bottom: 0.3rem;
}
.hero-title {
    font-size: 1.9rem;
    font-weight: 700;
    color: #FAFAFA;
    line-height: 1.15;
    margin: 0 0 0.4rem 0;
}
.hero-title span { color: #38A169; }
.hero-subtitle {
    font-size: 0.92rem;
    color: #718096;
    margin: 0;
    max-width: 520px;
}
.hero-badge {
    background: rgba(56,161,105,0.10);
    border: 1px solid rgba(56,161,105,0.30);
    border-radius: 50px;
    padding: 0.55rem 1.1rem;
    font-size: 0.82rem;
    color: #68D391;
    white-space: nowrap;
    flex-shrink: 0;
}

/* ── Metric Cards — fade-in animado ────────────────────────────────── */
@keyframes fadeSlideUp {
    from { opacity: 0; transform: translateY(14px); }
    to   { opacity: 1; transform: translateY(0);    }
}
[data-testid="metric-container"] {
    background-color: #1C2331;
    border: 1px solid #2D3748;
    border-radius: 12px;
    padding: 1rem 1.2rem;
    animation: fadeSlideUp 0.45s ease both;
}

/* ── Alertas e Badges ──────────────────────────────────────────────── */
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

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #0D1117;
    border-right: 1px solid #21262D;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #8B949E;
}

.block-container { padding-top: 3.5rem; }

hr { border-color: #2D3748 !important; }
</style>
"""


def aplicar_estilo_global() -> None:
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_info() -> None:
    with st.sidebar:
        # Branding
        st.markdown("""
<div style="margin-bottom:1.2rem; padding-bottom:1rem; border-bottom:1px solid #2D3748;">
    <span style="font-size:0.72rem; font-weight:600; letter-spacing:0.08em;
                 color:#38A169; text-transform:uppercase;">Protótipo</span><br>
    <span style="font-size:1.05rem; font-weight:700; color:#FAFAFA;">Renda Fixa CF</span>
</div>
""", unsafe_allow_html=True)

        # Mini-resumo da posição — populado pelo Dashboard após o primeiro render
        pos = st.session_state.get("_dash_pos")
        if pos:
            score     = pos["score"]
            cor_score = "#38A169" if score >= 70 else "#ECC94B" if score >= 40 else "#E53E3E"
            data_v    = pos["data_venc"].strftime("%d/%m/%Y")
            st.markdown(f"""
<div style="background:#1C2331; border:1px solid #2D3748; border-radius:10px;
            padding:0.8rem 1rem; margin-bottom:1.2rem;">
  <div style="font-size:0.68rem; color:#38A169; text-transform:uppercase;
              letter-spacing:0.08em; margin-bottom:0.45rem; font-weight:600;">Sua Posição</div>
  <div style="font-size:0.8rem; color:#FAFAFA; font-weight:600;
              margin-bottom:0.55rem; line-height:1.3;">{pos['titulo'][:32]}</div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.2rem;">
    <span style="color:#718096;">MaM Hoje</span>
    <span style="color:#FAFAFA;">{formatar_brl(pos['mam'])}</span>
  </div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.2rem;">
    <span style="color:#718096;">No Vencimento</span>
    <span style="color:#38A169;">{formatar_brl(pos['carrego'])}</span>
  </div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.55rem;">
    <span style="color:#718096;">Vence em</span>
    <span style="color:#FAFAFA;">{data_v}</span>
  </div>
  <div style="background:#0E1117; border-radius:4px; height:5px; margin-bottom:0.2rem;">
    <div style="background:{cor_score}; width:{score:.0f}%; height:5px; border-radius:4px;"></div>
  </div>
  <div style="font-size:0.68rem; color:#718096;">Serenidade: {score:.0f}/100</div>
</div>
""", unsafe_allow_html=True)

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
