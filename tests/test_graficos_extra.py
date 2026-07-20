"""Tests for core/graficos.py: remaining figure-returning functions."""

from datetime import date, timedelta

import pandas as pd
import plotly.graph_objects as go

from core.graficos import (
    AZUL,
    LARANJA,
    TEXTO,
    VERDE,
    VERMELHO,
    grafico_cenarios_batalha,
    grafico_curva_di,
    grafico_ipca_historico,
    grafico_markowitz,
    grafico_paradoxo,
    grafico_retorno_por_horizonte,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _df_paradoxo(n=20):
    # Datas 2020-2021 (passadas) — "Hoje" (2026) fica fora do range
    datas = pd.date_range("2020-01-01", periods=n, freq="MS")
    return pd.DataFrame(
        {
            "data": datas,
            "mam": [100.0 - i * 0.5 for i in range(n)],
            "carrego": [100.0 + i * 0.5 for i in range(n)],
        }
    )


def _df_paradoxo_com_hoje(n=30):
    """DataFrame com range que sempre inclui hoje dinamicamente."""
    hoje = pd.Timestamp.today().normalize()
    inicio = hoje - pd.DateOffset(months=6)
    datas = pd.date_range(inicio, periods=n, freq="MS")
    return pd.DataFrame(
        {
            "data": datas,
            "mam": [100.0 - i * 0.5 for i in range(n)],
            "carrego": [100.0 + i * 0.5 for i in range(n)],
        }
    )


def _df_ipca_historico():
    # 2022: 0.70%/mo → ~8.7% anual → VERMELHO (>=8%)
    # 2023: 0.50%/mo → ~6.2% anual → LARANJA (5-8%)
    # 2024: 0.39%/mo → ~4.8% anual → VERDE (<5%)
    d22 = pd.date_range("2022-01-01", periods=12, freq="MS")
    d23 = pd.date_range("2023-01-01", periods=12, freq="MS")
    d24 = pd.date_range("2024-01-01", periods=12, freq="MS")
    datas = list(d22) + list(d23) + list(d24)
    valores = [0.70] * 12 + [0.50] * 12 + [0.39] * 12
    return pd.DataFrame({"data": pd.DatetimeIndex(datas), "valor": valores})


def _df_ipca_com_marcos():
    """DataFrame com 2015 e 2021 para disparar anotações de marcos históricos."""
    registros = []
    for year, rate in [(2015, 0.89), (2021, 0.84)]:
        for m in pd.date_range(f"{year}-01-01", periods=12, freq="MS"):
            registros.append({"data": m, "valor": float(rate)})
    return pd.DataFrame(registros)


def _analises_batalha():
    return [
        {"nome": "Tesouro IPCA+ 2035", "ret_adv": 5.0, "ret_neu": 8.0, "ret_fav": 12.0},
        {
            "nome": "Tesouro Selic 2031",
            "ret_adv": 12.0,
            "ret_neu": 13.0,
            "ret_fav": 14.0,
        },
    ]


def _analises_markowitz():
    return [
        {
            "nome": "Tesouro IPCA+ 2035",
            "tipo": "ipca_mais",
            "risco_std": 2.0,
            "ret_neu": 8.0,
            "ret_adv": 5.0,
            "ret_fav": 12.0,
            "risco_label": "Média",
        },
        {
            "nome": "Tesouro Selic 2031",
            "tipo": "selic",
            "risco_std": 0.0,
            "ret_neu": 13.0,
            "ret_adv": 12.0,
            "ret_fav": 14.0,
            "risco_label": "Nenhuma",
        },
        {
            "nome": "Tesouro Prefixado 2029",
            "tipo": "pre",
            "risco_std": 1.5,
            "ret_neu": 10.0,
            "ret_adv": 7.0,
            "ret_fav": 14.0,
            "risco_label": "Baixa",
        },
    ]


def _resultados_horizonte(reinvest=False):
    a = {
        "nome": "Tesouro IPCA+ 2035",
        "ret_adv": 5.0,
        "ret_neu": 8.0,
        "ret_fav": 12.0,
        "reinvest": reinvest,
    }
    return {3: [a], 5: [a], 10: [a]}


# ---------------------------------------------------------------------------
# grafico_paradoxo
# ---------------------------------------------------------------------------


class TestGraficoParadoxo:
    def test_retorna_figure(self):
        assert isinstance(grafico_paradoxo(_df_paradoxo()), go.Figure)

    def test_tres_traces_sem_opcoes(self):
        # fill area + MaM + carrego
        fig = grafico_paradoxo(_df_paradoxo())
        assert len(fig.data) == 3

    def test_segundo_trace_mam_e_vermelho(self):
        fig = grafico_paradoxo(_df_paradoxo())
        assert fig.data[1].line.color == VERMELHO

    def test_terceiro_trace_carrego_e_verde(self):
        fig = grafico_paradoxo(_df_paradoxo())
        assert fig.data[2].line.color == VERDE

    def test_data_compra_dentro_range_adiciona_annotation_compra(self):
        df = _df_paradoxo()
        fig = grafico_paradoxo(df, data_compra=date(2020, 3, 1))
        textos = [a.text for a in fig.layout.annotations]
        assert any("Compra" in t for t in textos)

    def test_data_compra_fora_range_nao_adiciona(self):
        df = _df_paradoxo()
        fig = grafico_paradoxo(df, data_compra=date(2030, 1, 1))
        textos = [a.text for a in fig.layout.annotations]
        assert not any("Compra" in t for t in textos)

    def test_datas_cupom_passadas_nao_adicionam_annotation(self):
        df = _df_paradoxo()
        # 2020-06-01 é passado (antes de 2026-05-26 hoje)
        fig = grafico_paradoxo(df, datas_cupom=[date(2020, 6, 1)])
        textos = [a.text for a in fig.layout.annotations]
        assert not any("Cupom" in t for t in textos)

    def test_vencimento_dentro_range_adiciona_annotation(self):
        df = _df_paradoxo()
        fig = grafico_paradoxo(df, data_vencimento=date(2020, 10, 1))
        textos = [a.text for a in fig.layout.annotations]
        assert any("Vencimento" in t for t in textos)

    def test_hoje_dentro_range_adiciona_shape_e_annotation_hoje(self):
        fig = grafico_paradoxo(_df_paradoxo_com_hoje())
        textos = [a.text for a in fig.layout.annotations]
        assert any("Hoje" in t for t in textos)
        assert len(fig.layout.shapes) >= 1

    def test_cupom_futuro_dentro_range_adiciona_annotation_cupom(self):
        df = _df_paradoxo_com_hoje()
        prox_cupom = date.today() + timedelta(days=120)
        fig = grafico_paradoxo(df, datas_cupom=[prox_cupom])
        textos = [a.text for a in fig.layout.annotations]
        assert any("Cupom" in t for t in textos)

    # ---- df_historico_real (MaM real observada) ----
    def test_sem_historico_real_mantem_label_original(self):
        fig = grafico_paradoxo(_df_paradoxo(), df_historico_real=None)
        assert fig.data[1].name == "Marcação a Mercado (MaM)"
        assert len(fig.data) == 3

    def test_historico_real_vazio_nao_adiciona_trace(self):
        fig = grafico_paradoxo(_df_paradoxo(), df_historico_real=pd.DataFrame())
        assert len(fig.data) == 3

    def test_historico_real_adiciona_quarto_trace_branco(self):
        df_real = pd.DataFrame(
            {
                "data": pd.date_range("2020-01-01", periods=5, freq="D"),
                "mam": [10_000.0, 10_050.0, 10_020.0, 10_080.0, 10_100.0],
            }
        )
        fig = grafico_paradoxo(_df_paradoxo(), df_historico_real=df_real)
        assert len(fig.data) == 4
        assert fig.data[3].name == "MaM Real Observada"
        assert fig.data[3].line.color == TEXTO

    def test_historico_real_relabela_linha_projetada(self):
        df_real = pd.DataFrame(
            {"data": pd.date_range("2020-01-01", periods=3, freq="D"), "mam": [1, 2, 3]}
        )
        fig = grafico_paradoxo(_df_paradoxo(), df_historico_real=df_real)
        assert fig.data[1].name == "MaM Projetada (simulação)"


# ---------------------------------------------------------------------------
# grafico_ipca_historico
# ---------------------------------------------------------------------------


class TestGraficoIpcaHistorico:
    def test_retorna_figure(self):
        assert isinstance(grafico_ipca_historico(_df_ipca_historico()), go.Figure)

    def test_tem_um_trace_bar(self):
        fig = grafico_ipca_historico(_df_ipca_historico())
        assert len(fig.data) == 1
        assert isinstance(fig.data[0], go.Bar)

    def test_alto_ipca_e_vermelho(self):
        # 2022 → ~8.7% → VERMELHO
        fig = grafico_ipca_historico(_df_ipca_historico())
        assert list(fig.data[0].marker.color)[0] == VERMELHO

    def test_medio_ipca_e_laranja(self):
        # 2023 → ~6.2% → LARANJA
        fig = grafico_ipca_historico(_df_ipca_historico())
        assert list(fig.data[0].marker.color)[1] == LARANJA

    def test_baixo_ipca_e_verde(self):
        # 2024 → ~4.8% → VERDE
        fig = grafico_ipca_historico(_df_ipca_historico())
        assert list(fig.data[0].marker.color)[2] == VERDE

    def test_marcos_historicos_2015_2021_adicionam_annotations(self):
        fig = grafico_ipca_historico(_df_ipca_com_marcos())
        textos = [a.text for a in fig.layout.annotations]
        assert any("Crise" in t for t in textos)
        assert any("Ressurg" in t for t in textos)


# ---------------------------------------------------------------------------
# grafico_curva_di
# ---------------------------------------------------------------------------


class TestGraficoCurvaDi:
    _dados = [
        {"vencimento": "Jan/27", "taxa": 14.50},
        {"vencimento": "Jan/28", "taxa": 13.80},
        {"vencimento": "Jan/29", "taxa": 13.20},
    ]

    def test_retorna_figure(self):
        assert isinstance(grafico_curva_di(self._dados), go.Figure)

    def test_exatamente_um_trace(self):
        assert len(grafico_curva_di(self._dados).data) == 1

    def test_trace_e_scatter(self):
        assert isinstance(grafico_curva_di(self._dados).data[0], go.Scatter)

    def test_trace_cor_azul(self):
        assert grafico_curva_di(self._dados).data[0].line.color == AZUL

    def test_tres_pontos(self):
        assert len(grafico_curva_di(self._dados).data[0].x) == 3


# ---------------------------------------------------------------------------
# grafico_cenarios_batalha
# ---------------------------------------------------------------------------


class TestGraficoCenariosBatalha:
    def test_retorna_figure(self):
        assert isinstance(grafico_cenarios_batalha(_analises_batalha()), go.Figure)

    def test_tres_traces_bar(self):
        fig = grafico_cenarios_batalha(_analises_batalha())
        assert len(fig.data) == 3
        for trace in fig.data:
            assert isinstance(trace, go.Bar)

    def test_adverso_e_vermelho(self):
        assert (
            grafico_cenarios_batalha(_analises_batalha()).data[0].marker.color
            == VERMELHO
        )

    def test_neutro_e_azul(self):
        assert (
            grafico_cenarios_batalha(_analises_batalha()).data[1].marker.color == AZUL
        )

    def test_favoravel_e_verde(self):
        assert (
            grafico_cenarios_batalha(_analises_batalha()).data[2].marker.color == VERDE
        )

    def test_nomes_curtos_sem_prefixo_tesouro(self):
        fig = grafico_cenarios_batalha(_analises_batalha())
        assert all("Tesouro" not in str(x) for x in fig.data[0].x)


# ---------------------------------------------------------------------------
# grafico_markowitz
# ---------------------------------------------------------------------------


class TestGraficoMarkowitz:
    def test_retorna_figure(self):
        assert isinstance(grafico_markowitz(_analises_markowitz()), go.Figure)

    def test_tem_traces(self):
        assert len(grafico_markowitz(_analises_markowitz()).data) > 0

    def test_fronteira_adicionada_com_2_ou_mais_ativos(self):
        fig = grafico_markowitz(_analises_markowitz())
        assert any(isinstance(t, go.Scatter) for t in fig.data)

    def test_sem_carteira_mix_sem_trace_estrela(self):
        fig = grafico_markowitz(_analises_markowitz(), carteira_mix=None)
        nomes = [t.name for t in fig.data if t.name]
        assert not any("Carteira Mista" in str(n) for n in nomes)

    def test_com_carteira_mix_adiciona_trace_estrela(self):
        mix = {
            "nome_principal": "Tesouro IPCA+ 2035",
            "nome_liquida": "Tesouro Selic 2031",
            "peso_principal": 0.70,
            "peso_liquida": 0.30,
            "risco_std": 1.4,
            "ret_neu": 9.5,
        }
        fig = grafico_markowitz(_analises_markowitz(), carteira_mix=mix)
        nomes = [t.name for t in fig.data if t.name]
        assert any("Carteira Mista" in str(n) for n in nomes)

    def test_com_portfolios_mc_adiciona_nuvem(self):
        mc = [{"risco_std": i * 0.1, "ret_neu": 8.0 + i * 0.05} for i in range(10)]
        fig = grafico_markowitz(_analises_markowitz(), portfolios_mc=mc)
        nomes = [t.name for t in fig.data if t.name]
        assert any("possíveis" in str(n) for n in nomes)


# ---------------------------------------------------------------------------
# grafico_retorno_por_horizonte
# ---------------------------------------------------------------------------


class TestGraficoRetornoPorHorizonte:
    def test_retorna_figure(self):
        assert isinstance(
            grafico_retorno_por_horizonte(_resultados_horizonte(), 5), go.Figure
        )

    def test_dict_vazio_retorna_figure_sem_traces(self):
        fig = grafico_retorno_por_horizonte({}, 5)
        assert isinstance(fig, go.Figure)
        assert len(fig.data) == 0

    def test_sem_reinvest_tem_traces(self):
        fig = grafico_retorno_por_horizonte(_resultados_horizonte(reinvest=False), 5)
        assert len(fig.data) >= 1

    def test_com_reinvest_adiciona_linha_tracejada(self):
        a = {
            "nome": "Tesouro IPCA+ 2030",
            "ret_adv": 4.0,
            "ret_neu": 7.0,
            "ret_fav": 10.0,
            "reinvest": True,
        }
        resultados = {3: [a], 5: [a]}
        fig = grafico_retorno_por_horizonte(resultados, 5)
        dash_styles = [
            t.line.dash
            for t in fig.data
            if hasattr(t, "line") and t.line and t.line.dash
        ]
        assert any(d == "dot" for d in dash_styles)

    def test_horizonte_atual_gera_vline(self):
        fig = grafico_retorno_por_horizonte(_resultados_horizonte(), 5)
        assert len(fig.layout.shapes) >= 1

    def test_bridge_feito_ao_transicionar_carrego_para_reinvest(self):
        a_c = {
            "nome": "Tesouro IPCA+ 2030",
            "ret_adv": 5.0,
            "ret_neu": 7.0,
            "ret_fav": 10.0,
            "reinvest": False,
        }
        a_r = {
            "nome": "Tesouro IPCA+ 2030",
            "ret_adv": 6.0,
            "ret_neu": 8.0,
            "ret_fav": 11.0,
            "reinvest": True,
        }
        resultados = {3: [a_c], 5: [a_r], 10: [a_r]}
        fig = grafico_retorno_por_horizonte(resultados, 5)
        dashes = [
            t.line.dash
            for t in fig.data
            if hasattr(t, "line") and t.line and t.line.dash is not None
        ]
        assert any(d == "dot" for d in dashes)

    def test_nome_sem_resultado_em_horizonte_e_ignorado(self):
        a = {
            "nome": "Tesouro IPCA+ 2035",
            "ret_adv": 5.0,
            "ret_neu": 8.0,
            "ret_fav": 12.0,
            "reinvest": False,
        }
        resultados = {5: [a], 10: []}
        fig = grafico_retorno_por_horizonte(resultados, 5)
        assert isinstance(fig, go.Figure)
