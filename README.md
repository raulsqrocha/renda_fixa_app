# 📊 Renda Fixa CF — Brazilian Fixed Income Simulator

> An interactive educational tool that demystifies Brazil's government bond market — showing investors the difference between **what they feel** (daily price volatility) and **what they actually have** (a locked real return).

[![Streamlit App](https://static.streamlit.io/badges/streamlit_badge_black_white.svg)](https://fixacf.streamlit.app)
[![Python](https://img.shields.io/badge/Python-3.10%2B-blue)](https://www.python.org/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

**[▶ Live Demo](https://fixacf.streamlit.app)**

---

## 🌎 Brazilian Fixed Income in 30 Seconds

Brazil has a government-run retail bond program called **Tesouro Direto** (Direct Treasury), where individual investors can buy federal bonds directly — no broker, no minimum beyond ~R$30 (~$6 USD).

The most popular bond is **Tesouro IPCA+**: it pays a fixed *real* yield on top of IPCA (Brazil's CPI), meaning your purchasing power is locked regardless of future inflation. Think of it as a TIPS bond in the US, but with higher yields (currently 6–8% real p.a.) and direct retail access.

The catch: these bonds are **marked to market daily**. When interest rates rise, the bond's market price drops — and investors see red on their brokerage screens. Most retail investors panic and sell at the worst moment, locking in a loss that was never real. **This app exists to stop that.**

---

## ✨ Features

### 🏠 Dashboard — The Paradox of Fixed Income
The core screen. You configure a position (title, amount, contracted rate, purchase date) and the app shows you two things side by side:

- **MtM Line (red):** what the market would pay you *today* — volatile, scary
- **Carry Line (green):** what you will actually receive if you hold to maturity — stable, exponential

The two lines always converge at maturity. That convergence *is* the point.

Additional tools on the dashboard:
- **Panic Button:** stress-test with an adjustable rate shock (simulates fiscal or political crises) — shows the mark-to-market drop while the maturity value stays exactly the same
- **Serenity Index:** a behavioral score (0–100) combining current MtM position vs. invested capital and time remaining
- **IOF warning:** Brazil taxes short-term gains on a regressive daily scale (96% → 0% over 30 days); the app alerts you if selling now triggers IOF
- **B3 Custody Fee:** optional checkbox to factor in the 0.20% p.a. annual fee charged by B3 (Brazil's exchange), including the legal exemption for Tesouro Selic positions under R$10,000
- **Bid-Ask Spread:** shows the spread in basis points between Tesouro's buy and sell prices, with the estimated R$ impact on early redemption

### 🔬 Advanced Simulator
- **Inflation Scenarios:** project different IPCA paths and see that the *real* gain is identical across all of them — because IPCA+ locks your real yield at purchase
- **MtM Strategy Simulator:** a 9-scenario matrix showing early-exit returns across multiple titles and time horizons, with a color-coded heat map
- **DI Futures Curve:** manually input current futures contract rates (Jan/27 through Jan/35) and visualize the Brazilian yield curve structure
- **IPCA Historical Retrospective:** 10 years of monthly inflation data from the Brazilian Central Bank, with annotated macro events

### 🎯 Which Asset to Choose?
- **Scenario Battle:** compares Tesouro Selic (floating), Prefixado (fixed rate), and IPCA+ across three macro scenarios (adverse, neutral, favorable)
- Supports hold-to-maturity and early exit, with progressive IR tax applied correctly per holding period
- Mixed portfolio: shows the risk/return tradeoff when combining a long bond with a liquid short-term position

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

All data is **free, public, and requires no API keys.**

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

> Business days are counted Mon–Fri with an estimated correction of ~11 ANBIMA holidays/year — reducing the gap vs. the official ANBIMA calendar without requiring an external library. Expected deviation: ±2 DU/year.

**Mark-to-Market Early Exit Return:**

$$\text{Return} = \left(\frac{1 + r_{\text{buy}}}{1 + r_{\text{sell}}}\right)^{T - N} - 1$$

Where `T` = years to maturity, `N` = years to early exit. The future VNA cancels algebraically — IPCA does not directly affect this calculation.

**Progressive IR Tax** (Brazil's regressive income tax on fixed income):

| Holding period | Tax on gains |
|---|---|
| ≤ 180 days | 22.5% |
| 181–360 days | 20.0% |
| 361–720 days | 17.5% |
| > 720 days | 15.0% |

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
├── app.py                  # Streamlit entrypoint and navigation
├── pages/
│   ├── 0_Dashboard.py      # Page 1: Dashboard
│   ├── 1_Simulador_MaM.py  # Page 2: Advanced Simulator
│   └── 2_Qual_Ativo.py     # Page 3: Which Asset?
├── core/
│   ├── financas.py         # All financial calculations (pricing, IR, IOF, MtM)
│   ├── dados.py            # Data fetching and caching (BCB + Tesouro Transparente)
│   ├── graficos.py         # Plotly chart builders
│   └── estilos.py          # Global CSS and theme
├── telas/
│   ├── dashboard.py        # Dashboard screen logic
│   ├── simulador.py        # Simulator screen logic
│   └── batalha.py          # Scenario Battle screen logic
└── requirements.txt
```

---

## 🤝 Contributing

Pull requests are welcome. For significant changes, open an issue first to discuss what you'd like to change.

---

*Built with Python + Streamlit. Financial data sourced from the Brazilian Central Bank and Tesouro Transparente.*
