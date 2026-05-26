"""Tests for telas/simulador.py: pure utility functions (without Streamlit runtime)."""

from telas.simulador import _cor_retorno


# ---------------------------------------------------------------------------
# _cor_retorno
# ---------------------------------------------------------------------------

class TestCorRetorno:
    def test_negativo_retorna_vermelho(self):
        css = _cor_retorno("-5.3%")
        assert "#2d1515" in css   # fundo vermelho escuro
        assert "#fc8181" in css   # texto vermelho claro

    def test_zero_retorna_amarelo(self):
        # 0 < 30 → amarelo
        css = _cor_retorno("0%")
        assert "#2d2a10" in css

    def test_pequeno_positivo_retorna_amarelo(self):
        # 15 < 30 → amarelo
        css = _cor_retorno("15%")
        assert "#2d2a10" in css

    def test_medio_positivo_retorna_verde(self):
        # 50 < 100 → verde
        css = _cor_retorno("50%")
        assert "#15291a" in css
        assert "#68d391" in css

    def test_grande_positivo_retorna_azul(self):
        # 150 >= 100 → azul
        css = _cor_retorno("150%")
        assert "#0e1f3a" in css
        assert "#90cdf4" in css

    def test_string_com_sinal_mais_parseada(self):
        # O '+' é removido antes do parse
        css = _cor_retorno("+25.5%")
        assert "#2d2a10" in css   # 25.5 < 30 → amarelo

    def test_string_invalida_retorna_vazio(self):
        # Valor não-numérico → except → ""
        assert _cor_retorno("N/A") == ""

    def test_virgula_como_separador_decimal(self):
        # A função substitui ',' → '.' antes de converter → "50,5%" vira 50.5 → verde
        css = _cor_retorno("50,5%")
        assert "#15291a" in css   # 50.5 < 100 → verde
