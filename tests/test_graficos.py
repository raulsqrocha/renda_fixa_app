"""Tests for core/graficos.py: pure helpers and figure structure (no Streamlit needed)."""

import plotly.graph_objects as go

from core.graficos import (
    AMARELO,
    AZUL,
    FUNDO,
    VERDE,
    VERMELHO,
    _hex_to_rgb,
    _layout_base,
    grafico_cenarios,
    grafico_score,
)


# ---------------------------------------------------------------------------
# _hex_to_rgb
# ---------------------------------------------------------------------------


class TestHexToRgb:
    def test_preto(self):
        assert _hex_to_rgb("#000000") == "0, 0, 0"

    def test_branco(self):
        assert _hex_to_rgb("#FFFFFF") == "255, 255, 255"

    def test_vermelho_puro(self):
        assert _hex_to_rgb("#FF0000") == "255, 0, 0"

    def test_cor_da_paleta_vermelho(self):
        # VERMELHO = "#E53E3E" → 229, 62, 62
        assert _hex_to_rgb(VERMELHO) == "229, 62, 62"

    def test_cor_da_paleta_verde(self):
        # VERDE = "#38A169" → 56, 161, 105
        assert _hex_to_rgb(VERDE) == "56, 161, 105"

    def test_sem_hash_nao_explode(self):
        # lstrip("#") funciona mesmo sem "#"
        assert _hex_to_rgb("E53E3E") == "229, 62, 62"


# ---------------------------------------------------------------------------
# _layout_base
# ---------------------------------------------------------------------------


class TestLayoutBase:
    def test_retorna_dict(self):
        assert isinstance(_layout_base("Título"), dict)

    def test_paper_bgcolor_e_fundo(self):
        layout = _layout_base("T")
        assert layout["paper_bgcolor"] == FUNDO

    def test_hovermode_x_unified(self):
        assert _layout_base("T")["hovermode"] == "x unified"

    def test_yaxis_prefix_padrao_brl(self):
        layout = _layout_base("T")
        assert layout["yaxis"]["tickprefix"] == "R$ "

    def test_yaxis_prefix_customizado(self):
        layout = _layout_base("T", yaxis_prefix="%")
        assert layout["yaxis"]["tickprefix"] == "%"

    def test_titulo_preservado(self):
        layout = _layout_base("Meu Gráfico")
        assert layout["title"]["text"] == "Meu Gráfico"

    def test_separadores_br(self):
        # separadores brasileiros: vírgula decimal, ponto milhar
        assert _layout_base("T")["separators"] == ",."


# ---------------------------------------------------------------------------
# grafico_score
# ---------------------------------------------------------------------------


class TestGraficoScore:
    def test_retorna_figure(self):
        assert isinstance(grafico_score(75), go.Figure)

    def test_tem_exatamente_um_trace(self):
        assert len(grafico_score(50).data) == 1

    def test_score_acima_70_label_sereno(self):
        fig = grafico_score(80)
        assert "Sereno" in fig.data[0].title.text

    def test_score_exato_70_e_sereno(self):
        fig = grafico_score(70)
        assert "Sereno" in fig.data[0].title.text

    def test_score_entre_40_e_70_label_atencao(self):
        fig = grafico_score(55)
        assert "Aten" in fig.data[0].title.text  # "Atenção"

    def test_score_exato_40_e_atencao(self):
        fig = grafico_score(40)
        assert "Aten" in fig.data[0].title.text

    def test_score_abaixo_40_label_risco_panico(self):
        fig = grafico_score(20)
        assert "Pânico" in fig.data[0].title.text

    def test_score_zero_nao_explode(self):
        fig = grafico_score(0)
        assert "Pânico" in fig.data[0].title.text

    def test_value_preservado_no_indicator(self):
        fig = grafico_score(85)
        assert fig.data[0].value == 85

    def test_cor_sereno_e_verde(self):
        fig = grafico_score(90)
        assert fig.data[0].number.font.color == VERDE

    def test_cor_atencao_e_amarelo(self):
        fig = grafico_score(60)
        assert fig.data[0].number.font.color == AMARELO

    def test_cor_panico_e_vermelho(self):
        fig = grafico_score(30)
        assert fig.data[0].number.font.color == VERMELHO


# ---------------------------------------------------------------------------
# grafico_cenarios
# ---------------------------------------------------------------------------


def _cenarios():
    return {
        "Base (5% IPCA)": {"valor_final": 12_000.0, "retorno_real_pct": 40.0},
        "Estresse (8% IPCA)": {"valor_final": 14_000.0, "retorno_real_pct": 40.0},
        "Otimista (3% IPCA)": {"valor_final": 11_000.0, "retorno_real_pct": 40.0},
    }


class TestGraficoCenarios:
    def test_retorna_figure(self):
        assert isinstance(
            grafico_cenarios(_cenarios(), anos=5, valor_investido=10_000), go.Figure
        )

    def test_tem_dois_traces(self):
        fig = grafico_cenarios(_cenarios(), anos=5, valor_investido=10_000)
        assert len(fig.data) == 2

    def test_primeiro_trace_e_bar(self):
        fig = grafico_cenarios(_cenarios(), anos=5, valor_investido=10_000)
        assert isinstance(fig.data[0], go.Bar)

    def test_segundo_trace_e_scatter(self):
        fig = grafico_cenarios(_cenarios(), anos=5, valor_investido=10_000)
        assert isinstance(fig.data[1], go.Scatter)

    def test_cor_base_e_azul(self):
        fig = grafico_cenarios(_cenarios(), anos=5, valor_investido=10_000)
        cores = list(fig.data[0].marker.color)
        # "Base" → AZUL
        assert cores[0] == AZUL

    def test_cor_estresse_e_vermelho(self):
        fig = grafico_cenarios(_cenarios(), anos=5, valor_investido=10_000)
        cores = list(fig.data[0].marker.color)
        # "Estresse" → VERMELHO
        assert cores[1] == VERMELHO

    def test_cor_otimista_e_verde(self):
        fig = grafico_cenarios(_cenarios(), anos=5, valor_investido=10_000)
        cores = list(fig.data[0].marker.color)
        # "Otimista" → VERDE (nem Base nem Estresse)
        assert cores[2] == VERDE
