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

/* ── Títulos das páginas secundárias ────────────────────────────────── */
.titulo-principal {
    font-size: 1.75rem;
    font-weight: 700;
    color: #FAFAFA;
    line-height: 1.2;
    margin: 0 0 0.35rem 0;
}
.subtitulo {
    font-size: 0.92rem;
    color: #718096;
    margin: 0 0 1.2rem 0;
    max-width: 620px;
}
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

        # ── Contexto da página ativa ────────────────────────────────────
        page_id = st.session_state.get("_page_id", "dashboard")
        pos     = st.session_state.get("_dash_pos")

        # Dashboard: mini-resumo consolidado do portfólio
        if page_id == "dashboard":
            portfolio = st.session_state.get("_portfolio", [])
            if portfolio:
                total_cap     = sum(p["valor"]         for p in portfolio)
                total_mam     = sum(p.get("mam_cache",     p["valor"])     for p in portfolio)
                total_carrego = sum(p.get("carrego_cache", p["valor"])     for p in portfolio)
                var_pct       = (total_mam - total_cap) / total_cap * 100
                cor_var       = "#38A169" if var_pct >= 0 else "#E53E3E"
                scores        = [st.session_state.get("_dash_pos", {}).get("score")]
                saude         = pos["score"] if pos else None
                cor_saude     = "#38A169" if saude and saude >= 70 else "#ECC94B" if saude and saude >= 40 else "#E53E3E"
                saude_html    = (
                    f'<div style="background:#0E1117; border-radius:4px; height:5px; margin-bottom:0.2rem;">'
                    f'  <div style="background:{cor_saude}; width:{saude:.0f}%; height:5px; border-radius:4px;"></div>'
                    f'</div>'
                    f'<div style="font-size:0.68rem; color:#718096;">Saúde: {saude:.0f}/100</div>'
                ) if saude is not None else ""
                st.markdown(f"""
<div style="background:#1C2331; border:1px solid #2D3748; border-radius:10px;
            padding:0.8rem 1rem; margin-bottom:1.2rem;">
  <div style="font-size:0.68rem; color:#38A169; text-transform:uppercase;
              letter-spacing:0.08em; margin-bottom:0.45rem; font-weight:600;">Seu Portfólio</div>
  <div style="font-size:0.68rem; color:#718096; margin-bottom:0.45rem;">{"1 posição" if len(portfolio) == 1 else f"{len(portfolio)} posições"}</div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.2rem;">
    <span style="color:#718096;">Capital</span>
    <span style="color:#FAFAFA;">{formatar_brl(total_cap)}</span>
  </div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.2rem;">
    <span style="color:#718096;">MaM Hoje</span>
    <span style="color:{cor_var};">{formatar_brl(total_mam)} ({var_pct:+.1f}%)</span>
  </div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.55rem;">
    <span style="color:#718096;">No Vencimento</span>
    <span style="color:#38A169;">{formatar_brl(total_carrego)}</span>
  </div>
  {saude_html}
</div>
""", unsafe_allow_html=True)

        # Simulador: contexto do título e capital simulado
        elif page_id == "simulador":
            sim_titulo = st.session_state.get("sim_titulo") or "—"
            sim_valor  = st.session_state.get("sim_valor", 10_000.0)
            st.markdown(f"""
<div style="background:#1C2331; border:1px solid #2D3748; border-radius:10px;
            padding:0.8rem 1rem; margin-bottom:1.2rem;">
  <div style="font-size:0.68rem; color:#4299E1; text-transform:uppercase;
              letter-spacing:0.08em; margin-bottom:0.45rem; font-weight:600;">Simulando</div>
  <div style="font-size:0.8rem; color:#FAFAFA; font-weight:600;
              margin-bottom:0.55rem; line-height:1.3;">{sim_titulo[:32]}</div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem;">
    <span style="color:#718096;">Capital</span>
    <span style="color:#FAFAFA;">{formatar_brl(sim_valor)}</span>
  </div>
</div>
""", unsafe_allow_html=True)
            # Mostra posição do Dashboard se existir
            if pos:
                st.caption(f"Posição no Dashboard: {pos['titulo'][:28]}")

        # Qual Ativo: contexto de horizonte + parâmetros macro
        elif page_id == "batalha":
            horizonte = st.session_state.get("bat_horizonte", 3)
            capital   = st.session_state.get("bat_capital", 10_000.0)
            ipca      = st.session_state.get("bat_ipca", 5.0)
            selic     = st.session_state.get("bat_selic", 13.0)
            st.markdown(f"""
<div style="background:#1C2331; border:1px solid #2D3748; border-radius:10px;
            padding:0.8rem 1rem; margin-bottom:1.2rem;">
  <div style="font-size:0.68rem; color:#ECC94B; text-transform:uppercase;
              letter-spacing:0.08em; margin-bottom:0.45rem; font-weight:600;">Comparando Ativos</div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.2rem;">
    <span style="color:#718096;">Horizonte</span>
    <span style="color:#FAFAFA;">{horizonte} ano(s)</span>
  </div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.2rem;">
    <span style="color:#718096;">Capital</span>
    <span style="color:#FAFAFA;">{formatar_brl(capital)}</span>
  </div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem; margin-bottom:0.2rem;">
    <span style="color:#718096;">IPCA proj.</span>
    <span style="color:#FAFAFA;">{ipca:.1f}% a.a.</span>
  </div>
  <div style="display:flex; justify-content:space-between; font-size:0.76rem;">
    <span style="color:#718096;">Selic proj.</span>
    <span style="color:#FAFAFA;">{selic:.2f}% a.a.</span>
  </div>
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
