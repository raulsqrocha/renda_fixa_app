# 📊 Renda Fixa CF — Brazilian Fixed Income Simulator

> An interactive educational tool that demystifies Brazil's government bond market — showing investors the difference between **what they feel** (daily price volatility) and **what they actually have** (a locked real return).

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://fixacf.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**[▶ Live Demo](https://fixacf.streamlit.app)**

---

## 🌎 Brazilian Fixed Income in 30 Seconds

Brazil has a government-run retail bond program called **Tesouro Direto** (Direct Treasury), where individual investors can buy federal bonds directly with no broker and no minimum beyond ~R$30 (~$6 USD).

The most popular bond is **Tesouro IPCA+**: it pays a fixed *real* yield on top of IPCA (Brazil's CPI), meaning your purchasing power is locked regardless of future inflation. Think of it as a TIPS bond in the US, but with higher yields (currently 6–8% real p.a.) and direct retail access.

The catch: these bonds are **marked to market daily**. When interest rates rise, the bond's market price drops and investors see red on their brokerage screens. Most retail investors panic and sell at the worst moment, locking in a loss that was never real. This app exists to stop that.

---

## ✨ Features

### 💼 Dashboard — My Portfolio
The main screen. Track a multi-position fixed-income portfolio with live market data pulled directly from Tesouro Direto.

At the top, three metric cards show real-time rates for Tesouro Selic, Prefixado, and IPCA+ as soon as market data loads.

**Portfolio management**

Supports all Tesouro Direto bond types plus CDB, LCI, and LCA in the same portfolio. Consolidated metrics show total invested capital, mark-to-market value, projected maturity value, and a weighted portfolio Health Score.

Two donut charts break down your allocation by asset type (IPCA+, Pós-Fixado, Pré-Fixado, CDB, LCI, LCA) and by maturity horizon (short ≤ 2y, medium 3–5y, long > 5y). The position table includes a Health Progress Bar per holding (0–100), combining time remaining and current MtM position vs. invested capital.

**Detailed position analysis**

Clicking on any position opens a four-tab drill-down:

- **📊 Position:** the MtM vs. Carry paradox chart, showing how both lines always converge at maturity. Also includes IOF warning for positions under 30 days, bid-ask spread in basis points, B3 custody fee toggle, and a projected growth chart.
- **⚡ Simulations:** a rate shock stress-test with an adjustable basis-point shock; an early-exit cost calculator ("thinking of selling — what's the real cost?"); and a monthly contribution planner.
- **📈 Portfolio:** the full portfolio table with all positions in context.
- **🛠️ Utilities:** plain-text position summary for copying to notes or sharing.

**About the Health Score (0–100)**

The score has two components. Time (up to 60 pts): the more time remaining to maturity, the easier it is to ride out volatility. Position (up to 40 pts): the closer MtM is to invested capital, the lower the behavioral discomfort. Thresholds: 🟢 ≥ 70 Healthy · 🟡 40–69 Caution · 🔴 < 40 At Risk.

---

### 🎯 Which Asset to Choose?
Answers the practical question: given my exit horizon, which Tesouro Direto bond delivers the best real return for the least MtM risk?

All selected bonds run through adverse, neutral, and favorable macro scenarios at once. A **Markowitz frontier chart** plots each bond's expected return vs. MtM risk, and a **return by exit horizon** chart shows how that picture changes across 1 to 15 year windows. When a bond matures before the chosen horizon, the chart switches to a dashed line showing reinvestment at Selic.

There is also a mixed portfolio mode: combine a long-duration bond with a liquid short-term position and see the blended risk/return profile. Progressive IR tax is applied correctly per holding period throughout.

---

### 📊 Compare Products
Answers: given my tax profile and time horizon, does a CDB, LCI, or LCA beat Tesouro Direto?

All six product types are shown side by side with fully adjustable rates. A tax-equivalence calculator shows what gross rate a taxed product needs to match a tax-exempt one. The final value chart applies IR correctly per product type across the selected horizon.

---

### 🔬 Advanced Simulator
Four tools in one screen.

**Inflation Scenario Simulator.** Three sliders (low / base / stress IPCA) project the nominal value at maturity. The key insight: the real gain is identical across all inflation scenarios, because IPCA+ locks your real yield at purchase.

**MtM Strategy Matrix.** A 9-scenario × multi-bond heat map showing early-exit returns across rate environments from Péssimo to Excepcional. Cells are color-coded from deep red to deep green.

**DI Futures Curve.** Enter current futures contract rates (Jan/27 through Jan/35) sourced from B3 and visualize the Brazilian nominal yield curve. An adjustable slope tool lets you flatten or steepen the curve to explore duration risk.

**IPCA Historical Retrospective.** Over 10 years of monthly IPCA data from the Brazilian Central Bank, with annotated macro events like the 2015 fiscal crisis and the 2021 post-pandemic surge. Includes a "what if you had invested?" simulator: pick a starting year and capital amount, set hypothetical IPCA+, Prefixado, and Selic rates, and see the cumulative growth of each strategy plotted against the inflation baseline.

---

## 🏗️ Tech Stack

| Layer | Technology |
|---|---|
| UI & framework | [Streamlit](https://streamlit.io) |
| Numerical computing | NumPy, Pandas |
| Charting | Plotly |
| HTTP / data fetching | Requests |
| Timezone handling | Pytz |

---

## 📡 Data Sources

All data is free, public, and requires no API keys.

| Source | Data | Endpoint |
|---|---|---|
| [Banco Central do Brasil (BCB)](https://www.bcb.gov.br/) | Monthly IPCA inflation — last 132 months | SGS Series 433 |
| [Tesouro Transparente](https://www.tesourotransparente.gov.br/) | Live prices, rates, and bid-ask spreads for all Tesouro Direto bonds | Official CSV |

The app calculates the **VNA** (Valor Nominal Atualizado — the inflation-adjusted face value of NTN-B bonds) by compounding historical IPCA from the ANBIMA base of Dec/2014 (R$2,712.00). Cache refreshes automatically at 14:00 Brasília time, after Tesouro Direto's daily close.

---

## 📐 Key Formulas

**NTN-B / Tesouro IPCA+ Pricing** (ANBIMA methodology):

$$PU = \sum_{i=1}^{n} \frac{C}{(1 + r)^{du_i/252}} + \frac{VNA}{(1 + r)^{du_n/252}}$$

Where `C` = semiannual coupon (`VNA × [(1.06)^0.5 − 1]`), `r` = real yield, `du` = business days using the 252 d.u./year Brazilian convention.

> Business days are counted Mon–Fri with an estimated correction of ~11 ANBIMA holidays/year, reducing the gap vs. the official ANBIMA calendar without requiring an external library. Expected deviation: ±2 DU/year.

**Mark-to-Market Early Exit Return:**

$$\text{Return} = \left(\frac{1 + r_{\text{buy}}}{1 + r_{\text{sell}}}\right)^{T - N} - 1$$

Where `T` = years to maturity, `N` = years to early exit. The future VNA cancels algebraically, so IPCA does not directly affect this calculation.

**IPCA+ Monthly Compounding** (historical simulation):

$$V_t = V_{t-1} \times (1 + \text{IPCA}_{\text{month}}) \times (1 + r_{\text{real}})^{1/12}$$

**Progressive IR Tax** (Brazil's regressive income tax on fixed income):

| Holding period | Tax on gains |
|---|---|
| ≤ 180 days | 22.5% |
| 181–360 days | 20.0% |
| 361–720 days | 17.5% |
| > 720 days | 15.0% |

LCI and LCA are exempt from IR for individual investors at any holding period.

---

## 🚀 Local Setup

```bash
git clone https://github.com/raulsqrocha/renda_fixa_app.git
cd renda_fixa_app
pip install -r requirements.txt
streamlit run app.py
```

The app opens at `http://localhost:8501`. No environment variables or API keys required.

---

## 📁 Project Structure

```
renda_fixa_app/
├── app.py                        # Streamlit entrypoint and navigation
├── pages/
│   ├── 0_Dashboard.py            # Page 1: My Portfolio
│   ├── 1_Qual_Ativo.py           # Page 2: Which Asset to Choose?
│   ├── 2_Comparar_Produtos.py    # Page 3: Compare Products
│   └── 3_Simulador_MaM.py        # Page 4: Advanced Simulator
├── core/
│   ├── financas.py               # Financial calculations (pricing, IR, IOF, MtM, health score)
│   ├── dados.py                  # Data fetching and caching (BCB + Tesouro Transparente)
│   ├── graficos.py               # Plotly chart builders
│   ├── persistencia.py           # User preferences persistence across sessions
│   └── estilos.py                # Global CSS and dark theme
├── telas/
│   ├── dashboard.py              # Dashboard screen logic
│   ├── batalha.py                # Which Asset screen logic
│   ├── comparar.py               # Compare Products screen logic
│   └── simulador.py              # Advanced Simulator screen logic
└── requirements.txt
```

---

## 🤝 Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss what you'd like to change.

---

*Built with Python + Streamlit. Financial data sourced from the Brazilian Central Bank and Tesouro Transparente.*
