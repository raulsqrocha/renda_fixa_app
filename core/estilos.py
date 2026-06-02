"""CSS global compartilhado entre todas as páginas do app."""

import streamlit as st
from core.financas import formatar_brl

_CSS = """
<style>
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700&display=swap');

html, body, [class*="css"] {
    font-family: 'Inter', sans-serif !important;
}

/* ── Remove padding excessivo no topo do conteúdo principal ────────── */
[data-testid="stMainBlockContainer"] {
    padding-top: 1.5rem !important;
}

/* ── Sidebar: oculta nav automático (substituído por st.page_link) ─── */
[data-testid="stSidebarNav"] {
    display: none !important;
}

/* ── Hero Banner ───────────────────────────────────────────────────── */
.hero-banner {
    background: transparent;
    border: none;
    border-left: 3px solid #38A169;
    padding: 0.4rem 0 0.6rem 1.2rem;
    margin-bottom: 1.6rem;
}
.hero-title-row {
    display: flex;
    align-items: center;
    gap: 1rem;
    margin-bottom: 0.35rem;
}
.hero-bull {
    border-radius: 50%;
    overflow: hidden;
    background: #080c14;
    width: 150px;
    height: 150px;
    flex-shrink: 0;
    display: flex;
    align-items: center;
    justify-content: center;
    box-shadow: 0 0 0 2px rgba(56,161,105,0.35);
}
.hero-bull img {
    display: block;
    width: 150px;
    height: 150px;
    object-fit: cover;
    mix-blend-mode: screen;
}
.hero-tag {
    font-size: 0.68rem;
    font-weight: 600;
    letter-spacing: 0.1em;
    color: #38A169;
    text-transform: uppercase;
    margin-bottom: 0.25rem;
}
.hero-title {
    font-size: 1.75rem;
    font-weight: 700;
    color: #FAFAFA;
    line-height: 1.15;
    margin: 0 0 0.35rem 0;
}
.hero-title span { color: #FAFAFA; }
.hero-subtitle {
    font-size: 0.88rem;
    color: #718096;
    margin: 0;
    max-width: 520px;
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
    background: linear-gradient(135deg, #2a1010, #3d1c1c);
    border: 1px solid #E53E3E;
    border-left: 4px solid #E53E3E;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 0.8rem 0;
    font-size: 0.92rem;
    color: #FED7D7;
}
.badge-seguranca {
    background: linear-gradient(135deg, #0e2412, #1a3a1f);
    border: 1px solid #38A169;
    border-left: 4px solid #38A169;
    border-radius: 8px;
    padding: 1rem 1.2rem;
    margin: 0.8rem 0;
    font-size: 0.92rem;
    color: #C6F6D5;
}

/* ── Sidebar ────────────────────────────────────────────────────────── */
[data-testid="stSidebar"] {
    background-color: #0D1117;
    border-right: 1px solid #21262D;
}
[data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {
    color: #8B949E;
}

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

/* ── Responsivo ─────────────────────────────────────────────────────── */

/* Notebook menor / tablet landscape (< 1280px) */
@media (max-width: 1280px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: 2rem !important;
        padding-right: 2rem !important;
    }
    .hero-title { font-size: 1.55rem; }
    .hero-bull { width: 130px !important; height: 130px !important; }
    .hero-bull img { width: 130px !important; height: 130px !important; }
}

/* Tablet portrait / notebook pequeno (< 1024px) */
@media (max-width: 1024px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: 1.5rem !important;
        padding-right: 1.5rem !important;
    }
    .hero-title      { font-size: 1.35rem; }
    .hero-subtitle   { font-size: 0.84rem; }
    .hero-bull       { width: 110px !important; height: 110px !important; }
    .hero-bull img   { width: 110px !important; height: 110px !important; }
    .titulo-principal { font-size: 1.45rem; }
}

/* Tablet estreito / celular landscape (< 768px) */
@media (max-width: 768px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: 1rem !important;
        padding-right: 1rem !important;
        padding-top: 1rem !important;
    }
    .hero-banner     { padding-left: 0.8rem; }
    .hero-title      { font-size: 1.2rem; }
    .hero-subtitle   { font-size: 0.8rem; max-width: 100%; }
    .hero-bull       { width: 90px !important; height: 90px !important; }
    .hero-bull img   { width: 90px !important; height: 90px !important; }
    .titulo-principal { font-size: 1.25rem; }
    .subtitulo        { font-size: 0.84rem; }
}

/* Celular portrait (< 480px) */
@media (max-width: 480px) {
    [data-testid="stMainBlockContainer"] {
        padding-left: 0.6rem !important;
        padding-right: 0.6rem !important;
    }
    .hero-title-row  { flex-direction: column; align-items: flex-start; gap: 0.5rem; }
    .hero-bull       { width: 80px !important; height: 80px !important; }
    .hero-bull img   { width: 80px !important; height: 80px !important; }
    .hero-title      { font-size: 1.1rem; }
    .hero-subtitle   { font-size: 0.76rem; }
    .hero-tag        { font-size: 0.6rem; }
    .titulo-principal { font-size: 1.1rem; }
    .subtitulo        { font-size: 0.8rem; }
}
</style>
"""


def aplicar_estilo_global() -> None:
    """Injeta o CSS global do app via st.markdown."""
    st.markdown(_CSS, unsafe_allow_html=True)


def sidebar_info() -> None:
    """Renderiza o bloco de branding e créditos na sidebar."""
    with st.sidebar:
        # ── Contexto da página ativa ────────────────────────────────────
        page_id = st.session_state.get("_page_id", "dashboard")
        pos = st.session_state.get("_dash_pos")

        # Dashboard: mini-resumo consolidado do portfólio
        if page_id == "dashboard":
            portfolio = st.session_state.get("_portfolio", [])
            if portfolio:
                total_cap = sum(p["valor"] for p in portfolio)
                total_mam = sum(p.get("mam_cache", p["valor"]) for p in portfolio)
                total_carrego = sum(
                    p.get("carrego_cache", p["valor"]) for p in portfolio
                )
                var_pct = (total_mam - total_cap) / total_cap * 100
                cor_var = "#38A169" if var_pct >= 0 else "#E53E3E"
                saude = pos["score"] if pos else None
                cor_saude = (
                    "#38A169"
                    if saude and saude >= 70
                    else "#ECC94B"
                    if saude and saude >= 40
                    else "#E53E3E"
                )
                saude_html = (
                    (
                        f'<div style="background:#0E1117; border-radius:4px; height:5px; margin-bottom:0.2rem;">'
                        f'  <div style="background:{cor_saude}; width:{saude:.0f}%; height:5px; border-radius:4px;"></div>'
                        f"</div>"
                        f'<div style="font-size:0.68rem; color:#718096;">Saúde: {saude:.0f}/100</div>'
                    )
                    if saude is not None
                    else ""
                )
                st.markdown(
                    f"""
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
""",
                    unsafe_allow_html=True,
                )

        # Simulador: contexto do título e capital simulado
        elif page_id == "simulador":
            sim_titulo = st.session_state.get("sim_titulo") or "—"
            sim_valor = st.session_state.get("sim_valor", 10_000.0)
            st.markdown(
                f"""
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
""",
                unsafe_allow_html=True,
            )
            # Mostra posição do Dashboard se existir
            if pos:
                st.caption(f"Posição no Dashboard: {pos['titulo'][:28]}")

        # Qual Ativo: contexto de horizonte + parâmetros macro
        elif page_id == "batalha":
            horizonte = st.session_state.get("bat_horizonte", 3)
            capital = st.session_state.get("bat_capital", 10_000.0)
            ipca = st.session_state.get("bat_ipca", 5.0)
            selic = st.session_state.get("bat_selic", 14.75)
            st.markdown(
                f"""
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
""",
                unsafe_allow_html=True,
            )

        # Banner de aviso quando alguma fonte está usando dados de fallback
        status = st.session_state.get("_status_dados", {})
        partes = []
        if status.get("titulos_fallback"):
            partes.append("taxas dos títulos")
        if status.get("ipca_fallback"):
            partes.append("IPCA histórico")
        if partes:
            st.markdown(
                f'<div style="background:linear-gradient(135deg,#2a1a00,#3d2800);'
                f"border:1px solid #DD6B20;border-left:4px solid #DD6B20;"
                f"border-radius:8px;padding:0.7rem 0.9rem;margin-bottom:1rem;"
                f'font-size:0.78rem;color:#FEEBC8;">'
                f"⚠️ <b>Dados estimados</b><br>"
                f'<span style="color:#FBD38D;">{", ".join(partes)}</span><br>'
                f'<span style="color:#718096;font-size:0.72rem;">API indisponível — usando referências locais</span>'
                f"</div>",
                unsafe_allow_html=True,
            )

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
        st.markdown(
            '<div style="font-size:0.72rem; color:#4A5568; margin-top:0.4rem;">'
            "v1.0 · Streamlit · Plotly<br>"
            '<span style="color:#718096;">por Raul Rocha</span>'
            "</div>",
            unsafe_allow_html=True,
        )
