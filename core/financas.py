"""
Módulo de cálculos financeiros para títulos Tesouro IPCA+ (NTN-B).

Fórmulas baseadas na metodologia ANBIMA de precificação de títulos públicos.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import List


# ---------------------------------------------------------------------------
# Utilitários de datas
# ---------------------------------------------------------------------------

def calcular_du(data_inicio: date, data_fim: date) -> int:
    """
    Dias úteis entre duas datas usando convenção brasileira 252 d.u./ano.
    Aproximação sem feriados nacionais — aceitável para fins educacionais.
    """
    return max(0, int(np.busday_count(
        np.datetime64(data_inicio, 'D'),
        np.datetime64(data_fim, 'D'),
    )))


def datas_cupom_ntnb(data_hoje: date, data_vencimento: date) -> List[date]:
    """
    Gera lista de datas de pagamento de cupons NTN-B.
    Por convenção ANBIMA: 15 de maio e 15 de novembro de cada ano.
    """
    datas: List[date] = []
    for ano in range(data_hoje.year, data_vencimento.year + 1):
        for mes in (5, 11):
            dt = date(ano, mes, 15)
            if data_hoje < dt <= data_vencimento:
                datas.append(dt)
    return sorted(datas)


# ---------------------------------------------------------------------------
# Precificação NTN-B (Tesouro IPCA+)
# ---------------------------------------------------------------------------

def cupom_semestral(vna: float, taxa_cupom_anual: float = 0.06) -> float:
    """
    Valor do cupom semestral NTN-B.

    C = VNA × [(1 + 0,06)^(1/2) − 1]

    A NTN-B paga juros semestrais de 6% a.a. nominal sobre o VNA vigente.
    """
    return vna * ((1 + taxa_cupom_anual) ** 0.5 - 1)


def pu_ntnb(
    vna: float,
    taxa_real: float,
    data_hoje: date,
    data_vencimento: date,
    datas_cupom: List[date],
    taxa_cupom_anual: float = 0.06,
) -> float:
    """
    Preço Unitário (PU) da NTN-B com cupons semestrais.

    Fórmula ANBIMA:
        PU = Σᵢ [ C / (1 + r)^(duᵢ/252) ]  +  VNA / (1 + r)^(duₙ/252)

    Parâmetros
    ----------
    vna          : Valor Nominal Atualizado (corrigido pelo IPCA)
    taxa_real    : Yield real de mercado ao ano em decimal (ex: 0.075 = 7,5%)
    data_hoje    : Data de referência da precificação
    data_vencimento : Data de vencimento do título
    datas_cupom  : Lista com as datas futuras de pagamento de cupom
    taxa_cupom_anual : Taxa de cupom nominal anual (padrão NTN-B: 6%)
    """
    C = cupom_semestral(vna, taxa_cupom_anual)
    pu = 0.0

    for dt_cupom in datas_cupom:
        if dt_cupom > data_hoje:
            du = calcular_du(data_hoje, dt_cupom)
            if du > 0:
                pu += C / (1 + taxa_real) ** (du / 252)

    du_principal = calcular_du(data_hoje, data_vencimento)
    if du_principal > 0:
        pu += vna / (1 + taxa_real) ** (du_principal / 252)

    return pu


# ---------------------------------------------------------------------------
# Métricas do Dashboard
# ---------------------------------------------------------------------------

def taxa_diaria_simulada(taxa_base: float, data_ref: date, choque_bps: float = 3.0) -> float:
    """
    Gera uma variação de taxa determinística por dia (seed = data).
    Garante consistência no mesmo dia e variação entre dias.
    """
    seed = int(data_ref.strftime('%Y%m%d'))
    rng = np.random.default_rng(seed)
    return taxa_base + rng.normal(0, choque_bps / 10_000)


def metricas_carteira(
    valor_investido: float,
    pu_na_compra: float,
    taxa_real_contratada: float,
    taxa_real_mercado: float,
    vna: float,
    data_hoje: date,
    data_vencimento: date,
    datas_cupom: List[date],
) -> dict:
    """
    Calcula os três valores-chave do Dashboard:

    - mam        : valor de resgate antecipado hoje (Marcação a Mercado)
    - vencimento : valor estimado se aguardar o prazo (taxa contratada)
    - variacao_dia: variação percentual do PU hoje vs. ontem (simulada)
    - quantidade  : unidades do título na carteira
    """
    quantidade = valor_investido / pu_na_compra

    # Taxa de ontem simulada (seed da data anterior — consistente e realista)
    taxa_ontem = taxa_diaria_simulada(taxa_real_mercado, data_hoje - timedelta(days=1))

    pu_hoje   = pu_ntnb(vna, taxa_real_mercado, data_hoje, data_vencimento, datas_cupom)
    pu_ontem  = pu_ntnb(vna, taxa_ontem,        data_hoje, data_vencimento, datas_cupom)
    pu_carrego = pu_ntnb(vna, taxa_real_contratada, data_hoje, data_vencimento, datas_cupom)

    return {
        'mam':          quantidade * pu_hoje,
        'vencimento':   quantidade * pu_carrego,
        'variacao_dia': (pu_hoje / pu_ontem - 1) * 100,
        'pu_hoje':      pu_hoje,
        'pu_carrego':   pu_carrego,
        'quantidade':   quantidade,
    }


# ---------------------------------------------------------------------------
# Série Temporal para o Gráfico do Paradoxo
# ---------------------------------------------------------------------------

def serie_paradoxo(
    vna: float,
    taxa_real_contratada: float,
    taxa_real_mercado: float,
    data_compra: date,
    data_vencimento: date,
    quantidade: float,
    tem_cupom: bool = True,
    amostragem: int = 5,
) -> pd.DataFrame:
    """
    Gera as duas curvas do Gráfico do Paradoxo.

    Linha MaM (vermelha):
        Taxa de mercado evolui em random walk — reproduz a volatilidade percebida.

    Linha Carrego (verde):
        Taxa contratada fixa — reproduz a trajetória real do investimento.

    tem_cupom=True  (Juros Semestrais): ambas as linhas usam pu_ntnb() com cupons,
        produzindo o padrão em dente de serra natural após cada pagamento semestral.

    tem_cupom=False (Principal): ambas as linhas usam desconto simples VNA/(1+r)^(du/252),
        produzindo uma curva exponencial perfeitamente lisa e ascendente.

    O parâmetro `amostragem` (a cada N dias úteis) controla a performance.
    Valor padrão 5 = amostragem semanal, suficiente para o gráfico educacional.
    """
    datas_todas = pd.bdate_range(data_compra, data_vencimento)
    datas = datas_todas[::amostragem]
    n = len(datas)

    # Volatilidade escalada pela duração modificada do título.
    # Títulos ultra-longos (ex: RendA+ 2065, T≈40) são muito mais sensíveis
    # a variações de taxa — o preço oscila ~10x mais que um IPCA+ 2029 (T≈3).
    anos_totais  = (data_vencimento - data_compra).days / 365
    duracao_mod  = anos_totais / (1 + taxa_real_mercado)
    sigma = 0.0001 * max(1.0, duracao_mod / 5)   # escala linear com duração/5

    # Seed fixo garante que o gráfico não mude a cada reload.
    # Sem mean-centering: permite drift realista das taxas ao longo do prazo.
    rng = np.random.default_rng(seed=42)
    shocks    = rng.normal(0, sigma, n)
    taxas_mam = taxa_real_mercado + np.cumsum(shocks)
    taxas_mam = np.clip(taxas_mam, 0.02, 0.20)

    vals_mam, vals_carrego = [], []

    for i, dt in enumerate(datas.date):
        if dt >= data_vencimento:
            vals_mam.append(quantidade * vna)
            vals_carrego.append(quantidade * vna)
            continue

        du = calcular_du(dt, data_vencimento)

        if tem_cupom:
            # Juros Semestrais: PU inclui fluxo de cupons → dente de serra natural
            cpns = datas_cupom_ntnb(dt, data_vencimento)
            vals_mam.append(pu_ntnb(vna, taxas_mam[i], dt, data_vencimento, cpns) * quantidade)
            vals_carrego.append(pu_ntnb(vna, taxa_real_contratada, dt, data_vencimento, cpns) * quantidade)
        else:
            # Principal: desconto simples sem cupons → curva exponencial lisa
            if du > 0:
                vals_mam.append(quantidade * vna / (1 + taxas_mam[i]) ** (du / 252))
                vals_carrego.append(quantidade * vna / (1 + taxa_real_contratada) ** (du / 252))
            else:
                vals_mam.append(quantidade * vna)
                vals_carrego.append(quantidade * vna)

    n_real = len(vals_mam)
    return pd.DataFrame({
        'data':    datas[:n_real],
        'mam':     vals_mam,
        'carrego': vals_carrego,
    })


# ---------------------------------------------------------------------------
# Simulador de MaM — Venda Antecipada
# ---------------------------------------------------------------------------

def retorno_mam_antecipado(
    taxa_compra: float,
    taxa_venda: float,
    anos_saida: float,
    anos_vencimento: float,
) -> float:
    """
    Retorno de MaM ao vender antecipadamente — impacto puro da variação da taxa real.

    O VNA (corrigido pelo IPCA) cancela algebraicamente na razão PU_mercado / PU_ideal:

        PU_ideal   = VNA_futuro / (1 + taxa_compra)^(T−N)
        PU_mercado = VNA_futuro / (1 + taxa_venda)^(T−N)

        Retorno = PU_mercado / PU_ideal − 1
                = [(1 + taxa_compra) / (1 + taxa_venda)]^(T−N) − 1

    Consequência: o IPCA futuro NÃO entra na fórmula — ele é contexto macroeconômico
    que explica por que a taxa real mudou, mas não altera o cálculo diretamente.

    Parâmetros (em decimal, ex: 0.0715 = 7,15%)
    ----------
    taxa_compra    : yield IPCA+ real travado na data de compra
    taxa_venda     : yield IPCA+ real de mercado projetado na data de saída
    anos_saida     : horizonte de venda antecipada (anos)
    anos_vencimento: prazo total restante do título a partir de hoje (anos)
    """
    T, N = anos_vencimento, anos_saida
    if N <= 0 or N >= T:
        return float("nan")
    return ((1 + taxa_compra) / (1 + taxa_venda)) ** (T - N) * 100 - 100


# ---------------------------------------------------------------------------
# Simulação de Cenários de Inflação
# ---------------------------------------------------------------------------

def retorno_cenario_ipca(
    taxa_real: float,
    ipca_anual: float,
    anos: int,
    valor_inicial: float,
) -> dict:
    """
    Retorno do Tesouro IPCA+ em um cenário de IPCA projetado.

    Taxa nominal total = (1 + taxa_real) × (1 + IPCA) − 1
    O ganho real (acima da inflação) é travado pela taxa real contratada,
    independente do cenário de IPCA escolhido.
    """
    taxa_nominal = (1 + taxa_real) * (1 + ipca_anual) - 1
    valor_final  = valor_inicial * (1 + taxa_nominal) ** anos

    return {
        'taxa_nominal_aa':   taxa_nominal * 100,
        'valor_final':       valor_final,
        'retorno_nominal_pct': (valor_final / valor_inicial - 1) * 100,
        'retorno_real_pct':  ((1 + taxa_real) ** anos - 1) * 100,
    }
