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

import logging
import time
import requests
from requests.exceptions import HTTPError
import pandas as pd
import numpy as np
import streamlit as st
from datetime import datetime, date, timedelta
import pytz

_log = logging.getLogger(__name__)


def _get_com_retry(url: str, *, timeout: int, tentativas: int = 3) -> requests.Response:
    """
    Wrapper de requests.get com retry exponencial para erros retriáveis.

    Retenta em: erros 5xx (servidor), ConnectionError, Timeout.
    Não retenta em: erros 4xx (cliente) — são determinísticos.
    Intervalo entre tentativas: 0.5s, 1s (backoff linear).
    Só executa dentro de funções cacheadas — o sleep não bloqueia renders.
    """
    ultimo_erro: Exception = RuntimeError("sem tentativas")
    for i in range(tentativas):
        try:
            resp = requests.get(url, timeout=timeout)
            resp.raise_for_status()
            return resp
        except HTTPError as e:
            # Erros 4xx são determinísticos — não adianta retentar
            if e.response is not None and e.response.status_code < 500:
                raise
            ultimo_erro = e
        except Exception as e:
            ultimo_erro = e
        if i < tentativas - 1:
            time.sleep(0.5 * (i + 1))
    raise ultimo_erro


# ---------------------------------------------------------------------------
# Constantes
# ---------------------------------------------------------------------------

URL_BCB_IPCA = (
    "https://api.bcb.gov.br/dados/serie/bcdata.sgs.433/dados/ultimos/200?formato=json"
)
# Tesouro Transparente — CSV oficial, gratuito, sem auth, atualização diária
URL_TESOURO_CSV = (
    "https://www.tesourotransparente.gov.br/ckan/dataset/"
    "df56aa42-484a-4a59-8184-7676580c81e3/resource/"
    "796d2059-14e9-44e3-80c9-2d9e30b405c1/download/precotaxatesourodireto.csv"
)

# VNA da NTN-B em dez/2014 (fonte: ANBIMA histórico) — base para cálculo via BCB
VNA_BASE_DEZ2014 = 2_712.00

# VNA dinâmico: VNA_BASE_DEZ2014 corrigido por IPCA ~5% a.a. até hoje
# Usado apenas quando a API do BCB estiver offline (df_ipca vazio)
VNA_FALLBACK = round(
    VNA_BASE_DEZ2014 * (1.05) ** ((date.today() - date(2014, 12, 15)).days / 365),
    2,
)

# ---------------------------------------------------------------------------
# Catálogo completo de títulos suportados
# ---------------------------------------------------------------------------

# Configuração mestre: vencimento e tipo de cupom por título
# Principal e RendA+/Educar+ (acumulação) → sem cupons → gráfico liso
# Juros Semestrais → com cupons → gráfico dente de serra
TITULOS_CONFIG: dict = {
    # IPCA+ Principal (sem cupons) — mai/2026
    "Tesouro IPCA+ 2032": {"vencimento": date(2032, 8, 15), "tem_cupom": False},
    "Tesouro IPCA+ 2040": {"vencimento": date(2040, 8, 15), "tem_cupom": False},
    "Tesouro IPCA+ 2050": {"vencimento": date(2050, 8, 15), "tem_cupom": False},
    # IPCA+ com Juros Semestrais (cupom a cada 6 meses)
    "Tesouro IPCA+ com Juros Semestrais 2037": {
        "vencimento": date(2037, 5, 15),
        "tem_cupom": True,
    },
    "Tesouro IPCA+ com Juros Semestrais 2045": {
        "vencimento": date(2045, 5, 15),
        "tem_cupom": True,
    },
    "Tesouro IPCA+ com Juros Semestrais 2060": {
        "vencimento": date(2060, 8, 15),
        "tem_cupom": True,
    },
    # Tesouro Renda+ Aposentadoria Extra (exibido como RendA+)
    **{
        f"Tesouro RendA+ {ano}": {"vencimento": date(ano, 12, 15), "tem_cupom": False}
        for ano in [2030, 2035, 2040, 2045, 2050, 2055, 2060, 2065]
    },
    # Tesouro Educa+ (nome real no CSV; exibido como Educar+ no app)
    **{
        f"Tesouro Educar+ {ano}": {"vencimento": date(ano, 12, 15), "tem_cupom": False}
        for ano in range(2027, 2045)
    },
}

# ---------------------------------------------------------------------------
# Catálogo adicional: Selic e Prefixado (usados na Batalha de Cenários)
# taxa_ref = None para Selic porque a taxa vem da projeção do usuário
# ---------------------------------------------------------------------------

TITULOS_BATALHA: dict = {
    # Pós-Fixado (taxa_ref=None: vem da projeção do usuário)
    "Tesouro Selic 2031": {
        "vencimento": date(2031, 3, 1),
        "tipo": "selic",
        "taxa_ref": None,
    },
    "Tesouro Reserva": {
        "vencimento": date(2027, 3, 1),
        "tipo": "selic",
        "taxa_ref": None,
    },
    # Pré-Fixado
    "Tesouro Prefixado 2029": {
        "vencimento": date(2029, 1, 1),
        "tipo": "pre",
        "taxa_ref": 14.50,
    },
    "Tesouro Prefixado 2032": {
        "vencimento": date(2032, 1, 1),
        "tipo": "pre",
        "taxa_ref": 14.89,
    },
    "Tesouro Prefixado com Juros Semestrais 2037": {
        "vencimento": date(2037, 1, 1),
        "tipo": "pre",
        "taxa_ref": 14.89,
    },
    # Todos os IPCA+, RendA+ e Educar+ do catálogo completo
    **{
        nome: {"vencimento": cfg["vencimento"], "tipo": "ipca_mais", "taxa_ref": None}
        for nome, cfg in TITULOS_CONFIG.items()
    },
}

# Seletor de dois níveis: categoria → lista de títulos
# Derivado automaticamente de TITULOS_CONFIG para manter consistência
CATEGORIAS_TITULOS: dict = {
    "IPCA+ Principal": [
        k
        for k in TITULOS_CONFIG
        if k.startswith("Tesouro IPCA+") and "Semestrais" not in k
    ],
    "IPCA+ com Juros Semestrais": [k for k in TITULOS_CONFIG if "Semestrais" in k],
    "Tesouro RendA+": [k for k in TITULOS_CONFIG if "RendA+" in k],
    "Tesouro Educar+": [k for k in TITULOS_CONFIG if "Educar+" in k],
}

# Taxas de referência para o fallback — extraídas do Tesouro Transparente em 13/07/2026
_TAXAS_REF: dict = {
    # IPCA+ Principal
    "Tesouro IPCA+ 2032": 8.09,
    "Tesouro IPCA+ 2040": 7.53,
    "Tesouro IPCA+ 2050": 7.21,
    # IPCA+ Juros Semestrais
    "Tesouro IPCA+ com Juros Semestrais 2037": 7.83,
    "Tesouro IPCA+ com Juros Semestrais 2045": 7.49,
    "Tesouro IPCA+ com Juros Semestrais 2060": 7.36,
    # Renda+ Aposentadoria Extra
    "Tesouro RendA+ 2030": 7.82,
    "Tesouro RendA+ 2035": 7.65,
    "Tesouro RendA+ 2040": 7.5,
    "Tesouro RendA+ 2045": 7.38,
    "Tesouro RendA+ 2050": 7.28,
    "Tesouro RendA+ 2055": 7.2,
    "Tesouro RendA+ 2060": 7.14,
    "Tesouro RendA+ 2065": 7.08,
    # Educar+
    "Tesouro Educar+ 2027": 8.12,
    "Tesouro Educar+ 2028": 8.04,
    "Tesouro Educar+ 2029": 7.97,
    "Tesouro Educar+ 2030": 8.34,
    "Tesouro Educar+ 2031": 8.28,
    "Tesouro Educar+ 2032": 8.21,
    "Tesouro Educar+ 2033": 8.14,
    "Tesouro Educar+ 2034": 8.07,
    "Tesouro Educar+ 2035": 8.0,
    "Tesouro Educar+ 2036": 7.93,
    "Tesouro Educar+ 2037": 7.87,
    "Tesouro Educar+ 2038": 7.8,
    "Tesouro Educar+ 2039": 7.73,
    "Tesouro Educar+ 2040": 7.66,
    "Tesouro Educar+ 2041": 7.59,
    "Tesouro Educar+ 2042": 7.53,
    "Tesouro Educar+ 2043": 7.47,
    "Tesouro Educar+ 2044": 7.41,
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


@st.cache_data(ttl=3600 * 2)
def timestamp_ultima_atualizacao(chave: str) -> datetime:
    """Registra o momento exato em que os dados foram carregados. Cache sincronizado com buscar_titulos_tesouro."""
    return datetime.now(pytz.timezone("America/Sao_Paulo"))


# ---------------------------------------------------------------------------
# IPCA — Banco Central do Brasil
# ---------------------------------------------------------------------------


@st.cache_data(ttl=3600 * 4)
def buscar_selic_meta_bcb() -> float:
    """
    Retorna a meta da Selic mais recente (BCB Série 1178), em % a.a.
    TTL de 4 horas — muda apenas nas reuniões do COPOM (~a cada 45 dias).
    Fallback: 14.75% se a API estiver indisponível.
    """
    try:
        url = "https://api.bcb.gov.br/dados/serie/bcdata.sgs.1178/dados/ultimos/1?formato=json"
        resp = _get_com_retry(url, timeout=10)
        return float(resp.json()[0]["valor"])
    except Exception as e:
        _log.warning("BCB Selic meta indisponível (%s) — fallback 14.75%%", e)
        return 14.75


@st.cache_data(ttl=3600 * 24)
def buscar_selic_na_data(data_compra: "date") -> float:
    """
    Retorna a taxa Selic efetiva (% a.a., base 252) na data de compra.

    Usa BCB Série 4189 — "Taxa Selic" diária já anualizada, que reflete
    o valor exato acumulado pelo Tesouro Selic naquele pregão. É diferente
    da meta COPOM (Série 1178): a efetiva é o que o título realmente rendeu,
    a meta é a decisão formal do comitê (diferença típica < 5 bp).

    Busca os 10 dias anteriores à data para garantir que há pelo menos
    um dia útil no intervalo. Fallback: 14.75%.
    """
    try:
        ini = (data_compra - timedelta(days=10)).strftime("%d/%m/%Y")
        fim = data_compra.strftime("%d/%m/%Y")
        url = (
            f"https://api.bcb.gov.br/dados/serie/bcdata.sgs.4189/dados"
            f"?formato=json&dataInicial={ini}&dataFinal={fim}"
        )
        resp = _get_com_retry(url, timeout=10)
        dados = resp.json()
        if dados:
            return float(dados[-1]["valor"])
    except Exception as e:
        _log.warning(
            "BCB Selic efetiva indisponível para %s (%s) — fallback 14.75%%",
            data_compra,
            e,
        )
    return 14.75


@st.cache_data(ttl=3600 * 8)
def buscar_ipca_bcb() -> pd.DataFrame:
    """
    Busca os últimos 132 meses de IPCA mensal na API do BCB (Série 433).
    TTL de 8 horas — dados mudam apenas uma vez por mês.
    """
    try:
        resp = _get_com_retry(URL_BCB_IPCA, timeout=15)
        df = pd.DataFrame(resp.json())
        df.columns = ["data", "valor"]
        df["data"] = pd.to_datetime(df["data"], format="%d/%m/%Y")
        df["valor"] = df["valor"].astype(float)
        df = df.sort_values("data").reset_index(drop=True)
        df["_is_fallback"] = False
        return df

    except Exception as e:
        _log.warning("BCB IPCA API indisponível (%s) — usando série histórica local", e)
        return _ipca_fallback()


def _ipca_fallback() -> pd.DataFrame:
    """
    Série histórica real do IPCA mensal: jan/2015 a jun/2026 (138 meses).
    Jan–dez/2025: oficiais BCB. Jan–mai/2026: oficiais BCB. Jun/2026: estimativa.
    Usada quando a API do BCB está indisponível.
    """
    valores = [
        # 2015
        1.24,
        1.22,
        1.32,
        0.71,
        0.74,
        0.79,
        0.62,
        0.22,
        0.54,
        0.82,
        1.01,
        0.96,
        # 2016
        1.27,
        0.90,
        0.43,
        0.61,
        0.78,
        0.35,
        0.52,
        0.44,
        0.08,
        0.26,
        0.18,
        0.30,
        # 2017
        0.38,
        0.33,
        0.25,
        0.14,
        0.31,
        -0.23,
        0.24,
        0.19,
        0.16,
        0.42,
        0.28,
        0.44,
        # 2018
        0.29,
        0.32,
        0.09,
        0.22,
        0.40,
        1.26,
        0.33,
        -0.09,
        0.48,
        0.45,
        -0.21,
        0.15,
        # 2019
        0.32,
        0.43,
        0.75,
        0.57,
        0.13,
        0.01,
        0.19,
        0.11,
        -0.04,
        0.10,
        0.51,
        1.15,
        # 2020
        0.21,
        0.25,
        0.07,
        -0.31,
        -0.38,
        0.26,
        0.36,
        0.24,
        0.64,
        0.86,
        0.89,
        1.35,
        # 2021
        0.25,
        0.86,
        0.93,
        0.31,
        0.83,
        0.53,
        0.96,
        0.87,
        1.16,
        1.25,
        0.95,
        0.73,
        # 2022
        0.54,
        1.01,
        1.62,
        1.06,
        0.47,
        0.67,
        -0.68,
        -0.36,
        -0.29,
        0.59,
        0.41,
        0.54,
        # 2023
        0.53,
        0.84,
        0.71,
        0.61,
        0.23,
        -0.08,
        0.12,
        -0.02,
        0.26,
        0.24,
        0.28,
        0.62,
        # 2024
        0.42,
        0.83,
        0.16,
        0.38,
        0.46,
        0.20,
        0.38,
        -0.02,
        0.44,
        0.56,
        0.39,
        0.52,
        # 2025 — fonte: BCB Série 433 (verificado em 27/05/2026)
        0.16,
        1.31,
        0.56,
        0.43,
        0.26,
        0.24,
        0.26,
        -0.11,
        0.48,
        0.09,
        0.18,
        0.33,
        # 2026 (jan–mai: oficiais BCB; jun: estimativa — atualizar quando publicado ~jul/2026)
        0.33,
        0.70,
        0.88,
        0.67,
        0.43,
        0.40,
    ]
    datas = pd.date_range("2015-01-01", periods=138, freq="MS")
    df = pd.DataFrame({"data": datas, "valor": valores})
    df["_is_fallback"] = True
    return df


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
    if df_ipca.empty or "data" not in df_ipca.columns:
        return VNA_FALLBACK
    corte = pd.Timestamp("2015-01-01")
    df = df_ipca[df_ipca["data"] >= corte].copy()

    if df.empty:
        return VNA_FALLBACK  # fallback dinâmico quando API do BCB está offline

    fator = float(np.prod(1 + df["valor"].to_numpy(dtype=float) / 100))
    return round(VNA_BASE_DEZ2014 * fator, 2)


def calcular_vna_em_data(df_ipca: pd.DataFrame, data_ref: date) -> float:
    """
    Estima o VNA em uma data histórica acumulando IPCA desde jan/2015 até data_ref.

    Inclui todos os meses com início ≤ data_ref (convenção: o IPCA do mês
    é incorporado ao VNA no dia 15 daquele mês).

    Usado para calcular o PU correto na data de compra — sem esse ajuste,
    o app subestimaria MaM e carrego pelo IPCA acumulado desde a compra.
    """
    if df_ipca.empty or "data" not in df_ipca.columns:
        return VNA_BASE_DEZ2014
    corte = pd.Timestamp("2015-01-01")
    limite = pd.Timestamp(data_ref.replace(day=1))
    df = df_ipca[(df_ipca["data"] >= corte) & (df_ipca["data"] <= limite)].copy()

    if df.empty:
        return VNA_BASE_DEZ2014

    fator = float(np.prod(1 + df["valor"].to_numpy(dtype=float) / 100))
    return round(VNA_BASE_DEZ2014 * fator, 2)


# ---------------------------------------------------------------------------
# Tesouro Direto — preços e taxas
# ---------------------------------------------------------------------------


def construir_nome_titulo(tipo_csv: str, ano_venc: int) -> str | None:
    """
    Mapeia o nome do tipo no CSV do Tesouro Transparente para o nome interno do app.
    Normaliza variantes de acento e mantém consistência com TITULOS_CONFIG.
    """
    t = tipo_csv.strip()
    if t == "Tesouro IPCA+":
        return f"Tesouro IPCA+ {ano_venc}"
    if t == "Tesouro IPCA+ com Juros Semestrais":
        return f"Tesouro IPCA+ com Juros Semestrais {ano_venc}"
    if "Renda+" in t or "RendA+" in t:
        return f"Tesouro RendA+ {ano_venc}"
    if "Educa+" in t:
        return f"Tesouro Educar+ {ano_venc}"
    if t == "Tesouro Selic":
        return f"Tesouro Selic {ano_venc}"
    if t == "Tesouro Prefixado":
        return f"Tesouro Prefixado {ano_venc}"
    if "Prefixado com Juros Semestrais" in t:
        return f"Tesouro Prefixado com Juros Semestrais {ano_venc}"
    if "Reserva" in t:
        return "Tesouro Reserva"
    return None


@st.cache_data(ttl=3600 * 2)
def buscar_titulos_tesouro(chave_cache: str) -> pd.DataFrame:
    """
    Busca preços e taxas de TODOS os títulos via CSV do Tesouro Transparente.

    Fonte: dados.tesourotransparente.gov.br — oficial, gratuita, sem autenticação.
    Filtra para a data mais recente disponível no arquivo e descarta títulos
    com vencimento em menos de 30 dias.
    """
    try:
        from io import StringIO

        resp = _get_com_retry(URL_TESOURO_CSV, timeout=30)
        df_raw = pd.read_csv(
            StringIO(resp.text),
            sep=";",
            decimal=",",
            dayfirst=True,
            parse_dates=["Data Vencimento", "Data Base"],
        )
        df_raw.columns = df_raw.columns.str.strip()

        data_ref = df_raw["Data Base"].max()
        df = df_raw[df_raw["Data Base"] == data_ref].copy()

        hoje = pd.Timestamp(date.today())
        df = df[df["Data Vencimento"] > hoje + pd.Timedelta(days=30)]
        df = df[~df["Tipo Titulo"].str.contains("IGPM", na=False)]

        def _f(v):
            try:
                return float(str(v).replace(",", ".").replace(" ", "")) or 0.0
            except Exception:
                return 0.0

        nomes_validos = set(TITULOS_CONFIG) | set(TITULOS_BATALHA)

        registros = []
        for _, row in df.iterrows():
            tipo_csv = str(row["Tipo Titulo"]).strip()
            venc = row["Data Vencimento"]
            if pd.isnull(venc):
                continue
            nome = construir_nome_titulo(tipo_csv, venc.year)
            if not nome or nome not in nomes_validos:
                continue
            registros.append(
                {
                    "nome": nome,
                    "vencimento": venc.strftime("%Y-%m-%d"),
                    "taxa_compra": _f(row.get("Taxa Compra Manha", 0)),
                    "taxa_venda": _f(row.get("Taxa Venda Manha", 0)),
                    "pu_compra": _f(row.get("PU Compra Manha", 0)),
                    "pu_venda": _f(row.get("PU Venda Manha", 0)),
                }
            )

        if not registros:
            return _titulos_fallback()

        df_out = pd.DataFrame(registros).reset_index(drop=True)
        df_out["_is_fallback"] = False
        return df_out

    except Exception as e:
        _log.warning(
            "Tesouro Direto CSV indisponível (%s) — usando taxas de referência locais",
            e,
        )
        return _titulos_fallback()


def _titulos_fallback() -> pd.DataFrame:
    """
    Dados de referência para quando o CSV do Tesouro Transparente está indisponível.
    Inclui IPCA+, RendA+, Educar+ (via TITULOS_CONFIG) e Selic/Prefixado (via TITULOS_BATALHA).
    Data de extração de _TAXAS_REF: ver comentário acima do dict (atualizado por
    scripts/atualizar_taxas_ref.py).
    """
    hoje = date.today()
    # Usa VNA calculado pelo IPCA acumulado real (muito mais preciso que VNA_FALLBACK 5% flat)
    _vna_fb = calcular_vna_via_bcb(_ipca_fallback())
    registros = []

    for nome, cfg in TITULOS_CONFIG.items():
        venc = cfg["vencimento"]
        if venc <= hoje:
            continue
        taxa = _TAXAS_REF.get(nome, 7.50)
        T = max(0.1, (venc - hoje).days / 365)
        pu = round(_vna_fb / (1 + taxa / 100) ** T, 2)
        registros.append(
            {
                "nome": nome,
                "vencimento": venc.isoformat(),
                "taxa_compra": taxa,
                "taxa_venda": round(taxa + 0.03, 2),
                "pu_compra": pu,
                "pu_venda": round(pu * 0.995, 2),
            }
        )

    for nome, cfg in TITULOS_BATALHA.items():
        if cfg["tipo"] not in ("selic", "pre"):
            continue
        venc = cfg["vencimento"]
        if venc <= hoje:
            continue
        taxa = cfg.get("taxa_ref") or (14.75 if cfg["tipo"] == "selic" else 14.0)
        registros.append(
            {
                "nome": nome,
                "vencimento": venc.isoformat(),
                "taxa_compra": taxa,
                "taxa_venda": round(taxa + 0.02, 2),
                "pu_compra": 0.0,
                "pu_venda": 0.0,
            }
        )

    df_fb = pd.DataFrame(registros)
    df_fb["_is_fallback"] = True
    return df_fb


# ---------------------------------------------------------------------------
# Ponto de entrada central
# ---------------------------------------------------------------------------


def montar_catalogo_batalha(df_titulos: pd.DataFrame, selic_projetada: float) -> list:
    """
    Monta catálogo dinâmico de todos os títulos para a tela 'Qual Ativo Escolher?'.

    Fonte primária: DataFrame completo do Tesouro Transparente (CSV).
    Para Selic: sobrescreve a taxa com a projeção do usuário (pós-fixado acompanha Selic).
    """
    hoje = date.today()
    catalogo = []

    df = df_titulos if not df_titulos.empty else _titulos_fallback()

    for _, row in df.iterrows():
        nome = str(row["nome"]).strip()
        try:
            venc = date.fromisoformat(str(row["vencimento"])[:10])
        except Exception:
            continue

        if venc <= hoje + timedelta(days=30):
            continue

        anos = round((venc - hoje).days / 365, 2)

        if "Selic" in nome or "Reserva" in nome:
            tipo = "selic"
            taxa = selic_projetada
        elif "Prefixado" in nome:
            tipo = "pre"
            _v = row.get("taxa_compra")
            taxa = float(_v) if _v is not None and float(_v) > 0 else 14.0
        else:
            tipo = "ipca_mais"
            _v = row.get("taxa_compra")
            taxa = float(_v) if _v is not None and float(_v) > 0 else 7.50

        catalogo.append(
            {
                "nome": nome,
                "tipo": tipo,
                "vencimento": venc,
                "anos_total": anos,
                "taxa": taxa,
            }
        )

    # Complementa com títulos do TITULOS_CONFIG que não vieram no CSV
    # (ex: RendA+ não é distribuído pelo endpoint padrão do Tesouro Transparente)
    nomes_no_catalogo = {t["nome"] for t in catalogo}
    for nome, cfg in TITULOS_CONFIG.items():
        if nome in nomes_no_catalogo:
            continue
        venc = cfg["vencimento"]
        if venc <= hoje + timedelta(days=30):
            continue
        anos = round((venc - hoje).days / 365, 2)
        taxa = _TAXAS_REF.get(nome, 7.50)
        catalogo.append(
            {
                "nome": nome,
                "tipo": "ipca_mais",
                "vencimento": venc,
                "anos_total": anos,
                "taxa": taxa,
            }
        )

    # Dedup por nome — CSV com entradas duplicadas não deve criar itens duplicados no catálogo
    seen: set = set()
    catalogo_dedup = []
    for item in catalogo:
        if item["nome"] not in seen:
            seen.add(item["nome"])
            catalogo_dedup.append(item)

    ordem = {"selic": 0, "pre": 1, "ipca_mais": 2}
    return sorted(
        catalogo_dedup, key=lambda x: (ordem.get(x["tipo"], 3), x["vencimento"])
    )


def obter_dados_completos() -> tuple[pd.DataFrame, pd.DataFrame, float]:
    """
    Retorna todos os dados necessários para as telas do app.

    Returns
    -------
    df_ipca    : série histórica mensal do IPCA
    df_titulos : preços e taxas dos títulos Tesouro IPCA+
    vna        : VNA estimado atual (R$)

    Efeito colateral: registra `st.session_state["_status_dados"]` indicando
    se alguma fonte está usando dados de fallback (API indisponível).
    """
    df_ipca = buscar_ipca_bcb()
    df_titulos = buscar_titulos_tesouro(chave_cache_mercado())
    vna = calcular_vna_via_bcb(df_ipca)

    def _e_fallback(df: pd.DataFrame) -> bool:
        if df.empty or "_is_fallback" not in df.columns:
            return False
        return bool(df["_is_fallback"].iloc[0])

    st.session_state["_status_dados"] = {
        "ipca_fallback": _e_fallback(df_ipca),
        "titulos_fallback": _e_fallback(df_titulos),
    }

    return df_ipca, df_titulos, vna
