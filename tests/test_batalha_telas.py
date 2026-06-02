"""Tests for telas/batalha.py: pure utility functions (without Streamlit runtime)."""

from telas.batalha import (
    _analise_cached,
    _insight_texto,
    _risco_expo,
    _winner,
    _winner_por_perfil,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk(
    nome="A",
    tipo="ipca_mais",
    ret_adv=4.0,
    ret_neu=10.0,
    ret_fav=16.0,
    risco_std=2.0,
    anos_expo=3.0,
    ret_real=5.0,
    reinvest=False,
):
    return {
        "nome": nome,
        "tipo": tipo,
        "ret_adv": ret_adv,
        "ret_neu": ret_neu,
        "ret_fav": ret_fav,
        "risco_std": risco_std,
        "anos_expo": anos_expo,
        "ret_real": ret_real,
        "reinvest": reinvest,
    }


# ---------------------------------------------------------------------------
# _risco_expo
# ---------------------------------------------------------------------------


class TestRiscoExpo:
    def test_selic_sempre_nenhuma(self):
        assert "Nenhuma" in _risco_expo("selic", 10)

    def test_anos_zero_sempre_nenhuma(self):
        assert "Nenhuma" in _risco_expo("ipca_mais", 0)

    def test_ate_2_anos_baixa(self):
        assert "Baixa" in _risco_expo("ipca_mais", 1)
        assert "Baixa" in _risco_expo("pre", 2)

    def test_3_a_5_anos_media(self):
        assert "Média" in _risco_expo("ipca_mais", 3)
        assert "Média" in _risco_expo("pre", 5)

    def test_acima_5_anos_alta(self):
        assert "Alta" in _risco_expo("ipca_mais", 6)
        assert "Alta" in _risco_expo("pre", 15)


# ---------------------------------------------------------------------------
# _winner
# ---------------------------------------------------------------------------


class TestWinner:
    def test_escolhe_maior_retorno_por_risco(self):
        a = _mk("A", ret_neu=10.0, risco_std=2.0)  # ratio = 5
        b = _mk("B", ret_neu=12.0, risco_std=1.0)  # ratio = 12 → vencedor
        assert _winner([a, b])["nome"] == "B"

    def test_risco_zero_usa_piso_0_01(self):
        # risco_std=0 não deve explodir (usa max(risco, 0.01))
        a = _mk("A", ret_neu=10.0, risco_std=0.0)
        b = _mk("B", ret_neu=5.0, risco_std=0.0)
        winner = _winner([a, b])
        assert winner["nome"] == "A"

    def test_lista_de_um_retorna_esse(self):
        a = _mk("Único")
        assert _winner([a])["nome"] == "Único"


# ---------------------------------------------------------------------------
# _winner_por_perfil
# ---------------------------------------------------------------------------


class TestWinnerPorPerfil:
    def _analises(self):
        # Conservador_win: menor risco_std (0.5), Sharpe 6/0.5=12
        # Moderado_win:    maior Sharpe 15/1.0=15, ret_fav médio
        # Arrojado_win:    maior ret_fav (25), Sharpe 10/5=2
        return [
            _mk("Conservador_win", risco_std=0.5, ret_neu=6.0, ret_fav=8.0),
            _mk("Moderado_win", risco_std=1.0, ret_neu=15.0, ret_fav=17.0),
            _mk("Arrojado_win", risco_std=5.0, ret_neu=10.0, ret_fav=25.0),
        ]

    def test_conservador_minimiza_risco(self):
        w = _winner_por_perfil(self._analises(), "Conservador")
        assert w["nome"] == "Conservador_win"

    def test_arrojado_maximiza_ret_fav(self):
        w = _winner_por_perfil(self._analises(), "Arrojado")
        assert w["nome"] == "Arrojado_win"

    def test_moderado_usa_sharpe(self):
        # Moderado_win: 15/1.0=15 — maior ratio entre os três
        w = _winner_por_perfil(self._analises(), "Moderado")
        assert w["nome"] == "Moderado_win"


# ---------------------------------------------------------------------------
# _insight_texto — 7 ramos distintos
# ---------------------------------------------------------------------------


class TestInsightTexto:
    def test_selic(self):
        w = _mk("Tesouro Selic 2031", tipo="selic", ret_neu=13.0)
        txt = _insight_texto(w, horizonte=2, ipca=5.0, com_ir=False)
        assert "pós-fixado" in txt.lower()
        assert "13.0" in txt

    def test_pre_reinvest(self):
        w = _mk(
            "Tesouro Prefixado 2029",
            tipo="pre",
            reinvest=True,
            ret_neu=12.0,
            ret_adv=10.0,
        )
        txt = _insight_texto(w, horizonte=5, ipca=5.0, com_ir=False)
        assert "Prefixado" in txt
        assert "Selic" in txt

    def test_pre_expo_zero(self):
        w = _mk(
            "Tesouro Prefixado 2029",
            tipo="pre",
            reinvest=False,
            anos_expo=0,
            ret_neu=14.0,
            ret_real=6.0,
        )
        txt = _insight_texto(w, horizonte=3, ipca=5.0, com_ir=False)
        assert "14.0" in txt
        assert "MaM" in txt

    def test_pre_expo_positivo(self):
        w = _mk(
            "Tesouro Prefixado 2032",
            tipo="pre",
            reinvest=False,
            anos_expo=3.0,
            ret_neu=13.0,
            ret_adv=9.0,
        )
        txt = _insight_texto(w, horizonte=2, ipca=5.0, com_ir=False)
        assert "3.0 anos antes" in txt
        assert "adverso" in txt.lower()

    def test_ipca_mais_reinvest(self):
        w = _mk(
            "Tesouro IPCA+ 2032",
            tipo="ipca_mais",
            reinvest=True,
            ret_neu=11.0,
            ret_real=6.0,
            ret_adv=8.0,
        )
        txt = _insight_texto(w, horizonte=5, ipca=5.0, com_ir=False)
        assert "IPCA+" in txt
        assert "Selic" in txt

    def test_ipca_mais_expo_zero(self):
        w = _mk(
            "Tesouro IPCA+ 2040",
            tipo="ipca_mais",
            reinvest=False,
            anos_expo=0,
            ret_neu=10.0,
            ret_real=7.0,
        )
        txt = _insight_texto(w, horizonte=14, ipca=5.0, com_ir=False)
        assert "real" in txt.lower()
        assert "7.0" in txt

    def test_ipca_mais_expo_positivo(self):
        w = _mk(
            "Tesouro IPCA+ 2050",
            tipo="ipca_mais",
            reinvest=False,
            anos_expo=10.0,
            ret_neu=10.0,
            ret_real=6.5,
            ret_adv=4.0,
        )
        txt = _insight_texto(w, horizonte=5, ipca=5.0, com_ir=False)
        assert "10.0" in txt
        assert "adverso" in txt.lower()

    def test_com_ir_inclui_liquido(self):
        w = _mk("Tesouro Selic 2031", tipo="selic", ret_neu=13.0)
        txt = _insight_texto(w, horizonte=2, ipca=5.0, com_ir=True)
        assert "líquido de IR" in txt

    def test_sem_ir_nao_menciona_ir(self):
        w = _mk("Tesouro Selic 2031", tipo="selic", ret_neu=13.0)
        txt = _insight_texto(w, horizonte=2, ipca=5.0, com_ir=False)
        assert "IR" not in txt


# ---------------------------------------------------------------------------
# _analise_cached
# ---------------------------------------------------------------------------


class TestAnaliseCached:
    def test_delega_para_analise_batalha(self):
        result = _analise_cached(
            nome="T",
            tipo="pre",
            taxa=14.0,
            anos_total=5.0,
            anos_saida=5.0,
            ipca=5.0,
            choque=1.0,
            com_ir=True,
            selic=13.0,
        )
        assert "ret_neu" in result
        assert "nome" in result
        assert result["nome"] == "T"

    def test_retorno_ipca_mais(self):
        result = _analise_cached(
            nome="X",
            tipo="ipca_mais",
            taxa=7.0,
            anos_total=10.0,
            anos_saida=10.0,
            ipca=5.0,
            choque=1.0,
            com_ir=False,
            selic=13.0,
        )
        assert result["ret_neu"] > 0
