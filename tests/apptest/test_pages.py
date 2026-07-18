"""Testes de UI via streamlit.testing.v1.AppTest — rodam as páginas de verdade.

Execução isolada e obrigatória: `pytest tests/apptest` (ver conftest.py desta pasta,
que desmonta o mock global de streamlit e isola rede/disco).
"""

from streamlit.testing.v1 import AppTest

_TIMEOUT = 30


def _run(path: str) -> AppTest:
    at = AppTest.from_file(path)
    at.run(timeout=_TIMEOUT)
    assert not at.exception, f"{path} lançou exceção: {at.exception}"
    return at


def _clicar(at: AppTest, trecho_label: str) -> AppTest:
    botao = next(b for b in at.button if trecho_label in b.label)
    botao.click().run(timeout=_TIMEOUT)
    assert not at.exception, f"exceção após clicar em {trecho_label!r}: {at.exception}"
    return at


# ---------------------------------------------------------------------------
# Dashboard — Minha Carteira
# ---------------------------------------------------------------------------


class TestDashboard:
    def test_estado_vazio_sem_excecao(self):
        at = _run("pages/0_Dashboard.py")
        textos_info = " ".join(i.value for i in at.info)
        assert "Bem-vindo" in textos_info
        labels_botao = [b.label for b in at.button]
        assert any("Carregar Exemplo" in lbl for lbl in labels_botao)
        assert any("Adicionar ao portfólio" in lbl for lbl in labels_botao)

    def test_carregar_exemplo_popula_portfolio_e_metricas(self):
        at = _run("pages/0_Dashboard.py")
        _clicar(at, "Carregar Exemplo")

        labels_metric = [m.label for m in at.metric]
        for esperado in (
            "Capital Investido",
            "MaM Consolidado",
            "No Vencimento",
            "Saúde da Carteira",
        ):
            assert esperado in labels_metric, f"métrica {esperado!r} não encontrada"

        # Análise Detalhada: 4 abas principais + 2 sub-abas da calculadora de aportes
        assert len(at.tabs) == 6
        assert len(at.dataframe) >= 1  # tabela do portfólio

    def test_remover_posicao_volta_ao_estado_vazio(self):
        at = _run("pages/0_Dashboard.py")
        _clicar(at, "Carregar Exemplo")
        _clicar(at, "Limpar tudo")

        textos_info = " ".join(i.value for i in at.info)
        assert "Bem-vindo" in textos_info


# ---------------------------------------------------------------------------
# Qual Ativo Escolher? — Batalha de Cenários
# ---------------------------------------------------------------------------


class TestQualAtivo:
    def test_carrega_sem_excecao(self):
        at = _run("pages/1_Qual_Ativo.py")
        assert len(at.dataframe) >= 1 or len(at.plotly_chart) >= 1


# ---------------------------------------------------------------------------
# Comparar Produtos
# ---------------------------------------------------------------------------


class TestCompararProdutos:
    def test_carrega_com_os_seis_produtos(self):
        at = _run("pages/2_Comparar_Produtos.py")
        labels_metric = " ".join(m.label for m in at.metric)
        for produto in (
            "Tesouro IPCA+",
            "Tesouro Prefixado",
            "Tesouro Selic",
            "CDB",
            "LCI",
            "LCA",
        ):
            assert produto in labels_metric, f"produto {produto!r} não encontrado"
        # Um dos produtos é destacado como vencedor do horizonte padrão
        assert "🏆" in labels_metric


# ---------------------------------------------------------------------------
# Simulador Avançado (MaM)
# ---------------------------------------------------------------------------


class TestSimulador:
    def test_carrega_sem_excecao(self):
        _run("pages/3_Simulador_MaM.py")
