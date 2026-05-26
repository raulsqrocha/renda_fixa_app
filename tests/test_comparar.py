"""Tests for telas/comparar.py: pure utility functions (without Streamlit runtime)."""

import math

from telas.comparar import _taxa_equivalente_isento, _taxa_bruta_necessaria


# ---------------------------------------------------------------------------
# _taxa_equivalente_isento
# ---------------------------------------------------------------------------

class TestTaxaEquivalenteIsento:
    def test_formula_basica(self):
        # CDB 14% com alíq 15% → líquido = 14 * (1 - 0.15) = 11.9%
        assert abs(_taxa_equivalente_isento(0.14, 0.15) - 0.119) < 1e-9

    def test_aliquota_zero_retorna_taxa_bruta(self):
        # Sem IR, líquido == bruto
        assert abs(_taxa_equivalente_isento(0.14, 0.0) - 0.14) < 1e-9

    def test_aliquota_maxima_retorna_zero(self):
        # 100% de IR → zero líquido
        assert _taxa_equivalente_isento(0.14, 1.0) == 0.0

    def test_proporcional_a_taxa_bruta(self):
        # Dobrando a taxa bruta, o líquido dobra
        r1 = _taxa_equivalente_isento(0.10, 0.15)
        r2 = _taxa_equivalente_isento(0.20, 0.15)
        assert abs(r2 / r1 - 2.0) < 1e-9

    def test_aliquotas_regressivas_tabela_ir(self):
        # Tabela IR: 22.5% (≤180 dias) > 15% (>720 dias) → mais IR → menor líquido
        liq_22 = _taxa_equivalente_isento(0.14, 0.225)
        liq_15 = _taxa_equivalente_isento(0.14, 0.150)
        assert liq_22 < liq_15


# ---------------------------------------------------------------------------
# _taxa_bruta_necessaria
# ---------------------------------------------------------------------------

class TestTaxaBrutaNecessaria:
    def test_inversa_da_equivalente_isento(self):
        # _taxa_bruta_necessaria deve ser inversa de _taxa_equivalente_isento
        taxa_isenta = 0.119
        aliq = 0.15
        bruta = _taxa_bruta_necessaria(taxa_isenta, aliq)
        # Aplicando de volta: isenta = bruta * (1 - aliq) ≈ 0.119
        assert abs(_taxa_equivalente_isento(bruta, aliq) - taxa_isenta) < 1e-9

    def test_aliquota_zero_retorna_mesma_taxa(self):
        # Sem IR, taxa bruta necessária == taxa isenta
        assert abs(_taxa_bruta_necessaria(0.119, 0.0) - 0.119) < 1e-9

    def test_aliquota_100pct_retorna_inf(self):
        # Impossível empatar com isento se 100% vai para IR
        assert _taxa_bruta_necessaria(0.119, 1.0) == math.inf

    def test_aliquota_maior_exige_taxa_bruta_maior(self):
        # Mais IR → precisa de taxa bruta maior para empatar
        bruta_15 = _taxa_bruta_necessaria(0.10, 0.15)
        bruta_22 = _taxa_bruta_necessaria(0.10, 0.225)
        assert bruta_22 > bruta_15

    def test_formula_correta(self):
        # taxa_bruta = taxa_isenta / (1 - aliq)
        taxa_isenta, aliq = 0.10, 0.15
        esperado = taxa_isenta / (1 - aliq)
        assert abs(_taxa_bruta_necessaria(taxa_isenta, aliq) - esperado) < 1e-12
