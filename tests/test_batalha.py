"""Testes unitários para core/batalha.py: gerar_portfolios_aleatorios e carteira_mista."""

from core.batalha import carteira_mista, gerar_portfolios_aleatorios


def _analise(nome="A", ret_adv=5.0, ret_neu=10.0, ret_fav=15.0):
    return {
        "nome": nome,
        "tipo": "pre",
        "ret_adv": ret_adv,
        "ret_neu": ret_neu,
        "ret_fav": ret_fav,
    }


# ---------------------------------------------------------------------------
# gerar_portfolios_aleatorios
# ---------------------------------------------------------------------------


class TestGerarPortfoliosAleatorios:
    def test_retorna_vazio_com_menos_de_2_ativos(self):
        assert gerar_portfolios_aleatorios([_analise()]) == []
        assert gerar_portfolios_aleatorios([]) == []

    def test_retorna_n_portfolios(self):
        analises = [_analise("A"), _analise("B")]
        result = gerar_portfolios_aleatorios(analises, n=50)
        assert len(result) == 50

    def test_chaves_retornadas(self):
        analises = [_analise("A"), _analise("B")]
        p = gerar_portfolios_aleatorios(analises, n=1)[0]
        assert set(p) == {"ret_adv", "ret_neu", "ret_fav", "risco_std"}

    def test_seed_determinístico(self):
        analises = [_analise("A"), _analise("B"), _analise("C")]
        r1 = gerar_portfolios_aleatorios(analises, n=20, seed=7)
        r2 = gerar_portfolios_aleatorios(analises, n=20, seed=7)
        assert r1 == r2

    def test_seed_diferente_resultado_diferente(self):
        analises = [_analise("A"), _analise("B")]
        r1 = gerar_portfolios_aleatorios(analises, n=10, seed=1)
        r2 = gerar_portfolios_aleatorios(analises, n=10, seed=99)
        assert r1 != r2

    def test_risco_std_nao_negativo(self):
        analises = [_analise("A"), _analise("B")]
        for p in gerar_portfolios_aleatorios(analises, n=20):
            assert p["risco_std"] >= 0.0


# ---------------------------------------------------------------------------
# carteira_mista
# ---------------------------------------------------------------------------


class TestCarteiraMista:
    def _mix(self, peso=0.70):
        principal = _analise("IPCA+", ret_adv=4.0, ret_neu=10.0, ret_fav=16.0)
        liquida = _analise("Selic", ret_adv=12.0, ret_neu=13.0, ret_fav=14.0)
        return carteira_mista(principal, liquida, peso_principal=peso)

    def test_chaves_retornadas(self):
        res = self._mix()
        assert set(res) == {
            "ret_adv",
            "ret_neu",
            "ret_fav",
            "risco_std",
            "peso_principal",
            "peso_liquida",
            "nome_principal",
            "nome_liquida",
            "tipo_principal",
        }

    def test_pesos_somam_um(self):
        res = self._mix(0.70)
        assert abs(res["peso_principal"] + res["peso_liquida"] - 1.0) < 1e-9

    def test_retorno_neutro_eh_media_ponderada(self):
        principal = _analise("A", ret_neu=10.0)
        liquida = _analise("B", ret_neu=14.0)
        res = carteira_mista(principal, liquida, peso_principal=0.60)
        esperado = 0.60 * 10.0 + 0.40 * 14.0
        assert abs(res["ret_neu"] - esperado) < 1e-9

    def test_nomes_preservados(self):
        principal = _analise("IPCA+ 2035")
        liquida = _analise("Selic 2031")
        res = carteira_mista(principal, liquida)
        assert res["nome_principal"] == "IPCA+ 2035"
        assert res["nome_liquida"] == "Selic 2031"

    def test_tipo_principal_preservado(self):
        principal = {
            "nome": "P",
            "tipo": "ipca_mais",
            "ret_adv": 5.0,
            "ret_neu": 9.0,
            "ret_fav": 13.0,
        }
        liquida = _analise("L")
        res = carteira_mista(principal, liquida)
        assert res["tipo_principal"] == "ipca_mais"

    def test_risco_zero_quando_cenarios_iguais(self):
        # Se adv == neu == fav para ambos, risco = 0
        principal = _analise("A", ret_adv=10.0, ret_neu=10.0, ret_fav=10.0)
        liquida = _analise("B", ret_adv=10.0, ret_neu=10.0, ret_fav=10.0)
        res = carteira_mista(principal, liquida)
        assert abs(res["risco_std"]) < 1e-9
