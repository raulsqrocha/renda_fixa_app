"""
Módulo de cálculos financeiros para títulos Tesouro IPCA+ (NTN-B).

Fórmulas baseadas na metodologia ANBIMA de precificação de títulos públicos.
"""

import numpy as np
import pandas as pd
from datetime import date, timedelta
from typing import List


# ---------------------------------------------------------------------------
# Calendário oficial ANBIMA — feriados nacionais para precificação
# ---------------------------------------------------------------------------

def _computar_feriados_anbima(ano_inicio: int = 2015, ano_fim: int = 2070) -> list:
    """
    Gera os feriados nacionais reconhecidos pela ANBIMA.

    Feriados variáveis (Carnaval, Sexta-feira Santa, Corpus Christi) são
    derivados da Páscoa pelo algoritmo de Gauss.
    Consciência Negra (nov/20) incluída para todo o período — observada como
    não-útil bancário em São Paulo desde 2004 e nacional a partir de 2024.
    """
    feriados = []
    for ano in range(ano_inicio, ano_fim + 1):
        # Páscoa — algoritmo de Gauss
        a = ano % 19
        b = ano // 100
        c = ano % 100
        d = b // 4
        e = b % 4
        f = (b + 8) // 25
        g = (b - f + 1) // 3
        h = (19 * a + b - d - g + 15) % 30
        i = c // 4
        k = c % 4
        l = (32 + 2 * e + 2 * i - h - k) % 7
        m = (a + 11 * h + 22 * l) // 451
        mes_p = (h + l - 7 * m + 114) // 31
        dia_p = ((h + l - 7 * m + 114) % 31) + 1
        pascoa = date(ano, mes_p, dia_p)

        feriados += [
            pascoa - timedelta(days=48),   # Segunda de Carnaval
            pascoa - timedelta(days=47),   # Terça de Carnaval
            pascoa - timedelta(days=2),    # Sexta-feira Santa
            pascoa + timedelta(days=60),   # Corpus Christi
            date(ano, 1,  1),              # Ano Novo
            date(ano, 4,  21),             # Tiradentes
            date(ano, 5,  1),              # Dia do Trabalho
            date(ano, 9,  7),              # Independência do Brasil
            date(ano, 10, 12),             # Nossa Senhora Aparecida
            date(ano, 11, 2),              # Finados
            date(ano, 11, 15),             # Proclamação da República
            date(ano, 11, 20),             # Consciência Negra
            date(ano, 12, 25),             # Natal
        ]
    return sorted(set(feriados))


_CALENDARIO_ANBIMA = np.busdaycalendar(
    holidays=[np.datetime64(d, 'D') for d in _computar_feriados_anbima()]
)


def formatar_brl(valor: float, casas: int = 2) -> str:
    """Formata um valor no padrão monetário brasileiro: R$ 1.234,56"""
    fmt = f"{valor:,.{casas}f}"
    return "R$ " + fmt.replace(",", "X").replace(".", ",").replace("X", ".")


# ---------------------------------------------------------------------------
# Utilitários de datas
# ---------------------------------------------------------------------------

def calcular_du(data_inicio: date, data_fim: date) -> int:
    """
    Dias úteis entre duas datas usando o calendário oficial ANBIMA.
    Feriados computados algoritmicamente: Páscoa (Gauss) + fixos nacionais.
    Cobre 2015–2070, sem aproximações.
    """
    return max(0, int(np.busday_count(
        np.datetime64(data_inicio, 'D'),
        np.datetime64(data_fim, 'D'),
        busdaycal=_CALENDARIO_ANBIMA,
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


# ---------------------------------------------------------------------------
# Batalha de Cenários — Pré vs Pós vs IPCA+
# ---------------------------------------------------------------------------

def retorno_saida_antecipada(
    taxa_compra: float,
    taxa_venda: float,
    anos_total: float,
    anos_saida: float,
    tipo: str,
    ipca: float = 0.0,
) -> float:
    """
    Retorno nominal anualizado ao vender um título em anos_saida.

    Se anos_saida >= anos_total: retorno certo de carrego (sem exposição MaM).
    Se anos_saida < anos_total:  retorno ajustado pelo preço de mercado na saída.

    Para Prefixado:
        PU_H/PU_0 = (1+taxa_compra)^T / (1+taxa_venda)^(T-H)
    Para IPCA+:
        PU_H/PU_0 = (1+IPCA)^H × (1+taxa_compra)^T / (1+taxa_venda)^(T-H)
    Para Selic:
        Retorno ≈ taxa_compra (pós-fixado — taxa_venda não afeta preço)
    """
    H = anos_saida
    T = anos_total

    if tipo == "selic":
        return taxa_compra

    if H >= T:
        if tipo == "pre":
            return taxa_compra
        else:
            return (1 + ipca) * (1 + taxa_compra) - 1

    if tipo == "pre":
        ratio = (1 + taxa_compra) ** T / (1 + taxa_venda) ** (T - H)
        return ratio ** (1 / H) - 1
    else:
        ratio = (1 + ipca) ** H * (1 + taxa_compra) ** T / (1 + taxa_venda) ** (T - H)
        return ratio ** (1 / H) - 1


def aliquota_ir_renda_fixa(horizonte_anos: float) -> float:
    """Alíquota regressiva de IR sobre renda fixa (Tesouro Direto)."""
    dias = horizonte_anos * 365
    if dias <= 180:  return 0.225
    if dias <= 360:  return 0.200
    if dias <= 720:  return 0.175
    return 0.150


# Tabela oficial do IOF regressivo sobre rendimentos de renda fixa (Decreto 6.306/2007)
# Índice 0 = dia 1, índice 28 = dia 29; dia 30+ → 0%
_IOF_TABELA = [
    96, 93, 90, 86, 83, 80, 76, 73, 70, 66,   # dias 1–10
    63, 60, 56, 53, 50, 46, 43, 40, 36, 33,   # dias 11–20
    30, 26, 23, 20, 16, 13, 10,  6,  3,  0,   # dias 21–30
]


def aliquota_iof_renda_fixa(dias: int) -> float:
    """
    Alíquota de IOF regressivo sobre o rendimento de aplicações de renda fixa.

    Incide sobre o rendimento (não sobre o principal).
    Dia 1: 96% → Dia 29: 3% → Dia 30+: 0%
    """
    if dias <= 0:
        return 1.0
    if dias >= 30:
        return 0.0
    return _IOF_TABELA[dias - 1] / 100.0


def retorno_liquido_ir(retorno_bruto_anual: float, horizonte_anos: float) -> float:
    """
    Converte retorno bruto anualizado em retorno líquido após IR regressivo.

    IR incide sobre o lucro nominal acumulado no período.
    Prejuízo (lucro <= 0) não sofre IR — retorno bruto é mantido.
    """
    aliq  = aliquota_ir_renda_fixa(horizonte_anos)
    lucro = (1 + retorno_bruto_anual) ** horizonte_anos - 1
    if lucro <= 0:
        return retorno_bruto_anual
    lucro_liq = lucro * (1 - aliq)
    return (1 + lucro_liq) ** (1 / horizonte_anos) - 1


def retorno_hold_to_mat_reinvestido(
    taxa_compra: float,
    anos_total: float,
    anos_saida: float,
    tipo: str,
    ipca: float,
    selic: float,
    com_ir: bool,
) -> float:
    """
    Retorno anualizado combinado quando o título vence ANTES do horizonte do cliente.

    Fase 1 (T anos): carrego até o vencimento — IR pela tabela regressiva com prazo T.
    Fase 2 (H−T anos): resgate líquido reinvestido a 100% da Selic projetada — IR pelo prazo H−T.

    Parâmetros em decimal (ex: 0.135 = 13,5%).
    """
    T = anos_total
    H = anos_saida

    # Fase 1: fator bruto no vencimento do título
    if tipo == "pre":
        fator_bruto_T = (1 + taxa_compra) ** T
    else:  # ipca_mais
        fator_bruto_T = ((1 + ipca) * (1 + taxa_compra)) ** T

    lucro_T = fator_bruto_T - 1
    if com_ir and lucro_T > 0:
        fator_liq_T = 1.0 + lucro_T * (1.0 - aliquota_ir_renda_fixa(T))
    else:
        fator_liq_T = fator_bruto_T

    # Fase 2: reinvestimento a Selic pelos anos restantes
    anos_rest = H - T
    fator_bruto_2 = (1 + selic) ** anos_rest
    lucro_2 = fator_bruto_2 - 1
    if com_ir and lucro_2 > 0:
        fator_liq_2 = 1.0 + lucro_2 * (1.0 - aliquota_ir_renda_fixa(anos_rest))
    else:
        fator_liq_2 = fator_bruto_2

    return (fator_liq_T * fator_liq_2) ** (1.0 / H) - 1.0


def analise_batalha(
    nome: str,
    tipo: str,
    taxa: float,
    anos_total: float,
    anos_saida: float,
    ipca: float,
    choque: float = 0.01,
    com_ir: bool = False,
    selic: float = 0.0,
) -> dict:
    """
    Calcula retorno e risco para um título nos três cenários de taxa.

    Cenários (choque de 1 p.p. por padrão):
      Adverso   — taxas sobem (Selic: taxas caem  → rende menos)
      Neutro    — taxas inalteradas
      Favorável — taxas caem  (Selic: taxas sobem → rende mais)

    Risco = desvio-padrão dos três retornos anualizados.
    Se com_ir=True, IR regressivo é aplicado sobre o lucro antes do cálculo de risco.
    """
    t  = taxa  / 100
    ip = ipca  / 100
    ck = choque / 100
    sl = selic  / 100

    # Reinvestimento: título vence ANTES do horizonte do cliente.
    # IR aplicado dentro de retorno_hold_to_mat_reinvestido com prazo correto por fase.
    _reinvest = anos_saida > anos_total and sl > 0 and tipo != "selic"

    if tipo == "selic":
        # Pós-fixado: sem MaM, retorno acompanha Selic — adverso = Selic cai
        r_adv = retorno_saida_antecipada(max(t - ck, 0.005), max(t - ck, 0.005), anos_total, anos_saida, "selic")
        r_neu = retorno_saida_antecipada(t,      t,      anos_total, anos_saida, "selic")
        r_fav = retorno_saida_antecipada(t + ck, t + ck, anos_total, anos_saida, "selic")
        if com_ir:
            r_adv = retorno_liquido_ir(r_adv, anos_saida)
            r_neu = retorno_liquido_ir(r_neu, anos_saida)
            r_fav = retorno_liquido_ir(r_fav, anos_saida)
    elif _reinvest:
        # Título vence antes do horizonte: Fase 1 = carrego até T; Fase 2 = Selic por H−T.
        # Adverso/Favorável refletem variação da Selic na fase de reinvestimento.
        r_adv = retorno_hold_to_mat_reinvestido(t, anos_total, anos_saida, tipo, ip, max(sl - ck, 0.005), com_ir)
        r_neu = retorno_hold_to_mat_reinvestido(t, anos_total, anos_saida, tipo, ip, sl,           com_ir)
        r_fav = retorno_hold_to_mat_reinvestido(t, anos_total, anos_saida, tipo, ip, sl + ck,      com_ir)
    else:
        # Saída antecipada (H < T) ou H == T: MaM determina o retorno
        r_adv = retorno_saida_antecipada(t, t + ck, anos_total, anos_saida, tipo, ip)
        r_neu = retorno_saida_antecipada(t, t,      anos_total, anos_saida, tipo, ip)
        r_fav = retorno_saida_antecipada(t, t - ck, anos_total, anos_saida, tipo, ip)
        if com_ir:
            r_adv = retorno_liquido_ir(r_adv, anos_saida)
            r_neu = retorno_liquido_ir(r_neu, anos_saida)
            r_fav = retorno_liquido_ir(r_fav, anos_saida)

    risco_std = float(np.std([r_adv, r_neu, r_fav]))
    if not np.isfinite(risco_std):
        risco_std = 0.0

    anos_expo = max(0.0, anos_total - anos_saida)
    if tipo == "selic" or anos_expo == 0:
        risco_label = "🟢 Baixo"
    elif anos_expo <= 2:
        risco_label = "🟡 Moderado"
    elif anos_expo <= 5:
        risco_label = "🟠 Médio-Alto"
    else:
        risco_label = "🔴 Alto"

    r_real_neu = (1 + r_neu) / (1 + ip) - 1 if ip > 0 else r_neu

    return {
        "nome":        nome,
        "tipo":        tipo,
        "ret_adv":     r_adv  * 100,
        "ret_neu":     r_neu  * 100,
        "ret_fav":     r_fav  * 100,
        "ret_real":    r_real_neu * 100,
        "risco_std":   risco_std  * 100,
        "risco_label": risco_label,
        "anos_expo":   anos_expo,
        "hold_to_mat": anos_saida >= anos_total,
        "reinvest":    _reinvest,
    }


def gerar_portfolios_aleatorios(analises: list, n: int = 400, seed: int = 42) -> list:
    """
    Gera n portfólios aleatórios via amostragem Dirichlet (Monte Carlo).
    Usado para plotar a nuvem de pontos da fronteira eficiente de Markowitz.
    """
    k = len(analises)
    if k < 2:
        return []
    rng = np.random.default_rng(seed)
    adv = np.array([a["ret_adv"] for a in analises])
    neu = np.array([a["ret_neu"] for a in analises])
    fav = np.array([a["ret_fav"] for a in analises])
    out = []
    for _ in range(n):
        w     = rng.dirichlet(np.ones(k))
        r_adv = float(w @ adv)
        r_neu = float(w @ neu)
        r_fav = float(w @ fav)
        out.append({
            "ret_adv":   r_adv,
            "ret_neu":   r_neu,
            "ret_fav":   r_fav,
            "risco_std": float(np.std([r_adv, r_neu, r_fav])),
        })
    return out


def carteira_mista(
    analise_principal: dict,
    analise_liquida: dict,
    peso_principal: float = 0.70,
) -> dict:
    """
    Métricas de uma carteira com dois ativos nos três cenários de taxa.

    Retorno combinado = média ponderada dos retornos de cada cenário.
    Risco = desvio-padrão dos três retornos ponderados.
    (Modelo co-movimento: mesmos choques macroeconômicos nos dois ativos.)
    """
    wl = 1.0 - peso_principal

    r_adv = peso_principal * analise_principal["ret_adv"] + wl * analise_liquida["ret_adv"]
    r_neu = peso_principal * analise_principal["ret_neu"] + wl * analise_liquida["ret_neu"]
    r_fav = peso_principal * analise_principal["ret_fav"] + wl * analise_liquida["ret_fav"]
    risco = float(np.std([r_adv, r_neu, r_fav]))

    return {
        "ret_adv":        r_adv,
        "ret_neu":        r_neu,
        "ret_fav":        r_fav,
        "risco_std":      risco,
        "peso_principal": peso_principal,
        "peso_liquida":   wl,
        "nome_principal": analise_principal["nome"],
        "nome_liquida":   analise_liquida["nome"],
        "tipo_principal": analise_principal["tipo"],
    }



def fv_mensal(taxa_a: float, n_meses: int, cap: float, pmt: float, aliq: float) -> dict:
    """Valor futuro com aportes mensais. IR sobre o ganho total no vencimento."""
    r_m = (1 + taxa_a) ** (1 / 12) - 1 if taxa_a > 0 else 0.0
    n = float(n_meses)
    if n == 0:
        return {"fv_liq": cap, "fv_bruto": cap, "total_inv": cap, "ir": 0.0}
    fator = (1 + r_m) ** n_meses
    fv_bruto  = cap * fator + (pmt * (fator - 1) / r_m if abs(r_m) > 1e-10 else pmt * n)
    total_inv = cap + pmt * n
    ganho     = max(0.0, fv_bruto - total_inv)
    ir        = ganho * aliq
    return {"fv_liq": fv_bruto - ir, "fv_bruto": fv_bruto, "total_inv": total_inv, "ir": ir}


def pmt_para_meta(taxa_a: float, n_meses: int, cap: float, meta: float, aliq: float) -> float:
    """Aporte mensal necessário para atingir 'meta' líquida dado capital inicial."""
    r_m = (1 + taxa_a) ** (1 / 12) - 1 if taxa_a > 0 else 0.0
    n = float(n_meses)
    if n <= 0:
        return max(0.0, meta - cap)
    fator = (1 + r_m) ** n_meses
    if abs(r_m) < 1e-10:
        A, B = cap, n
    else:
        A = cap * (fator * (1 - aliq) + aliq)
        B = (fator - 1) / r_m * (1 - aliq) + n * aliq
    return max(0.0, (meta - A) / B) if B > 0 else 0.0


