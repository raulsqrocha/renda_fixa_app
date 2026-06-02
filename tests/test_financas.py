"""
Testes unitários para core/financas.py.

Cobre as funções financeiras críticas:
  - aliquota_ir_renda_fixa           : tabela regressiva de IR (todos os brackets)
  - aliquota_iof_renda_fixa          : tabela regressiva de IOF (dias 0–30+)
  - retorno_mam_antecipado           : fórmula de saída antecipada MaM
  - cupom_semestral                  : cálculo do cupom NTN-B (metodologia ANBIMA)
  - pu_ntnb                          : precificação completa da NTN-B
  - calcular_du                      : dias úteis com calendário ANBIMA
  - datas_cupom_ntnb                 : geração das datas de cupom (15/mai e 15/nov)
  - retorno_liquido_ir               : retorno líquido após IR regressivo
  - retorno_cenario_ipca             : simulação de cenário de inflação
  - metricas_carteira                : MaM, carrego e quantidade da posição
  - fv_mensal                        : valor futuro com aportes mensais
  - pmt_para_meta                    : aporte mensal para atingir meta líquida
  - retorno_saida_antecipada         : retorno MaM para saída antes do vencimento
  - retorno_hold_to_mat_reinvestido  : retorno com reinvestimento pós-vencimento
  - analise_batalha                  : análise de cenários para comparação de ativos
"""

import math
import pandas as pd
from datetime import date, timedelta

from core.financas import (
    aliquota_ir_renda_fixa,
    aliquota_iof_renda_fixa,
    formatar_brl,
    retorno_mam_antecipado,
    cupom_semestral,
    pu_ntnb,
    calcular_du,
    datas_cupom_ntnb,
    retorno_liquido_ir,
    retorno_cenario_ipca,
    serie_paradoxo,
    metricas_carteira,
    fv_mensal,
    pmt_para_meta,
    retorno_saida_antecipada,
    retorno_hold_to_mat_reinvestido,
    analise_batalha,
)


# ---------------------------------------------------------------------------
# Formatação monetária
# ---------------------------------------------------------------------------


class TestFormatarBrl:
    def test_valor_basico(self):
        assert formatar_brl(1234.56) == "R$ 1.234,56"

    def test_zero_casas_decimais(self):
        assert formatar_brl(1000.0, casas=0) == "R$ 1.000"

    def test_valor_pequeno(self):
        assert formatar_brl(0.50) == "R$ 0,50"

    def test_valor_zero(self):
        assert formatar_brl(0.0) == "R$ 0,00"

    def test_valor_negativo(self):
        # Valores negativos devem preservar o sinal antes do número
        resultado = formatar_brl(-1234.56)
        assert "R$ " in resultado
        assert "-" in resultado
        assert "1.234,56" in resultado


# ---------------------------------------------------------------------------
# IR Regressivo
# ---------------------------------------------------------------------------


class TestAliquotaIR:
    def test_ate_180_dias(self):
        assert aliquota_ir_renda_fixa(90 / 365) == 0.225

    def test_181_a_360_dias(self):
        assert aliquota_ir_renda_fixa(270 / 365) == 0.200

    def test_361_a_720_dias(self):
        assert aliquota_ir_renda_fixa(500 / 365) == 0.175

    def test_acima_720_dias(self):
        assert aliquota_ir_renda_fixa(800 / 365) == 0.150

    def test_limite_exato_180(self):
        # 180 dias <= 180 → 22.5%
        assert aliquota_ir_renda_fixa(180 / 365) == 0.225

    def test_limite_181(self):
        # 181 dias → 20%
        assert aliquota_ir_renda_fixa(181 / 365) == 0.200

    def test_limite_exato_720(self):
        # 720 dias <= 720 → 17.5%
        assert aliquota_ir_renda_fixa(720 / 365) == 0.175

    def test_limite_721(self):
        # 721 dias > 720 → 15%
        assert aliquota_ir_renda_fixa(721 / 365) == 0.150

    def test_longo_prazo(self):
        assert aliquota_ir_renda_fixa(10.0) == 0.150


# ---------------------------------------------------------------------------
# IOF Regressivo
# ---------------------------------------------------------------------------


class TestAliquotaIOF:
    def test_dia_0_sem_aplicacao(self):
        # Dia 0 ou menos → 100% (todo rendimento vai para IOF)
        assert aliquota_iof_renda_fixa(0) == 1.0

    def test_dia_1(self):
        assert aliquota_iof_renda_fixa(1) == 0.96

    def test_dia_10(self):
        assert aliquota_iof_renda_fixa(10) == 0.66

    def test_dia_15(self):
        # Posição 14 na tabela (índice base 0): 50%
        assert aliquota_iof_renda_fixa(15) == 0.50

    def test_dia_29(self):
        assert aliquota_iof_renda_fixa(29) == 0.03

    def test_dia_30_zero(self):
        assert aliquota_iof_renda_fixa(30) == 0.00

    def test_dia_acima_30(self):
        assert aliquota_iof_renda_fixa(60) == 0.00

    def test_tabela_decrescente(self):
        # A alíquota deve ser estritamente decrescente do dia 1 ao 29
        aliquotas = [aliquota_iof_renda_fixa(d) for d in range(1, 30)]
        for i in range(len(aliquotas) - 1):
            assert aliquotas[i] > aliquotas[i + 1]


# ---------------------------------------------------------------------------
# MaM — Retorno de Saída Antecipada
# ---------------------------------------------------------------------------


class TestRetornoMaM:
    def test_taxa_igual_retorno_zero(self):
        r = retorno_mam_antecipado(0.07, 0.07, anos_saida=1.0, anos_vencimento=5.0)
        assert abs(r) < 1e-9

    def test_taxa_sobe_perde(self):
        # Mercado foi para cima (taxa vendida > taxa comprada) → perde
        r = retorno_mam_antecipado(0.07, 0.09, anos_saida=1.0, anos_vencimento=5.0)
        assert r < 0

    def test_taxa_cai_ganha(self):
        # Mercado caiu (taxa vendida < taxa comprada) → ganha
        r = retorno_mam_antecipado(0.07, 0.05, anos_saida=1.0, anos_vencimento=5.0)
        assert r > 0

    def test_saida_zero_retorna_nan(self):
        assert math.isnan(retorno_mam_antecipado(0.07, 0.07, 0.0, 5.0))

    def test_saida_igual_vencimento_retorna_nan(self):
        assert math.isnan(retorno_mam_antecipado(0.07, 0.07, 5.0, 5.0))

    def test_saida_maior_vencimento_retorna_nan(self):
        assert math.isnan(retorno_mam_antecipado(0.07, 0.07, 6.0, 5.0))

    def test_formula_manual(self):
        # Fórmula: [(1+c)/(1+v)]^(T-N) * 100 - 100
        c, v, N, T = 0.07, 0.09, 2.0, 10.0
        esperado = ((1 + c) / (1 + v)) ** (T - N) * 100 - 100
        assert abs(retorno_mam_antecipado(c, v, N, T) - esperado) < 1e-9

    def test_titulo_longo_amplifica_perda(self):
        # Mesmo choque, prazo maior → perda maior (duration maior)
        r_curto = retorno_mam_antecipado(
            0.07, 0.09, anos_saida=1.0, anos_vencimento=3.0
        )
        r_longo = retorno_mam_antecipado(
            0.07, 0.09, anos_saida=1.0, anos_vencimento=15.0
        )
        assert r_longo < r_curto

    def test_titulo_longo_amplifica_ganho(self):
        # Mesmo choque positivo, prazo maior → ganho maior
        r_curto = retorno_mam_antecipado(
            0.07, 0.05, anos_saida=1.0, anos_vencimento=3.0
        )
        r_longo = retorno_mam_antecipado(
            0.07, 0.05, anos_saida=1.0, anos_vencimento=15.0
        )
        assert r_longo > r_curto

    def test_resultado_em_percentual(self):
        # A função retorna em %, não decimal
        r = retorno_mam_antecipado(0.07, 0.07, anos_saida=1.0, anos_vencimento=5.0)
        assert abs(r) < 1e-6  # próximo de 0% (não 0.0000…)

    def test_simetria_aproximada(self):
        # Ganhar com queda de 1pp deve ser próximo (mas não igual) de perder com alta de 1pp
        ganho = retorno_mam_antecipado(0.07, 0.06, 1.0, 5.0)
        perda = retorno_mam_antecipado(0.07, 0.08, 1.0, 5.0)
        assert ganho > 0 and perda < 0


# ---------------------------------------------------------------------------
# Cupom Semestral NTN-B
# ---------------------------------------------------------------------------


class TestCupomSemestral:
    def test_formula_anbima(self):
        # C = VNA × [(1 + 0,06)^0,5 − 1]
        vna = 4_000.0
        c = cupom_semestral(vna, 0.06)
        esperado = vna * ((1.06**0.5) - 1)
        assert abs(c - esperado) < 1e-9

    def test_proporcional_ao_vna(self):
        c1 = cupom_semestral(2_000.0)
        c2 = cupom_semestral(4_000.0)
        assert abs(c2 / c1 - 2.0) < 1e-9

    def test_taxa_diferente(self):
        vna = 3_000.0
        taxa = 0.08
        c = cupom_semestral(vna, taxa)
        esperado = vna * ((1 + taxa) ** 0.5 - 1)
        assert abs(c - esperado) < 1e-9

    def test_cupom_positivo(self):
        assert cupom_semestral(4_000.0, 0.06) > 0


# ---------------------------------------------------------------------------
# Preço Unitário NTN-B (pu_ntnb)
# ---------------------------------------------------------------------------


class TestPuNtnb:
    def test_sem_cupons_desconto_simples(self):
        """
        Sem datas de cupom, PU = VNA / (1+r)^(du/252).
        """
        vna = 4_000.0
        r = 0.07
        hoje = date(2025, 1, 2)
        venc = date(2026, 1, 2)
        du = calcular_du(hoje, venc)
        esperado = vna / (1 + r) ** (du / 252)
        pu = pu_ntnb(vna, r, hoje, venc, datas_cupom=[], taxa_cupom_anual=0.06)
        assert abs(pu - esperado) < 0.01

    def test_taxa_maior_reduz_pu(self):
        vna = 4_000.0
        hoje = date(2025, 1, 2)
        venc = date(2035, 5, 15)
        cupons = datas_cupom_ntnb(hoje, venc)
        pu_baixo = pu_ntnb(vna, 0.06, hoje, venc, cupons)
        pu_alto = pu_ntnb(vna, 0.10, hoje, venc, cupons)
        assert pu_baixo > pu_alto

    def test_pu_positivo(self):
        vna = 4_000.0
        hoje = date(2025, 1, 2)
        venc = date(2040, 8, 15)
        cupons = datas_cupom_ntnb(hoje, venc)
        pu = pu_ntnb(vna, 0.075, hoje, venc, cupons)
        assert pu > 0

    def test_proximo_vencimento_aproxima_vna(self):
        """Muito próximo do vencimento (sem cupons), PU deve estar bem próximo do VNA."""
        vna = 4_000.0
        venc = date(2025, 11, 15)
        # Um dia útil antes do vencimento
        hoje = date(2025, 11, 14)
        pu = pu_ntnb(vna, 0.07, hoje, venc, datas_cupom=[], taxa_cupom_anual=0.06)
        # Com apenas 1 DU de prazo, o desconto é mínimo — PU deve ser > 99,9% do VNA
        assert pu > vna * 0.999

    def test_cupom_aumenta_pu(self):
        """Com cupons, o PU deve ser maior que sem cupons (mesmo VNA e taxa)."""
        vna = 4_000.0
        r = 0.07
        hoje = date(2025, 1, 2)
        venc = date(2035, 5, 15)
        cupons = datas_cupom_ntnb(hoje, venc)
        pu_com_cupom = pu_ntnb(vna, r, hoje, venc, cupons)
        pu_sem_cupom = pu_ntnb(vna, r, hoje, venc, datas_cupom=[])
        assert pu_com_cupom > pu_sem_cupom

    def test_prazo_maior_reduz_pu(self):
        """Mesmo título com prazo mais longo tem PU menor (maior desconto)."""
        vna = 4_000.0
        r = 0.07
        hoje = date(2025, 1, 2)
        venc_curto = date(2030, 5, 15)
        venc_longo = date(2045, 5, 15)
        pu_curto = pu_ntnb(vna, r, hoje, venc_curto, datas_cupom_ntnb(hoje, venc_curto))
        pu_longo = pu_ntnb(vna, r, hoje, venc_longo, datas_cupom_ntnb(hoje, venc_longo))
        assert pu_curto > pu_longo


# ---------------------------------------------------------------------------
# Dias Úteis — calendário ANBIMA
# ---------------------------------------------------------------------------


class TestCalcularDu:
    def test_mesmo_dia_zero(self):
        d = date(2025, 6, 2)
        assert calcular_du(d, d) == 0

    def test_um_dia_util(self):
        # Terça → Quarta = 1 DU
        assert calcular_du(date(2025, 6, 3), date(2025, 6, 4)) == 1

    def test_fim_semana_excluido(self):
        # Sexta → Segunda: [Sex] = 1 DU (sáb e dom excluídos)
        sexta = date(2025, 5, 30)
        segunda = date(2025, 6, 2)
        assert calcular_du(sexta, segunda) == 1

    def test_semana_completa(self):
        # Segunda → Sexta: [Seg, Ter, Qua, Qui] = 4 DU (Sex é endpoint exclusivo)
        seg = date(2025, 6, 2)
        sex = date(2025, 6, 6)
        assert calcular_du(seg, sex) == 4

    def test_feriado_ano_novo(self):
        # Dec-31 → Jan-02: [31/dez] = 1 DU (Jan 1 é feriado, Jan 2 é endpoint)
        assert calcular_du(date(2024, 12, 31), date(2025, 1, 2)) == 1

    def test_feriado_tiradentes(self):
        # 21/abr/2025 é Tiradentes. Seg 21 → Ter 22: 0 DU (21 é feriado)
        assert calcular_du(date(2025, 4, 21), date(2025, 4, 22)) == 0

    def test_resultado_nao_negativo(self):
        # Data início > data fim → retorna 0 (não negativo)
        assert calcular_du(date(2025, 6, 5), date(2025, 6, 2)) == 0


# ---------------------------------------------------------------------------
# Datas de Cupom NTN-B
# ---------------------------------------------------------------------------


class TestDatasCupomNtnb:
    def test_gera_15_mai_e_15_nov(self):
        hoje = date(2025, 1, 1)
        venc = date(2026, 11, 15)
        datas = datas_cupom_ntnb(hoje, venc)
        assert date(2025, 5, 15) in datas
        assert date(2025, 11, 15) in datas
        assert date(2026, 5, 15) in datas
        assert date(2026, 11, 15) in datas

    def test_nao_inclui_passado(self):
        hoje = date(2025, 6, 1)
        venc = date(2027, 5, 15)
        datas = datas_cupom_ntnb(hoje, venc)
        for d in datas:
            assert d > hoje

    def test_nao_supera_vencimento(self):
        hoje = date(2025, 1, 1)
        venc = date(2027, 5, 15)
        datas = datas_cupom_ntnb(hoje, venc)
        for d in datas:
            assert d <= venc

    def test_ordenado(self):
        hoje = date(2025, 1, 1)
        venc = date(2030, 11, 15)
        datas = datas_cupom_ntnb(hoje, venc)
        assert datas == sorted(datas)


# ---------------------------------------------------------------------------
# Retorno Líquido após IR
# ---------------------------------------------------------------------------


class TestRetornoLiquidoIR:
    def test_sem_lucro_sem_ir(self):
        # Retorno zero: não há IR
        r = retorno_liquido_ir(0.0, 2.0)
        assert abs(r) < 1e-9

    def test_prejuizo_sem_ir(self):
        # Retorno negativo: não há IR
        r_bruto = -0.05
        r_liq = retorno_liquido_ir(r_bruto, 2.0)
        assert r_liq == r_bruto

    def test_liquido_menor_que_bruto(self):
        # Com ganho, líquido < bruto
        r_bruto = 0.10
        r_liq = retorno_liquido_ir(r_bruto, 2.0)
        assert r_liq < r_bruto

    def test_formula_1_ano(self):
        # 10% a.a. por 1 ano: dias = 365, alíq = 17.5% (361–720 dias)
        # lucro = 1.10^1 - 1 = 0.10 → lucro_liq = 0.10 * 0.825 = 0.0825
        # retorno_liq = (1.0825)^1 - 1 = 8.25%
        r_liq = retorno_liquido_ir(0.10, 1.0)
        assert abs(r_liq - 0.0825) < 1e-9

    def test_aliquota_longo_prazo(self):
        # Prazo longo (>720 dias) usa 15%
        r_bruto = 0.10
        r_liq_longo = retorno_liquido_ir(r_bruto, 3.0)
        r_liq_curto = retorno_liquido_ir(r_bruto, 0.3)
        # Prazo longo paga menos IR → retorno líquido maior
        assert r_liq_longo > r_liq_curto


# ---------------------------------------------------------------------------
# Cenário de IPCA
# ---------------------------------------------------------------------------


class TestRetornoCenarioIPCA:
    def test_taxa_nominal_formula(self):
        # taxa_nominal = (1 + real) * (1 + ipca) - 1
        real = 0.07
        ipca = 0.05
        res = retorno_cenario_ipca(real, ipca, 1, 1000.0)
        esperado = (1 + real) * (1 + ipca) - 1
        assert abs(res["taxa_nominal_aa"] / 100 - esperado) < 1e-9

    def test_ganho_real_travado(self):
        # O ganho real é determinístico: não depende do cenário de IPCA
        real = 0.07
        res_baixo = retorno_cenario_ipca(real, 0.03, 5, 1000.0)
        res_alto = retorno_cenario_ipca(real, 0.12, 5, 1000.0)
        assert abs(res_baixo["retorno_real_pct"] - res_alto["retorno_real_pct"]) < 1e-6

    def test_valor_final_correto(self):
        real = 0.07
        ipca = 0.05
        anos = 3
        cap = 1000.0
        res = retorno_cenario_ipca(real, ipca, anos, cap)
        nominal = (1 + real) * (1 + ipca) - 1
        esperado = cap * (1 + nominal) ** anos
        assert abs(res["valor_final"] - esperado) < 0.01

    def test_retorno_nominal_pct_correto(self):
        res = retorno_cenario_ipca(0.07, 0.05, 1, 1000.0)
        assert abs(res["retorno_nominal_pct"] - res["taxa_nominal_aa"]) < 1e-9


# ---------------------------------------------------------------------------
# Retorno de Saída Antecipada
# ---------------------------------------------------------------------------


class TestRetornoSaidaAntecipada:
    def test_anos_saida_zero_retorna_nan(self):
        import math

        assert math.isnan(retorno_saida_antecipada(0.14, 0.14, 5.0, 0.0, "pre"))

    # ---- Selic ----
    def test_selic_retorna_taxa_compra(self):
        r = retorno_saida_antecipada(
            0.135, 0.140, anos_total=5.0, anos_saida=2.0, tipo="selic"
        )
        assert r == 0.135

    def test_selic_ignora_taxa_venda(self):
        r1 = retorno_saida_antecipada(
            0.135, 0.10, anos_total=5.0, anos_saida=2.0, tipo="selic"
        )
        r2 = retorno_saida_antecipada(
            0.135, 0.20, anos_total=5.0, anos_saida=2.0, tipo="selic"
        )
        assert r1 == r2 == 0.135

    # ---- Pré-fixado hold-to-mat ----
    def test_pre_hold_to_mat_retorna_taxa_compra(self):
        r = retorno_saida_antecipada(
            0.14, 0.16, anos_total=5.0, anos_saida=5.0, tipo="pre"
        )
        assert r == 0.14

    def test_pre_alem_do_vencimento_retorna_taxa_compra(self):
        r = retorno_saida_antecipada(
            0.14, 0.16, anos_total=5.0, anos_saida=7.0, tipo="pre"
        )
        assert r == 0.14

    # ---- IPCA+ hold-to-mat ----
    def test_ipca_hold_to_mat_retorna_nominal(self):
        tc, ipca = 0.07, 0.05
        r = retorno_saida_antecipada(
            tc, 0.09, anos_total=5.0, anos_saida=5.0, tipo="ipca_mais", ipca=ipca
        )
        esperado = (1 + ipca) * (1 + tc) - 1
        assert abs(r - esperado) < 1e-12

    # ---- Pré-fixado saída antecipada ----
    def test_pre_taxa_igual_retorna_taxa_compra(self):
        # tv == tc → sem MaM → retorno = carrego
        r = retorno_saida_antecipada(
            0.14, 0.14, anos_total=10.0, anos_saida=3.0, tipo="pre"
        )
        assert abs(r - 0.14) < 1e-9

    def test_pre_taxa_sobe_retorno_cai(self):
        r_neutro = retorno_saida_antecipada(
            0.14, 0.14, anos_total=10.0, anos_saida=3.0, tipo="pre"
        )
        r_adverso = retorno_saida_antecipada(
            0.14, 0.15, anos_total=10.0, anos_saida=3.0, tipo="pre"
        )
        assert r_adverso < r_neutro

    def test_pre_taxa_cai_retorno_sobe(self):
        r_neutro = retorno_saida_antecipada(
            0.14, 0.14, anos_total=10.0, anos_saida=3.0, tipo="pre"
        )
        r_favoravel = retorno_saida_antecipada(
            0.14, 0.13, anos_total=10.0, anos_saida=3.0, tipo="pre"
        )
        assert r_favoravel > r_neutro

    def test_pre_formula_manual(self):
        tc, tv, T, H = 0.14, 0.16, 10.0, 3.0
        ratio = (1 + tc) ** T / (1 + tv) ** (T - H)
        esperado = ratio ** (1 / H) - 1
        r = retorno_saida_antecipada(tc, tv, T, H, tipo="pre")
        assert abs(r - esperado) < 1e-12

    def test_pre_prazo_longo_amplifica_perda(self):
        # Mesmo choque de taxa: prazo mais longo → perda maior (duration maior)
        r_curto = retorno_saida_antecipada(
            0.14, 0.15, anos_total=5.0, anos_saida=2.0, tipo="pre"
        )
        r_longo = retorno_saida_antecipada(
            0.14, 0.15, anos_total=15.0, anos_saida=2.0, tipo="pre"
        )
        assert r_longo < r_curto

    # ---- IPCA+ saída antecipada ----
    def test_ipca_formula_manual(self):
        tc, tv, T, H, ip = 0.07, 0.09, 10.0, 3.0, 0.05
        ratio = (1 + ip) ** H * (1 + tc) ** T / (1 + tv) ** (T - H)
        esperado = ratio ** (1 / H) - 1
        r = retorno_saida_antecipada(tc, tv, T, H, tipo="ipca_mais", ipca=ip)
        assert abs(r - esperado) < 1e-12

    def test_ipca_maior_inflacao_aumenta_retorno_nominal(self):
        r_baixo = retorno_saida_antecipada(
            0.07, 0.07, 10.0, 3.0, tipo="ipca_mais", ipca=0.03
        )
        r_alto = retorno_saida_antecipada(
            0.07, 0.07, 10.0, 3.0, tipo="ipca_mais", ipca=0.10
        )
        assert r_alto > r_baixo


# ---------------------------------------------------------------------------
# Retorno Hold-to-Mat com Reinvestimento
# ---------------------------------------------------------------------------


class TestRetornoHoldToMatReinvestido:
    def test_pre_sem_ir_formula_manual(self):
        tc, T, H, ip, sl = 0.14, 3.0, 5.0, 0.05, 0.135
        fator_T = (1 + tc) ** T
        fator_2 = (1 + sl) ** (H - T)
        esperado = (fator_T * fator_2) ** (1 / H) - 1
        r = retorno_hold_to_mat_reinvestido(
            tc, T, H, tipo="pre", ipca=ip, selic=sl, com_ir=False
        )
        assert abs(r - esperado) < 1e-12

    def test_ipca_sem_ir_formula_manual(self):
        tc, T, H, ip, sl = 0.07, 3.0, 5.0, 0.05, 0.135
        fator_T = ((1 + ip) * (1 + tc)) ** T
        fator_2 = (1 + sl) ** (H - T)
        esperado = (fator_T * fator_2) ** (1 / H) - 1
        r = retorno_hold_to_mat_reinvestido(
            tc, T, H, tipo="ipca_mais", ipca=ip, selic=sl, com_ir=False
        )
        assert abs(r - esperado) < 1e-12

    def test_com_ir_menor_que_sem_ir(self):
        r_bruto = retorno_hold_to_mat_reinvestido(
            0.14, 3.0, 5.0, "pre", 0.05, 0.135, com_ir=False
        )
        r_liq = retorno_hold_to_mat_reinvestido(
            0.14, 3.0, 5.0, "pre", 0.05, 0.135, com_ir=True
        )
        assert r_liq < r_bruto

    def test_selic_maior_aumenta_retorno(self):
        r_baixo = retorno_hold_to_mat_reinvestido(
            0.14, 3.0, 5.0, "pre", 0.05, selic=0.10, com_ir=False
        )
        r_alto = retorno_hold_to_mat_reinvestido(
            0.14, 3.0, 5.0, "pre", 0.05, selic=0.15, com_ir=False
        )
        assert r_alto > r_baixo

    def test_ipca_maior_aumenta_retorno(self):
        r_baixo = retorno_hold_to_mat_reinvestido(
            0.07, 3.0, 5.0, "ipca_mais", ipca=0.03, selic=0.135, com_ir=False
        )
        r_alto = retorno_hold_to_mat_reinvestido(
            0.07, 3.0, 5.0, "ipca_mais", ipca=0.08, selic=0.135, com_ir=False
        )
        assert r_alto > r_baixo

    def test_resultado_positivo_com_taxas_realistas(self):
        r = retorno_hold_to_mat_reinvestido(
            0.14, 3.0, 5.0, "pre", 0.05, 0.135, com_ir=True
        )
        assert r > 0.0


# ---------------------------------------------------------------------------
# Análise de Batalha
# ---------------------------------------------------------------------------


class TestAnaliseBatalha:
    def test_chaves_retornadas(self):
        res = analise_batalha("Tesouro Prefixado 2029", "pre", 14.0, 5.0, 3.0, 5.0)
        assert set(res) == {
            "nome",
            "tipo",
            "ret_adv",
            "ret_neu",
            "ret_fav",
            "ret_real",
            "risco_std",
            "risco_label",
            "anos_expo",
            "hold_to_mat",
            "reinvest",
        }

    def test_nome_e_tipo_preservados(self):
        res = analise_batalha("Teste", "pre", 14.0, 5.0, 3.0, 5.0)
        assert res["nome"] == "Teste"
        assert res["tipo"] == "pre"

    # ---- Pré: adverso = taxa sobe → perde ----
    def test_pre_adverso_menor_que_neutro(self):
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=10.0, anos_saida=3.0, ipca=5.0
        )
        assert res["ret_adv"] < res["ret_neu"]

    def test_pre_favoravel_maior_que_neutro(self):
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=10.0, anos_saida=3.0, ipca=5.0
        )
        assert res["ret_fav"] > res["ret_neu"]

    # ---- Selic: adverso = Selic cai → rende menos ----
    def test_selic_adverso_menor_que_favoravel(self):
        res = analise_batalha(
            "S", "selic", 14.75, anos_total=5.0, anos_saida=3.0, ipca=5.0
        )
        assert res["ret_adv"] < res["ret_fav"]

    def test_selic_risco_label_baixo(self):
        res = analise_batalha(
            "S", "selic", 14.75, anos_total=5.0, anos_saida=3.0, ipca=5.0
        )
        assert res["risco_label"] == "🟢 Baixo"

    # ---- Hold-to-mat: todos os cenários iguais (sem exposição MaM) ----
    def test_hold_to_mat_risco_zero(self):
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=5.0, anos_saida=5.0, ipca=5.0
        )
        assert abs(res["risco_std"]) < 1e-9
        assert res["hold_to_mat"] is True

    def test_hold_to_mat_alem_do_vencimento(self):
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=5.0, anos_saida=7.0, ipca=5.0
        )
        assert res["hold_to_mat"] is True

    # ---- anos_expo ----
    def test_anos_expo_saida_antes_do_vencimento(self):
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=10.0, anos_saida=3.0, ipca=5.0
        )
        assert abs(res["anos_expo"] - 7.0) < 1e-9

    def test_anos_expo_zero_quando_hold_to_mat(self):
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=5.0, anos_saida=6.0, ipca=5.0
        )
        assert res["anos_expo"] == 0.0

    # ---- risco_label por prazo de exposição ----
    def test_risco_label_moderado(self):
        # anos_expo = 1 (≤ 2) → Moderado
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=4.0, anos_saida=3.0, ipca=5.0
        )
        assert res["risco_label"] == "🟡 Moderado"

    def test_risco_label_medio_alto(self):
        # anos_expo = 3 (≤ 5, > 2) → Médio-Alto
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=6.0, anos_saida=3.0, ipca=5.0
        )
        assert res["risco_label"] == "🟠 Médio-Alto"

    def test_risco_label_alto(self):
        # anos_expo = 7 (> 5) → Alto
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=10.0, anos_saida=3.0, ipca=5.0
        )
        assert res["risco_label"] == "🔴 Alto"

    # ---- IR ----
    def test_com_ir_reduz_ret_neutro(self):
        r_bruto = analise_batalha("P", "pre", 14.0, 5.0, 3.0, 5.0, com_ir=False)
        r_liq = analise_batalha("P", "pre", 14.0, 5.0, 3.0, 5.0, com_ir=True)
        assert r_liq["ret_neu"] < r_bruto["ret_neu"]

    # ---- reinvest ----
    def test_reinvest_true_quando_saida_maior_e_selic_positiva(self):
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=3.0, anos_saida=5.0, ipca=5.0, selic=13.0
        )
        assert res["reinvest"] is True

    def test_reinvest_false_para_selic(self):
        res = analise_batalha(
            "S", "selic", 14.75, anos_total=3.0, anos_saida=5.0, ipca=5.0, selic=14.75
        )
        assert res["reinvest"] is False

    def test_reinvest_false_sem_selic(self):
        # selic=0 → reinvest False mesmo com saida > total
        res = analise_batalha(
            "P", "pre", 14.0, anos_total=3.0, anos_saida=5.0, ipca=5.0, selic=0.0
        )
        assert res["reinvest"] is False

    # ---- ret_real ----
    def test_ret_real_menor_que_nominal_com_ipca(self):
        res = analise_batalha("P", "ipca_mais", 7.0, 5.0, 3.0, ipca=5.0)
        assert res["ret_real"] < res["ret_neu"]

    def test_ret_real_igual_nominal_sem_ipca(self):
        res = analise_batalha("P", "pre", 14.0, 5.0, 3.0, ipca=0.0)
        assert abs(res["ret_real"] - res["ret_neu"]) < 1e-9

    def test_selic_com_ir_reduz_retorno(self):
        # cobre branch com_ir=True para tipo="selic" (linhas 567-569)
        r_bruto = analise_batalha("S", "selic", 14.75, 5.0, 3.0, ipca=5.0, com_ir=False)
        r_liq = analise_batalha("S", "selic", 14.75, 5.0, 3.0, ipca=5.0, com_ir=True)
        assert r_liq["ret_neu"] < r_bruto["ret_neu"]

    def test_anos_saida_zero_nao_explode(self):
        # retornos viram nan → risco_std = 0.0 via guard (linha 588)
        res = analise_batalha("S", "selic", 14.75, 5.0, 0.0, ipca=5.0)
        assert res["risco_std"] == 0.0

    def test_tipo_desconhecido_levanta_value_error(self):
        import pytest

        with pytest.raises(ValueError, match="tipo desconhecido"):
            analise_batalha("X", "cdb", 14.0, 5.0, 3.0, ipca=5.0)

    def test_ipca_mais_reinvest_com_ir_menor_que_sem_ir(self):
        # Documenta: ipca_mais + anos_saida > anos_total + selic > 0 → reinvest=True
        # Com IR, retorno deve ser menor que sem IR
        r_bruto = analise_batalha(
            "T",
            "ipca_mais",
            7.0,
            anos_total=3.0,
            anos_saida=5.0,
            ipca=5.0,
            selic=13.0,
            com_ir=False,
        )
        r_liq = analise_batalha(
            "T",
            "ipca_mais",
            7.0,
            anos_total=3.0,
            anos_saida=5.0,
            ipca=5.0,
            selic=13.0,
            com_ir=True,
        )
        assert r_bruto["reinvest"] is True
        assert r_liq["ret_neu"] < r_bruto["ret_neu"]


# ---------------------------------------------------------------------------
# Série Temporal do Paradoxo
# ---------------------------------------------------------------------------

_DC_SP = date.today() - timedelta(days=365)
_DV_SP = date(2035, 8, 15)
_VNA_SP = 4_200.0


def _serie(tem_cupom: bool = True):
    return serie_paradoxo(
        vna=_VNA_SP,
        taxa_real_contratada=0.075,
        taxa_real_mercado=0.080,
        data_compra=_DC_SP,
        data_vencimento=_DV_SP,
        quantidade=2.5,
        tem_cupom=tem_cupom,
    )


class TestSerieParadoxo:
    def test_retorna_dataframe(self):
        assert isinstance(_serie(), pd.DataFrame)

    def test_colunas_data_mam_carrego(self):
        assert {"data", "mam", "carrego"}.issubset(set(_serie().columns))

    def test_sem_cupom_retorna_dataframe(self):
        df = _serie(tem_cupom=False)
        assert isinstance(df, pd.DataFrame)
        assert {"data", "mam", "carrego"}.issubset(set(df.columns))

    def test_sem_cupom_carrego_monotonicamente_crescente(self):
        vals = _serie(tem_cupom=False)["carrego"].values
        assert all(vals[i] <= vals[i + 1] for i in range(len(vals) - 1))

    def test_seed_fixo_determinístico(self):
        df1 = _serie(tem_cupom=False)
        df2 = _serie(tem_cupom=False)
        assert df1["mam"].tolist() == df2["mam"].tolist()

    def test_taxa_mercado_acima_contratada_mam_menor_carrego(self):
        # taxa mercado (8%) > contratada (7.5%) → MaM < carrego ao longo do tempo
        df = _serie(tem_cupom=False)
        assert (df["mam"] < df["carrego"]).any()

    def test_amostragem_reduz_linhas(self):
        df_padrao = _serie(tem_cupom=False)
        df_denso = serie_paradoxo(
            vna=_VNA_SP,
            taxa_real_contratada=0.075,
            taxa_real_mercado=0.080,
            data_compra=_DC_SP,
            data_vencimento=_DV_SP,
            quantidade=2.5,
            tem_cupom=False,
            amostragem=1,
        )
        assert len(df_denso) > len(df_padrao)

    def test_cupom_dt_igual_vencimento_nao_explode(self):
        # Cobre linhas 328-330: quando dt >= data_vencimento no loop com cupons,
        # o guard retorna quantidade * vna em vez de chamar pu_ntnb com du=0.
        dc = date(2026, 5, 26)
        dv = date(2026, 5, 27)  # 1 dia útil depois → datas amostra inclui dv
        df = serie_paradoxo(
            vna=4_200.0,
            taxa_real_contratada=0.075,
            taxa_real_mercado=0.080,
            data_compra=dc,
            data_vencimento=dv,
            quantidade=1.0,
            tem_cupom=True,
            amostragem=1,
        )
        assert isinstance(df, pd.DataFrame)
        assert len(df) >= 1


# ---------------------------------------------------------------------------
# Métricas de Carteira (MaM + Carrego)
# ---------------------------------------------------------------------------

_HOJE_MC = date(2025, 6, 2)
_VENC_MC = date(2035, 5, 15)
_VNA_MC = 4_200.0
_TC_MC = 0.075  # taxa contratada
_TM_MC = 0.080  # taxa de mercado (acima da contratada → MaM < carrego)


def _metricas(tc=_TC_MC, tm=_TM_MC):
    cupons = datas_cupom_ntnb(_HOJE_MC, _VENC_MC)
    pu_c = pu_ntnb(_VNA_MC, tc, _HOJE_MC, _VENC_MC, cupons)
    return metricas_carteira(
        valor_investido=10_000.0,
        pu_na_compra=pu_c,
        taxa_real_contratada=tc,
        taxa_real_mercado=tm,
        vna=_VNA_MC,
        data_hoje=_HOJE_MC,
        data_vencimento=_VENC_MC,
        datas_cupom=cupons,
    )


class TestMetricasCarteira:
    def test_chaves_retornadas(self):
        res = _metricas()
        assert set(res) == {
            "mam",
            "vencimento",
            "variacao_dia",
            "pu_hoje",
            "pu_carrego",
            "quantidade",
        }

    def test_quantidade_correta(self):
        cupons = datas_cupom_ntnb(_HOJE_MC, _VENC_MC)
        pu_c = pu_ntnb(_VNA_MC, _TC_MC, _HOJE_MC, _VENC_MC, cupons)
        res = _metricas()
        assert abs(res["quantidade"] - 10_000.0 / pu_c) < 1e-9

    def test_mam_igual_quantidade_vezes_pu_hoje(self):
        res = _metricas()
        assert abs(res["mam"] - res["quantidade"] * res["pu_hoje"]) < 1e-6

    def test_vencimento_igual_quantidade_vezes_pu_carrego(self):
        res = _metricas()
        assert abs(res["vencimento"] - res["quantidade"] * res["pu_carrego"]) < 1e-6

    def test_taxa_mercado_acima_mam_menor_carrego(self):
        # tm > tc → mercado penaliza → MaM < carrego
        res = _metricas(tc=0.075, tm=0.090)
        assert res["mam"] < res["vencimento"]

    def test_taxa_mercado_abaixo_mam_maior_carrego(self):
        # tm < tc → mercado premia → MaM > carrego
        res = _metricas(tc=0.075, tm=0.060)
        assert res["mam"] > res["vencimento"]

    def test_taxa_mercado_igual_mam_igual_carrego(self):
        # tm == tc → pu_hoje == pu_carrego → mam == vencimento
        res = _metricas(tc=0.075, tm=0.075)
        assert abs(res["mam"] - res["vencimento"]) < 1e-6

    def test_pu_positivos(self):
        res = _metricas()
        assert res["pu_hoje"] > 0
        assert res["pu_carrego"] > 0

    def test_variacao_dia_float(self):
        res = _metricas()
        assert isinstance(res["variacao_dia"], float)


# ---------------------------------------------------------------------------
# Valor Futuro com Aportes Mensais (fv_mensal)
# ---------------------------------------------------------------------------


class TestFvMensal:
    def test_zero_meses_retorna_capital(self):
        res = fv_mensal(taxa_a=0.12, n_meses=0, cap=10_000.0, pmt=500.0, aliq=0.15)
        assert res == {
            "fv_liq": 10_000.0,
            "fv_bruto": 10_000.0,
            "total_inv": 10_000.0,
            "ir": 0.0,
        }

    def test_chaves_retornadas(self):
        res = fv_mensal(0.10, 12, 1_000.0, 100.0, 0.15)
        assert set(res) == {"fv_liq", "fv_bruto", "total_inv", "ir"}

    def test_total_investido_correto(self):
        res = fv_mensal(0.10, 24, 5_000.0, 200.0, 0.15)
        assert abs(res["total_inv"] - (5_000.0 + 200.0 * 24)) < 1e-6

    def test_fv_liquido_igual_bruto_menos_ir(self):
        res = fv_mensal(0.12, 12, 1_000.0, 100.0, 0.15)
        assert abs(res["fv_liq"] - (res["fv_bruto"] - res["ir"])) < 1e-9

    def test_sem_taxa_sem_ganho_sem_ir(self):
        # Com taxa zero, fv_bruto == total_inv → ganho == 0 → ir == 0
        res = fv_mensal(taxa_a=0.0, n_meses=12, cap=1_000.0, pmt=100.0, aliq=0.15)
        assert abs(res["fv_bruto"] - res["total_inv"]) < 1e-6
        assert res["ir"] == 0.0

    def test_taxa_positiva_gera_ganho(self):
        res = fv_mensal(0.12, 12, 1_000.0, 100.0, 0.15)
        assert res["fv_bruto"] > res["total_inv"]

    def test_taxa_maior_fv_maior(self):
        r_baixo = fv_mensal(0.08, 24, 1_000.0, 200.0, 0.15)
        r_alto = fv_mensal(0.14, 24, 1_000.0, 200.0, 0.15)
        assert r_alto["fv_bruto"] > r_baixo["fv_bruto"]

    def test_ir_proporcional_aliquota(self):
        r_baixo = fv_mensal(0.12, 12, 1_000.0, 100.0, aliq=0.15)
        r_alto = fv_mensal(0.12, 12, 1_000.0, 100.0, aliq=0.225)
        # fv_bruto é o mesmo; IR maior com alíquota maior
        assert abs(r_baixo["fv_bruto"] - r_alto["fv_bruto"]) < 1e-6
        assert r_alto["ir"] > r_baixo["ir"]

    def test_sem_aporte_formula_juros_compostos(self):
        # pmt=0: fv_bruto = cap * (1+r_m)^n
        taxa_a = 0.12
        n = 12
        cap = 5_000.0
        r_m = (1 + taxa_a) ** (1 / 12) - 1
        esperado = cap * (1 + r_m) ** n
        res = fv_mensal(taxa_a, n, cap, pmt=0.0, aliq=0.15)
        assert abs(res["fv_bruto"] - esperado) < 1e-6


# ---------------------------------------------------------------------------
# Aporte Mensal para Meta (pmt_para_meta)
# ---------------------------------------------------------------------------


class TestPmtParaMeta:
    def test_zero_meses_retorna_diferenca(self):
        assert abs(pmt_para_meta(0.10, 0, 5_000.0, 8_000.0, 0.15) - 3_000.0) < 1e-6

    def test_meses_negativos_retorna_diferenca(self):
        assert abs(pmt_para_meta(0.10, -1, 5_000.0, 8_000.0, 0.15) - 3_000.0) < 1e-6

    def test_capital_supera_meta_retorna_zero(self):
        assert pmt_para_meta(0.10, 24, 10_000.0, 8_000.0, 0.15) == 0.0

    def test_resultado_nao_negativo(self):
        pmt = pmt_para_meta(0.12, 12, 0.0, 5_000.0, 0.15)
        assert pmt >= 0.0

    def test_taxa_maior_pmt_menor(self):
        # Maior rendimento → precisa aportar menos para atingir a mesma meta
        pmt_baixo = pmt_para_meta(0.08, 24, 1_000.0, 10_000.0, 0.15)
        pmt_alto = pmt_para_meta(0.14, 24, 1_000.0, 10_000.0, 0.15)
        assert pmt_alto < pmt_baixo

    def test_roundtrip_fv_mensal(self):
        # pmt calculado deve produzir exatamente a meta em fv_mensal
        taxa_a = 0.10
        n = 24
        cap = 2_000.0
        meta = 8_000.0
        aliq = 0.15
        pmt = pmt_para_meta(taxa_a, n, cap, meta, aliq)
        res = fv_mensal(taxa_a, n, cap, pmt, aliq)
        assert abs(res["fv_liq"] - meta) < 0.01  # tolerância de 1 centavo

    def test_sem_taxa_formula_linear(self):
        # taxa_a=0, aliq=0 → pmt = (meta - cap) / n
        n = 12
        cap = 1_000.0
        meta = 4_000.0
        pmt = pmt_para_meta(0.0, n, cap, meta, aliq=0.0)
        assert abs(pmt - (meta - cap) / n) < 1e-6
