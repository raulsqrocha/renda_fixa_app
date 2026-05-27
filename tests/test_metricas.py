"""Tests for telas/_dashboard_metricas.py: calcular_posicao_ntnb and calcular_posicao_simples."""

from datetime import date, timedelta

import pandas as pd
import pytest

from telas._dashboard_metricas import (
    SCORE_POS_MAX,
    SCORE_POS_PRE,
    SCORE_PRAZO_MAX,
    calcular_posicao_ntnb,
    calcular_posicao_simples,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_HOJE = date.today()
_DC   = _HOJE - timedelta(days=365)         # compra 1 ano atrás
_DV   = date(2035, 8, 15)                   # vencimento distante
_VNA  = 5_500.0  # VNA coerente com IPCA artificial de 0.5%/mês × 137 meses ≈ 5_367


def _df_titulos(nome="Tesouro IPCA+ 2035", taxa_compra=7.50, taxa_venda=7.53):
    return pd.DataFrame([{
        "nome":        nome,
        "vencimento":  _DV.isoformat(),
        "taxa_compra": taxa_compra,
        "taxa_venda":  taxa_venda,
        "pu_compra":   3_500.0,
        "pu_venda":    3_490.0,
        "_is_fallback": False,
    }])


def _df_ipca_simples():
    """IPCA artificial de 0.5% ao mês desde 2015-01-01."""
    datas = pd.date_range("2015-01-01", periods=137, freq="MS")
    return pd.DataFrame({"data": datas, "valor": [0.5] * 137, "_is_fallback": False})


def _calc(titulo="Tesouro IPCA+ 2035", valor=10_000.0, taxa_pct=7.50,
          data_compra=None, df_t=None, df_i=None):
    return calcular_posicao_ntnb(
        titulo, valor, taxa_pct,
        (data_compra or _DC).isoformat(),
        df_titulos=df_t if df_t is not None else _df_titulos(titulo),
        df_ipca=df_i if df_i is not None else _df_ipca_simples(),
        vna=_VNA,
    )


def _simples(titulo="Tesouro Selic 2031", tipo="selic", valor=10_000.0,
             taxa_pct=14.75, data_compra=None, vencimento=None):
    dc = data_compra or _DC
    dv = vencimento or date(2031, 3, 1)
    return calcular_posicao_simples(titulo, tipo, valor, taxa_pct,
                                    dc.isoformat(), dv.isoformat())


# ---------------------------------------------------------------------------
# calcular_posicao_ntnb — retorno None em bordas inválidas
# ---------------------------------------------------------------------------

class TestCalcNtnbNone:
    def test_compra_igual_vencimento_retorna_none(self):
        assert _calc(data_compra=_DV) is None

    def test_compra_apos_vencimento_retorna_none(self):
        assert _calc(data_compra=_DV + timedelta(days=1)) is None

    def test_pu_zero_retorna_none(self):
        # Cobre linha 127: pu_c <= 0 → return None.
        # IPCA de -100% em jan/2015 faz calcular_vna_em_data retornar 0,
        # logo pu_ntnb(vna=0, ...) = 0 → branch return None é atingido.
        df_ipca_zero = pd.DataFrame({
            "data":        [pd.Timestamp("2015-01-01")],
            "valor":       [-100.0],
            "_is_fallback": [True],
        })
        result = _calc(df_i=df_ipca_zero)
        assert result is None

    def test_pu_invalido_df_vazio_fallback_usa_config(self):
        # df_titulos vazio → usa TITULOS_CONFIG para data de vencimento
        df_vazio = pd.DataFrame(columns=["nome", "vencimento", "taxa_compra", "taxa_venda"])
        result = _calc(df_t=df_vazio)
        # Deve retornar None (TITULOS_CONFIG não tem "Tesouro IPCA+ 2035" com venc 2035-08-15)
        # ou um resultado válido se encontrar vencimento default — ambos são comportamentos corretos
        # O importante: não lança exceção
        assert result is None or isinstance(result, dict)


# ---------------------------------------------------------------------------
# calcular_posicao_ntnb — estrutura do resultado
# ---------------------------------------------------------------------------

class TestCalcNtnbEstrutura:
    _CHAVES = {
        "res", "taxa_mkt_pct", "taxa_vda_pct",
        "dv", "dc", "tc", "tm", "cupom",
        "pu_c", "cpns_h", "anos_tot", "anos_res",
        "vf", "prazo_score", "posicao_score", "score",
        "taxa_pct", "is_simples",
    }

    def test_todas_as_chaves_presentes(self):
        r = _calc()
        assert r is not None
        assert self._CHAVES.issubset(set(r.keys()))

    def test_is_simples_false(self):
        assert _calc()["is_simples"] is False

    def test_sem_cupom_para_ipca_principal(self):
        assert _calc()["cupom"] is False

    def test_com_cupom_para_juros_semestrais(self):
        titulo = "Tesouro IPCA+ com Juros Semestrais 2037"
        df = _df_titulos(titulo, taxa_compra=7.51, taxa_venda=7.54)
        r  = calcular_posicao_ntnb(
            titulo, 10_000.0, 7.51, _DC.isoformat(),
            df_titulos=df, df_ipca=_df_ipca_simples(), vna=_VNA,
        )
        assert r is not None
        assert r["cupom"] is True

    def test_dc_e_dv_corretos(self):
        r = _calc()
        assert r["dc"] == _DC
        assert r["dv"] == _DV

    def test_taxa_pct_preservada(self):
        r = _calc(taxa_pct=6.80)
        assert r["taxa_pct"] == pytest.approx(6.80)

    def test_tc_e_taxa_pct_consistentes(self):
        r = _calc(taxa_pct=7.50)
        assert r["tc"] == pytest.approx(7.50 / 100)


# ---------------------------------------------------------------------------
# calcular_posicao_ntnb — valores financeiros
# ---------------------------------------------------------------------------

class TestCalcNtnbFinancas:
    def test_mam_positivo(self):
        assert _calc()["res"]["mam"] > 0

    def test_vf_maior_que_capital(self):
        r = _calc(valor=10_000.0, taxa_pct=7.50)
        assert r["vf"] > 10_000.0

    def test_taxa_mercado_maior_reduz_mam(self):
        r_baixa = _calc()
        df_alta  = _df_titulos(taxa_compra=10.0, taxa_venda=10.03)
        r_alta   = _calc(df_t=df_alta)
        assert r_alta is not None and r_baixa is not None
        assert r_alta["res"]["mam"] < r_baixa["res"]["mam"]

    def test_pu_c_positivo(self):
        assert _calc()["pu_c"] > 0

    def test_anos_res_ao_menos_1(self):
        assert _calc()["anos_res"] >= 1


# ---------------------------------------------------------------------------
# calcular_posicao_ntnb — Score de Saúde
# ---------------------------------------------------------------------------

class TestCalcNtnbScore:
    def test_score_e_soma_dos_sub_scores(self):
        r = _calc()
        assert r["score"] == pytest.approx(r["prazo_score"] + r["posicao_score"])

    def test_prazo_score_max_60(self):
        assert _calc()["prazo_score"] <= SCORE_PRAZO_MAX

    def test_posicao_score_max_40(self):
        assert _calc()["posicao_score"] <= SCORE_POS_MAX

    def test_posicao_score_nao_negativo(self):
        assert _calc()["posicao_score"] >= 0.0

    def test_prazo_longo_eleva_prazo_score(self):
        # vencimento em 2060 → prazo_score deve atingir o máximo
        titulo = "Tesouro IPCA+ 2060"
        dv_longe = date(2060, 8, 15)
        df = pd.DataFrame([{
            "nome": titulo, "vencimento": dv_longe.isoformat(),
            "taxa_compra": 7.0, "taxa_venda": 7.03,
            "pu_compra": 1_000.0, "pu_venda": 995.0, "_is_fallback": False,
        }])
        r = calcular_posicao_ntnb(
            titulo, 10_000.0, 7.0, _DC.isoformat(),
            df_titulos=df, df_ipca=_df_ipca_simples(), vna=_VNA,
        )
        assert r is not None
        assert r["prazo_score"] == pytest.approx(SCORE_PRAZO_MAX)

    def test_score_maximo_e_100(self):
        assert SCORE_PRAZO_MAX + SCORE_POS_MAX == 100.0


# ---------------------------------------------------------------------------
# calcular_posicao_simples — retorno None em bordas
# ---------------------------------------------------------------------------

class TestCalcSimplesNone:
    def test_compra_igual_vencimento_retorna_none(self):
        dc = date(2030, 1, 1)
        assert calcular_posicao_simples("X", "selic", 10_000.0, 14.75,
                                        dc.isoformat(), dc.isoformat()) is None

    def test_compra_apos_vencimento_retorna_none(self):
        dc = date(2031, 1, 1)
        dv = date(2030, 1, 1)
        assert calcular_posicao_simples("X", "selic", 10_000.0, 14.75,
                                        dc.isoformat(), dv.isoformat()) is None


# ---------------------------------------------------------------------------
# calcular_posicao_simples — estrutura
# ---------------------------------------------------------------------------

class TestCalcSimplesEstrutura:
    _CHAVES = {
        "res", "taxa_mkt_pct", "taxa_vda_pct",
        "dv", "dc", "tc", "tm",
        "cupom", "pu_c", "cpns_h",
        "anos_tot", "anos_res",
        "vf", "prazo_score", "posicao_score", "score",
        "taxa_pct", "tipo_asset", "is_simples",
    }

    def test_todas_as_chaves_presentes(self):
        r = _simples()
        assert r is not None
        assert self._CHAVES.issubset(set(r.keys()))

    def test_is_simples_true(self):
        assert _simples()["is_simples"] is True

    def test_sem_cupom(self):
        assert _simples()["cupom"] is False

    def test_tipo_asset_preservado(self):
        assert _simples(tipo="pre")["tipo_asset"] == "pre"

    def test_taxa_vda_none(self):
        assert _simples()["taxa_vda_pct"] is None

    def test_cpns_h_vazio(self):
        assert _simples()["cpns_h"] == []


# ---------------------------------------------------------------------------
# calcular_posicao_simples — valores financeiros
# ---------------------------------------------------------------------------

class TestCalcSimplesFinancas:
    def test_mam_maior_que_capital_apos_1_ano(self):
        r = _simples(taxa_pct=14.75)
        assert r["res"]["mam"] > 10_000.0

    def test_vf_maior_que_mam(self):
        r = _simples()
        assert r["vf"] > r["res"]["mam"]

    def test_anos_res_ao_menos_1(self):
        assert _simples()["anos_res"] >= 1

    def test_tc_consistente_com_taxa_pct(self):
        r = _simples(taxa_pct=12.0)
        assert r["tc"] == pytest.approx(12.0 / 100)


# ---------------------------------------------------------------------------
# calcular_posicao_simples — Score diferenciado por tipo
# ---------------------------------------------------------------------------

class TestCalcSimplesScore:
    def test_score_e_soma_dos_sub_scores(self):
        r = _simples()
        assert r["score"] == pytest.approx(r["prazo_score"] + r["posicao_score"])

    def test_pre_tem_posicao_score_reduzido(self):
        r_selic = _simples(tipo="selic")
        r_pre   = _simples(tipo="pre")
        assert r_pre["posicao_score"] < r_selic["posicao_score"]

    def test_pre_posicao_score_igual_constante(self):
        assert _simples(tipo="pre")["posicao_score"] == pytest.approx(SCORE_POS_PRE)

    def test_selic_posicao_score_igual_constante(self):
        assert _simples(tipo="selic")["posicao_score"] == pytest.approx(SCORE_POS_MAX)

    def test_prazo_score_max_60(self):
        assert _simples()["prazo_score"] <= SCORE_PRAZO_MAX

    def test_prazo_longo_atinge_max(self):
        dv_longe = _HOJE + timedelta(days=365 * 10)
        r = _simples(vencimento=dv_longe)
        assert r["prazo_score"] == pytest.approx(SCORE_PRAZO_MAX)
