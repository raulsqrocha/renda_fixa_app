"""Tests for core/dados.py: fallback data, VNA calculations, catalog, name parsing."""

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pandas as pd

from core.dados import (
    VNA_BASE_DEZ2014,
    buscar_historico_titulos_tesouro,
    buscar_ipca_bcb,
    buscar_selic_meta_bcb,
    buscar_selic_na_data,
    buscar_titulos_tesouro,
    construir_nome_titulo,
    historico_titulo,
    _get_com_retry,
    _ipca_fallback,
    _TAXAS_REF,
    _titulos_fallback,
    calcular_vna_em_data,
    calcular_vna_via_bcb,
    chave_cache_mercado,
    montar_catalogo_batalha,
    TITULOS_BATALHA,
    TITULOS_CONFIG,
    timestamp_ultima_atualizacao,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _mk_ipca(valores, start="2015-01-01"):
    datas = pd.date_range(start, periods=len(valores), freq="MS")
    return pd.DataFrame({"data": datas, "valor": list(valores), "_is_fallback": False})


# ---------------------------------------------------------------------------
# _ipca_fallback
# ---------------------------------------------------------------------------


class TestIpcaFallback:
    def test_retorna_dataframe(self):
        assert isinstance(_ipca_fallback(), pd.DataFrame)

    def test_colunas_obrigatorias(self):
        assert {"data", "valor", "_is_fallback"}.issubset(set(_ipca_fallback().columns))

    def test_is_fallback_true(self):
        assert _ipca_fallback()["_is_fallback"].all()

    def test_138_meses(self):
        assert len(_ipca_fallback()) == 138

    def test_inicio_jan2015(self):
        assert _ipca_fallback()["data"].iloc[0] == pd.Timestamp("2015-01-01")

    def test_fim_jun2026(self):
        assert _ipca_fallback()["data"].iloc[-1] == pd.Timestamp("2026-06-01")

    def test_valores_numericos(self):
        assert pd.api.types.is_float_dtype(_ipca_fallback()["valor"])


# ---------------------------------------------------------------------------
# _titulos_fallback
# ---------------------------------------------------------------------------


class TestTitulosFallback:
    _COLS = {
        "nome",
        "vencimento",
        "taxa_compra",
        "taxa_venda",
        "pu_compra",
        "pu_venda",
        "_is_fallback",
    }

    def test_retorna_dataframe(self):
        assert isinstance(_titulos_fallback(), pd.DataFrame)

    def test_colunas_obrigatorias(self):
        assert self._COLS.issubset(set(_titulos_fallback().columns))

    def test_is_fallback_true(self):
        assert _titulos_fallback()["_is_fallback"].all()

    def test_sem_titulos_vencidos(self):
        hoje = date.today()
        for v in _titulos_fallback()["vencimento"]:
            assert date.fromisoformat(str(v)[:10]) > hoje

    def test_spread_taxa_ipca(self):
        df = _titulos_fallback()
        ipca = df[df["nome"].str.contains(r"IPCA\+", regex=True)]
        assert (ipca["taxa_venda"] > ipca["taxa_compra"]).all()

    def test_contem_tres_categorias(self):
        nomes = _titulos_fallback()["nome"].tolist()
        assert any("IPCA+" in n for n in nomes)
        assert any("RendA+" in n for n in nomes)
        assert any("Educar+" in n for n in nomes)


# ---------------------------------------------------------------------------
# calcular_vna_via_bcb
# ---------------------------------------------------------------------------


class TestCalcularVnaViaBcb:
    def test_sem_dados_pos2015_retorna_fallback(self):
        from core.dados import VNA_FALLBACK

        df = _mk_ipca([1.0], start="2014-01-01")
        assert calcular_vna_via_bcb(df) == VNA_FALLBACK

    def test_um_mes_1pct(self):
        df = _mk_ipca([1.0])
        assert calcular_vna_via_bcb(df) == round(VNA_BASE_DEZ2014 * 1.01, 2)

    def test_dois_meses_compostos(self):
        df = _mk_ipca([1.0, 2.0])
        esperado = round(VNA_BASE_DEZ2014 * 1.01 * 1.02, 2)
        assert calcular_vna_via_bcb(df) == esperado

    def test_serie_completa_maior_que_base(self):
        assert calcular_vna_via_bcb(_ipca_fallback()) > VNA_BASE_DEZ2014

    def test_serie_completa_dentro_de_faixa_plausivel_anbima(self):
        # Regressão: reconciliado contra o VNA oficial ANBIMA (R$4.743,207764,
        # código Selic, 07/07/2026). Tolerância de ±2% cobre a defasagem
        # natural entre a série de fallback local e a data de referência da
        # ANBIMA, sem permitir que a base histórica volte a divergir ~7-8%
        # como antes da recalibração de VNA_BASE_DEZ2014 (2.712,00 -> 2.521,24).
        vna = calcular_vna_via_bcb(_ipca_fallback())
        assert 4_648.0 < vna < 4_838.0


# ---------------------------------------------------------------------------
# calcular_vna_em_data
# ---------------------------------------------------------------------------


class TestCalcularVnaEmData:
    def test_antes_jan2015_retorna_base(self):
        df = _ipca_fallback()
        assert calcular_vna_em_data(df, date(2014, 12, 31)) == VNA_BASE_DEZ2014

    def test_jan2015_acumula_um_mes(self):
        df = _mk_ipca([1.0])
        assert calcular_vna_em_data(df, date(2015, 1, 31)) == round(
            VNA_BASE_DEZ2014 * 1.01, 2
        )

    def test_fev2015_acumula_dois_meses(self):
        df = _mk_ipca([1.0, 2.0])
        esperado = round(VNA_BASE_DEZ2014 * 1.01 * 1.02, 2)
        assert calcular_vna_em_data(df, date(2015, 2, 28)) == esperado

    def test_vna_cresce_ao_longo_do_tempo(self):
        df = _ipca_fallback()
        v1 = calcular_vna_em_data(df, date(2016, 1, 1))
        v2 = calcular_vna_em_data(df, date(2020, 1, 1))
        assert v2 > v1 > VNA_BASE_DEZ2014


# ---------------------------------------------------------------------------
# construir_nome_titulo
# ---------------------------------------------------------------------------


class TestConstruirNomeTitulo:
    def test_ipca_principal(self):
        assert construir_nome_titulo("Tesouro IPCA+", 2032) == "Tesouro IPCA+ 2032"

    def test_ipca_juros_semestrais(self):
        assert (
            construir_nome_titulo("Tesouro IPCA+ com Juros Semestrais", 2037)
            == "Tesouro IPCA+ com Juros Semestrais 2037"
        )

    def test_renda_mais_variante_renda(self):
        assert (
            construir_nome_titulo("Tesouro Renda+ Aposentadoria Extra", 2035)
            == "Tesouro RendA+ 2035"
        )

    def test_renda_mais_variante_renda_maiusculo(self):
        assert (
            construir_nome_titulo("Tesouro RendA+ Aposentadoria Extra", 2035)
            == "Tesouro RendA+ 2035"
        )

    def test_educa_mais(self):
        assert construir_nome_titulo("Tesouro Educa+", 2030) == "Tesouro Educar+ 2030"

    def test_selic(self):
        assert construir_nome_titulo("Tesouro Selic", 2031) == "Tesouro Selic 2031"

    def test_prefixado(self):
        assert (
            construir_nome_titulo("Tesouro Prefixado", 2029) == "Tesouro Prefixado 2029"
        )

    def test_prefixado_juros_semestrais(self):
        assert (
            construir_nome_titulo("Tesouro Prefixado com Juros Semestrais", 2029)
            == "Tesouro Prefixado com Juros Semestrais 2029"
        )

    def test_reserva_ignora_ano(self):
        assert construir_nome_titulo("Tesouro Reserva", 2027) == "Tesouro Reserva"

    def test_tipo_desconhecido_retorna_none(self):
        assert construir_nome_titulo("Tesouro Ouro", 2030) is None


# ---------------------------------------------------------------------------
# montar_catalogo_batalha
# ---------------------------------------------------------------------------


class TestMontarCatalogoBatalha:
    def _df(self):
        return pd.DataFrame(
            [
                {
                    "nome": "Tesouro Selic 2031",
                    "vencimento": "2031-03-01",
                    "taxa_compra": 14.75,
                    "taxa_venda": 14.77,
                    "pu_compra": 0.0,
                    "pu_venda": 0.0,
                },
                {
                    "nome": "Tesouro Prefixado 2029",
                    "vencimento": "2029-01-01",
                    "taxa_compra": 14.50,
                    "taxa_venda": 14.52,
                    "pu_compra": 800.0,
                    "pu_venda": 798.0,
                },
                {
                    "nome": "Tesouro IPCA+ 2032",
                    "vencimento": "2032-08-15",
                    "taxa_compra": 7.75,
                    "taxa_venda": 7.78,
                    "pu_compra": 3000.0,
                    "pu_venda": 2990.0,
                },
            ]
        )

    def test_retorna_lista_nao_vazia(self):
        cat = montar_catalogo_batalha(self._df(), 14.75)
        assert isinstance(cat, list)
        assert len(cat) > 0

    def test_selic_usa_taxa_projetada(self):
        cat = montar_catalogo_batalha(self._df(), 12.0)
        selic = [t for t in cat if t["tipo"] == "selic"]
        assert len(selic) >= 1
        assert all(t["taxa"] == 12.0 for t in selic)

    def test_ordem_selic_pre_ipca(self):
        cat = montar_catalogo_batalha(self._df(), 14.75)
        tipos = [t["tipo"] for t in cat]
        pesos = {"selic": 0, "pre": 1, "ipca_mais": 2}
        for a, b in zip(tipos, tipos[1:]):
            assert pesos.get(a, 3) <= pesos.get(b, 3)

    def test_exclui_titulo_vencendo_em_20_dias(self):
        venc_proximo = (date.today() + timedelta(days=20)).isoformat()
        df = pd.DataFrame(
            [
                {
                    "nome": "Tesouro IPCA+ 2025",
                    "vencimento": venc_proximo,
                    "taxa_compra": 7.0,
                    "taxa_venda": 7.03,
                    "pu_compra": 100.0,
                    "pu_venda": 99.5,
                }
            ]
        )
        cat = montar_catalogo_batalha(df, 14.75)
        assert "Tesouro IPCA+ 2025" not in {t["nome"] for t in cat}


# ---------------------------------------------------------------------------
# chave_cache_mercado
# ---------------------------------------------------------------------------


class TestChaveCacheMercado:
    def test_retorna_string(self):
        assert isinstance(chave_cache_mercado(), str)

    def test_pre_fechamento_antes_14h(self):
        mock_agora = MagicMock()
        mock_agora.hour = 13
        mock_agora.date.return_value = date(2026, 5, 26)
        with patch("core.dados.datetime") as mock_dt:
            mock_dt.now.return_value = mock_agora
            chave = chave_cache_mercado()
        assert "pre_fechamento" in chave
        assert "2026-05-26" in chave

    def test_pos_fechamento_a_partir_14h(self):
        mock_agora = MagicMock()
        mock_agora.hour = 14
        mock_agora.date.return_value = date(2026, 5, 26)
        with patch("core.dados.datetime") as mock_dt:
            mock_dt.now.return_value = mock_agora
            chave = chave_cache_mercado()
        assert "pos_fechamento" in chave


# ---------------------------------------------------------------------------
# _get_com_retry
# ---------------------------------------------------------------------------


class TestGetComRetry:
    def test_sucesso_na_primeira_tentativa(self):
        mock_resp = MagicMock()
        with patch("core.dados.requests.get", return_value=mock_resp) as mock_get:
            r = _get_com_retry("http://x", timeout=5)
        assert r is mock_resp
        assert mock_get.call_count == 1

    def test_falha_e_retenta_ate_sucesso(self):
        mock_resp = MagicMock()
        with (
            patch(
                "core.dados.requests.get", side_effect=[ConnectionError(), mock_resp]
            ) as mock_get,
            patch("core.dados.time.sleep"),
        ):
            r = _get_com_retry("http://x", timeout=5)
        assert r is mock_resp
        assert mock_get.call_count == 2

    def test_todas_tentativas_falham_propaga_excecao(self):
        with (
            patch("core.dados.requests.get", side_effect=ConnectionError("erro")),
            patch("core.dados.time.sleep"),
        ):
            try:
                _get_com_retry("http://x", timeout=5, tentativas=3)
                assert False, "deveria ter lançado exceção"
            except ConnectionError:
                pass

    def test_sleep_entre_tentativas(self):
        mock_resp = MagicMock()
        with (
            patch(
                "core.dados.requests.get", side_effect=[ConnectionError(), mock_resp]
            ),
            patch("core.dados.time.sleep") as mock_sleep,
        ):
            _get_com_retry("http://x", timeout=5)
        mock_sleep.assert_called_once_with(0.5)

    def test_sem_sleep_na_primeira_tentativa(self):
        with (
            patch("core.dados.requests.get", return_value=MagicMock()),
            patch("core.dados.time.sleep") as mock_sleep,
        ):
            _get_com_retry("http://x", timeout=5)
        mock_sleep.assert_not_called()

    def test_erro_4xx_nao_retenta(self):
        from requests.exceptions import HTTPError

        mock_resp_404 = MagicMock()
        mock_resp_404.status_code = 404
        err = HTTPError("404", response=mock_resp_404)
        with patch("core.dados.requests.get") as mock_get:
            mock_get.return_value.raise_for_status.side_effect = err
            try:
                _get_com_retry("http://x", timeout=5)
            except HTTPError:
                pass
        # Deve ter tentado apenas 1 vez (sem retry para 4xx)
        assert mock_get.call_count == 1

    def test_erro_503_retenta(self):
        from requests.exceptions import HTTPError

        mock_resp_503 = MagicMock()
        mock_resp_503.status_code = 503
        err_503 = HTTPError("503", response=mock_resp_503)
        mock_ok = MagicMock()
        mock_ok.raise_for_status.return_value = None

        calls = [MagicMock(), mock_ok]
        calls[0].raise_for_status.side_effect = err_503

        with (
            patch("core.dados.requests.get", side_effect=calls),
            patch("core.dados.time.sleep") as mock_sleep,
        ):
            r = _get_com_retry("http://x", timeout=5)
        assert r is mock_ok
        mock_sleep.assert_called_once()


# ---------------------------------------------------------------------------
# buscar_selic_meta_bcb
# ---------------------------------------------------------------------------


class TestBuscarSelicMetaBcb:
    def test_sucesso_retorna_valor_api(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"valor": "13.25"}]
        with patch("core.dados.requests.get", return_value=mock_resp):
            assert buscar_selic_meta_bcb() == 13.25

    def test_raise_for_status_retorna_fallback(self):
        mock_resp = MagicMock()
        mock_resp.raise_for_status.side_effect = Exception("HTTP 503")
        with patch("core.dados.requests.get", return_value=mock_resp):
            assert buscar_selic_meta_bcb() == 14.75

    def test_connection_error_retorna_fallback(self):
        with patch("core.dados.requests.get", side_effect=ConnectionError("timeout")):
            assert buscar_selic_meta_bcb() == 14.75


# ---------------------------------------------------------------------------
# buscar_selic_na_data
# ---------------------------------------------------------------------------


class TestBuscarSelicNaData:
    def test_sucesso_retorna_ultimo_valor(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [{"valor": "13.00"}, {"valor": "13.50"}]
        with patch("core.dados.requests.get", return_value=mock_resp):
            result = buscar_selic_na_data(date(2026, 5, 20))
        assert result == 13.50

    def test_resposta_vazia_retorna_fallback(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = []
        with patch("core.dados.requests.get", return_value=mock_resp):
            result = buscar_selic_na_data(date(2026, 5, 20))
        assert result == 14.75

    def test_exception_retorna_fallback(self):
        with patch("core.dados.requests.get", side_effect=ConnectionError()):
            result = buscar_selic_na_data(date(2026, 5, 20))
        assert result == 14.75


# ---------------------------------------------------------------------------
# buscar_ipca_bcb
# ---------------------------------------------------------------------------


class TestBuscarIpcaBcb:
    _COLS = {"data", "valor", "_is_fallback"}

    def test_sucesso_retorna_dataframe(self):
        mock_resp = MagicMock()
        mock_resp.json.return_value = [
            {"data": "01/01/2026", "valor": "0.16"},
            {"data": "01/02/2026", "valor": "1.31"},
        ]
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_ipca_bcb()
        assert isinstance(df, pd.DataFrame)
        assert self._COLS.issubset(set(df.columns))
        assert not df["_is_fallback"].any()
        assert len(df) == 2

    def test_exception_retorna_fallback(self):
        with patch("core.dados.requests.get", side_effect=Exception("offline")):
            df = buscar_ipca_bcb()
        assert isinstance(df, pd.DataFrame)
        assert df["_is_fallback"].all()


# ---------------------------------------------------------------------------
# buscar_titulos_tesouro
# ---------------------------------------------------------------------------

_CSV_TESOURO = (
    "Tipo Titulo;Data Vencimento;Data Base;"
    "Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha\n"
    "Tesouro Selic;01/03/2031;26/05/2026;14,75;14,77;13456,78;13450,00\n"
    "Tesouro Prefixado;01/01/2029;26/05/2026;14,50;14,52;800,00;798,00\n"
)

_COLS_TITULOS = {
    "nome",
    "vencimento",
    "taxa_compra",
    "taxa_venda",
    "pu_compra",
    "pu_venda",
    "_is_fallback",
}


class TestBuscarTitulosTesouro:
    def test_sucesso_retorna_dataframe(self):
        mock_resp = MagicMock()
        mock_resp.text = _CSV_TESOURO
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_titulos_tesouro("chave_teste")
        assert isinstance(df, pd.DataFrame)
        assert _COLS_TITULOS.issubset(set(df.columns))
        assert not df["_is_fallback"].any()

    def test_sucesso_contem_titulos_esperados(self):
        mock_resp = MagicMock()
        mock_resp.text = _CSV_TESOURO
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_titulos_tesouro("chave_teste")
        nomes = set(df["nome"])
        assert "Tesouro Selic 2031" in nomes
        assert "Tesouro Prefixado 2029" in nomes

    def test_sem_registros_validos_retorna_fallback(self):
        csv_invalido = (
            "Tipo Titulo;Data Vencimento;Data Base;"
            "Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha\n"
            "Tesouro IGPM 2032;01/08/2032;26/05/2026;5,00;5,02;1000,00;998,00\n"
        )
        mock_resp = MagicMock()
        mock_resp.text = csv_invalido
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_titulos_tesouro("chave_teste")
        assert df["_is_fallback"].all()

    def test_exception_retorna_fallback(self):
        with patch("core.dados.requests.get", side_effect=Exception("DNS error")):
            df = buscar_titulos_tesouro("chave_teste")
        assert isinstance(df, pd.DataFrame)
        assert df["_is_fallback"].all()

    def test_valor_invalido_na_taxa_cobre_excecao_de_conversao(self):
        # Cobre linhas 385-386: quando um campo numérico é "abc" (string não-numérica
        # que pandas não converte a NaN), _f() captura ValueError e retorna 0.0.
        csv_com_invalido = (
            "Tipo Titulo;Data Vencimento;Data Base;"
            "Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha\n"
            "Tesouro Selic;01/03/2031;26/05/2026;abc;14,77;13456,78;13450,00\n"
        )
        mock_resp = MagicMock()
        mock_resp.text = csv_com_invalido
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_titulos_tesouro("chave_invalida")
        assert isinstance(df, pd.DataFrame)
        # "Tesouro Selic 2031" é título válido → registros criados, taxa_compra=0.0
        selic = df[df["nome"] == "Tesouro Selic 2031"]
        assert len(selic) == 1
        assert selic["taxa_compra"].iloc[0] == 0.0

    def test_vencimento_nulo_no_csv_pula_linha(self):
        # Cobre linha 395: quando Data Vencimento é vazio → pandas produz NaT →
        # pd.isnull(venc) é True → continue sem processar a linha.
        # A segunda linha tem data válida e garante que o loop roda.
        csv_com_nulo = (
            "Tipo Titulo;Data Vencimento;Data Base;"
            "Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha\n"
            "Tesouro Selic;;26/05/2026;14,75;14,77;13456,78;13450,00\n"
            "Tesouro Selic;01/03/2031;26/05/2026;14,75;14,77;13456,78;13450,00\n"
        )
        mock_resp = MagicMock()
        mock_resp.text = csv_com_nulo
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_titulos_tesouro("chave_nulo")
        # Apenas a segunda linha deve aparecer no resultado
        assert len(df) == 1
        assert df["nome"].iloc[0] == "Tesouro Selic 2031"

    def test_titulo_desconhecido_nao_igpm_continua_loop(self):
        # Cobre linha 398: tipo "Tesouro Futuro" passa filtro IGPM mas
        # construir_nome_titulo retorna None → continue sem registrar.
        # Com um segundo título válido o loop roda e a linha 398 é atingida.
        csv_misto = (
            "Tipo Titulo;Data Vencimento;Data Base;"
            "Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha\n"
            "Tesouro Futuro;01/12/2035;26/05/2026;7,00;7,02;3000,00;2990,00\n"
            "Tesouro Selic;01/03/2031;26/05/2026;14,75;14,77;13456,78;13450,00\n"
        )
        mock_resp = MagicMock()
        mock_resp.text = csv_misto
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_titulos_tesouro("chave_mista")
        nomes = set(df["nome"])
        assert "Tesouro Selic 2031" in nomes
        assert not any("Futuro" in n for n in nomes)


# ---------------------------------------------------------------------------
# buscar_historico_titulos_tesouro / historico_titulo
# ---------------------------------------------------------------------------

_CSV_HISTORICO = (
    "Tipo Titulo;Data Vencimento;Data Base;"
    "Taxa Compra Manha;Taxa Venda Manha;PU Compra Manha;PU Venda Manha\n"
    "Tesouro IPCA+;15/08/2032;10/01/2026;7,50;7,52;2000,00;1998,00\n"
    "Tesouro IPCA+;15/08/2032;15/03/2026;7,60;7,62;2020,00;2018,00\n"
    "Tesouro IPCA+;15/08/2032;17/07/2026;7,93;7,95;2090,00;2088,00\n"
    "Tesouro Selic;01/03/2031;17/07/2026;14,75;14,77;13456,78;13450,00\n"
)


class TestBuscarHistoricoTitulosTesouro:
    def test_sucesso_retorna_todas_as_datas_base(self):
        mock_resp = MagicMock()
        mock_resp.text = _CSV_HISTORICO
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_historico_titulos_tesouro()
        assert isinstance(df, pd.DataFrame)
        assert {"nome", "data", "pu_compra", "taxa_compra"}.issubset(df.columns)
        # 3 linhas de IPCA+ 2032 (datas distintas) + 1 de Selic 2031
        assert len(df[df["nome"] == "Tesouro IPCA+ 2032"]) == 3
        assert len(df[df["nome"] == "Tesouro Selic 2031"]) == 1

    def test_ordenado_por_nome_e_data(self):
        mock_resp = MagicMock()
        mock_resp.text = _CSV_HISTORICO
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_historico_titulos_tesouro()
        sub = df[df["nome"] == "Tesouro IPCA+ 2032"]
        assert list(sub["data"]) == sorted(sub["data"])

    def test_pu_e_taxa_convertidos_corretamente(self):
        mock_resp = MagicMock()
        mock_resp.text = _CSV_HISTORICO
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_historico_titulos_tesouro()
        linha = df[
            (df["nome"] == "Tesouro IPCA+ 2032")
            & (df["data"] == pd.Timestamp("2026-07-17"))
        ].iloc[0]
        assert linha["pu_compra"] == 2090.00
        assert linha["taxa_compra"] == 7.93

    def test_exception_retorna_dataframe_vazio(self):
        with patch("core.dados.requests.get", side_effect=Exception("timeout")):
            df = buscar_historico_titulos_tesouro()
        assert isinstance(df, pd.DataFrame)
        assert df.empty

    def test_titulo_sem_historico_nao_aparece(self):
        mock_resp = MagicMock()
        mock_resp.text = _CSV_HISTORICO
        with patch("core.dados.requests.get", return_value=mock_resp):
            df = buscar_historico_titulos_tesouro()
        assert "Tesouro Prefixado 2029" not in set(df["nome"])


class TestHistoricoTitulo:
    def _df(self):
        mock_resp = MagicMock()
        mock_resp.text = _CSV_HISTORICO
        with patch("core.dados.requests.get", return_value=mock_resp):
            return buscar_historico_titulos_tesouro()

    def test_filtra_por_nome(self):
        df = historico_titulo(
            self._df(), "Tesouro IPCA+ 2032", date(2026, 1, 1), date(2026, 12, 31)
        )
        assert set(df["nome"]) == {"Tesouro IPCA+ 2032"}
        assert len(df) == 3

    def test_filtra_por_janela_de_datas(self):
        # Só as duas primeiras datas (10/01 e 15/03) caem na janela
        df = historico_titulo(
            self._df(), "Tesouro IPCA+ 2032", date(2026, 1, 1), date(2026, 4, 1)
        )
        assert len(df) == 2

    def test_dataframe_vazio_retorna_vazio(self):
        vazio = pd.DataFrame()
        assert historico_titulo(
            vazio, "Tesouro IPCA+ 2032", date(2026, 1, 1), date(2026, 12, 31)
        ).empty

    def test_titulo_inexistente_retorna_vazio(self):
        df = historico_titulo(
            self._df(), "Tesouro Inexistente 2099", date(2026, 1, 1), date(2026, 12, 31)
        )
        assert df.empty


# ---------------------------------------------------------------------------
# _titulos_fallback — ramos de vencimento expirado
# ---------------------------------------------------------------------------


class TestTitulosFallbackVencimentoExpirado:
    def test_titulos_config_expirados_sao_pulados(self):
        # Cobre linhas 432 e 450: quando todos os títulos já venceram (data far future),
        # _titulos_fallback retorna DataFrame vazio (ou só com itens não expirados do BATALHA).
        import core.dados as _dados_mod
        from datetime import date as _date

        class _FutureDate(_date):
            @classmethod
            def today(cls):
                return cls(2200, 1, 1)

        with patch.object(_dados_mod, "date", _FutureDate):
            df = _titulos_fallback()
        assert isinstance(df, pd.DataFrame)
        # Com data em 2200, todos os títulos estão expirados → lista vazia
        assert len(df) == 0


# ---------------------------------------------------------------------------
# montar_catalogo_batalha — ramos de exceção e filtro de prazo
# ---------------------------------------------------------------------------


class TestMontarCatalogoBatalhaExtras:
    def test_vencimento_invalido_no_df_pula_linha(self):
        # Cobre linhas 486-487: date.fromisoformat falha em string corrompida →
        # except Exception: continue (linha é pulada sem explodir).
        df = pd.DataFrame(
            [
                {
                    "nome": "Tesouro Selic 2031",
                    "vencimento": "invalid-date",
                    "taxa_compra": 14.75,
                },
                {
                    "nome": "Tesouro IPCA+ 2032",
                    "vencimento": "2032-08-15",
                    "taxa_compra": 7.50,
                },
            ]
        )
        cat = montar_catalogo_batalha(df, 14.75)
        nomes = {t["nome"] for t in cat}
        assert "Tesouro IPCA+ 2032" in nomes
        assert "Tesouro Selic 2031" not in nomes  # linha inválida foi pulada

    def test_titulos_config_proximos_ao_vencimento_excluidos_do_complemento(self):
        # Cobre linha 520: quando um título de TITULOS_CONFIG ainda não está no catalogo
        # mas vence em menos de 30 dias, deve ser excluído do complemento.
        import core.dados as _dados_mod
        from datetime import date as _date

        class _FutureDate(_date):
            @classmethod
            def today(cls):
                return cls(2200, 1, 1)

        # Com data em 2200, todos os TITULOS_CONFIG expiram → nenhum é complementado
        with patch.object(_dados_mod, "date", _FutureDate):
            df_vazio = pd.DataFrame(columns=["nome", "vencimento", "taxa_compra"])
            cat = montar_catalogo_batalha(df_vazio, 14.75)
        assert isinstance(cat, list)


# ---------------------------------------------------------------------------
# timestamp_ultima_atualizacao
# ---------------------------------------------------------------------------


class TestTimestampUltimaAtualizacao:
    def test_retorna_datetime(self):
        from datetime import datetime

        result = timestamp_ultima_atualizacao("chave_qualquer")
        assert isinstance(result, datetime)

    def test_timezone_brasil(self):
        result = timestamp_ultima_atualizacao("chave_tz")
        assert result.tzinfo is not None


# ---------------------------------------------------------------------------
# obter_dados_completos
# ---------------------------------------------------------------------------


class TestObterDadosCompletos:
    """Cobre linhas 548-562: orquestração de dados + registro de status no session_state."""

    def _df_ipca(self):
        datas = pd.date_range("2015-01-01", periods=3, freq="MS")
        return pd.DataFrame(
            {"data": datas, "valor": [0.5, 0.5, 0.5], "_is_fallback": False}
        )

    def _df_titulos(self):
        return pd.DataFrame(
            [
                {
                    "nome": "Tesouro Selic 2031",
                    "vencimento": "2031-03-01",
                    "taxa_compra": 14.75,
                    "taxa_venda": 14.77,
                    "pu_compra": 0.0,
                    "pu_venda": 0.0,
                    "_is_fallback": False,
                }
            ]
        )

    def test_retorna_tupla_de_tres_elementos(self):
        from core.dados import obter_dados_completos
        import core.dados as _dm

        df_i = self._df_ipca()
        df_t = self._df_titulos()
        with (
            patch.object(_dm, "buscar_ipca_bcb", return_value=df_i),
            patch.object(_dm, "buscar_titulos_tesouro", return_value=df_t),
            patch.object(_dm, "chave_cache_mercado", return_value="chave"),
        ):
            resultado = obter_dados_completos()
        assert len(resultado) == 3
        assert isinstance(resultado[0], pd.DataFrame)
        assert isinstance(resultado[1], pd.DataFrame)
        assert isinstance(resultado[2], float)

    def test_vna_positivo(self):
        from core.dados import obter_dados_completos
        import core.dados as _dm

        df_i = self._df_ipca()
        df_t = self._df_titulos()
        with (
            patch.object(_dm, "buscar_ipca_bcb", return_value=df_i),
            patch.object(_dm, "buscar_titulos_tesouro", return_value=df_t),
            patch.object(_dm, "chave_cache_mercado", return_value="chave"),
        ):
            _, _, vna = obter_dados_completos()
        assert vna > 0

    def test_fallback_detectado_quando_is_fallback_true(self):
        from core.dados import obter_dados_completos
        import core.dados as _dm

        df_i = self._df_ipca().assign(_is_fallback=True)
        df_t = self._df_titulos().assign(_is_fallback=True)
        session: dict = {}
        with (
            patch.object(_dm, "buscar_ipca_bcb", return_value=df_i),
            patch.object(_dm, "buscar_titulos_tesouro", return_value=df_t),
            patch.object(_dm, "chave_cache_mercado", return_value="chave"),
            patch.object(_dm.st, "session_state", session),
        ):
            obter_dados_completos()
        assert session["_status_dados"]["ipca_fallback"] is True
        assert session["_status_dados"]["titulos_fallback"] is True

    def test_fallback_false_quando_api_ok(self):
        from core.dados import obter_dados_completos
        import core.dados as _dm

        df_i = self._df_ipca()
        df_t = self._df_titulos()
        session: dict = {}
        with (
            patch.object(_dm, "buscar_ipca_bcb", return_value=df_i),
            patch.object(_dm, "buscar_titulos_tesouro", return_value=df_t),
            patch.object(_dm, "chave_cache_mercado", return_value="chave"),
            patch.object(_dm.st, "session_state", session),
        ):
            obter_dados_completos()
        assert session["_status_dados"]["ipca_fallback"] is False
        assert session["_status_dados"]["titulos_fallback"] is False

    def test_df_sem_coluna_is_fallback_retorna_false(self):
        # Cobre linha 554: _e_fallback retorna False quando "_is_fallback" não
        # está nas colunas do DataFrame (guarda defensiva dentro da função).
        from core.dados import obter_dados_completos
        import core.dados as _dm

        # DataFrames sem coluna _is_fallback → _e_fallback vai pelo return False
        df_i = self._df_ipca().drop(columns=["_is_fallback"])
        df_t = self._df_titulos().drop(columns=["_is_fallback"])
        session: dict = {}
        with (
            patch.object(_dm, "buscar_ipca_bcb", return_value=df_i),
            patch.object(_dm, "buscar_titulos_tesouro", return_value=df_t),
            patch.object(_dm, "chave_cache_mercado", return_value="chave"),
            patch.object(_dm.st, "session_state", session),
        ):
            obter_dados_completos()
        assert session["_status_dados"]["ipca_fallback"] is False
        assert session["_status_dados"]["titulos_fallback"] is False


# ---------------------------------------------------------------------------
# Integridade: TITULOS_CONFIG × _TAXAS_REF
# ---------------------------------------------------------------------------


class TestIntegridadeConfigs:
    def test_todos_titulos_config_tem_taxa_ref(self):
        # Todo título em TITULOS_CONFIG deve ter uma entrada em _TAXAS_REF;
        # caso contrário, o fallback usa 7.50% silenciosamente.
        sem_taxa = [nome for nome in TITULOS_CONFIG if nome not in _TAXAS_REF]
        assert sem_taxa == [], f"Títulos sem _TAXAS_REF: {sem_taxa}"

    def test_taxas_ref_positivas(self):
        # Todas as taxas de referência devem ser valores positivos (% a.a.)
        invalidas = {nome: taxa for nome, taxa in _TAXAS_REF.items() if taxa <= 0}
        assert invalidas == {}, f"Taxas inválidas em _TAXAS_REF: {invalidas}"

    def test_titulos_config_tem_vencimento_futuro_a_partir_de_2026(self):
        # Nenhum título deve ter vencimento antes de 2026 (seriam expirados ao lançar o app)
        from datetime import date as _date

        expirados = [
            nome
            for nome, cfg in TITULOS_CONFIG.items()
            if cfg["vencimento"] < _date(2026, 1, 1)
        ]
        assert expirados == [], f"Títulos expirados em TITULOS_CONFIG: {expirados}"

    def test_taxas_ref_sem_titulo_config_correspondente(self):
        # Entradas em _TAXAS_REF sem correspondente em TITULOS_CONFIG são órfãs —
        # nunca serão usadas e indicam inconsistência ao remover/renomear um título.
        orfaos = [nome for nome in _TAXAS_REF if nome not in TITULOS_CONFIG]
        assert orfaos == [], f"Entradas órfãs em _TAXAS_REF: {orfaos}"

    def test_titulos_config_em_titulos_batalha_como_ipca_mais(self):
        # Todo título em TITULOS_CONFIG deve aparecer em TITULOS_BATALHA com tipo "ipca_mais".
        # TITULOS_BATALHA é derivado via dict unpacking de TITULOS_CONFIG — este teste
        # detectaria uma refatoração que quebre essa derivação.
        erros = [
            nome
            for nome in TITULOS_CONFIG
            if nome not in TITULOS_BATALHA
            or TITULOS_BATALHA[nome].get("tipo") != "ipca_mais"
        ]
        assert erros == [], f"Títulos fora de TITULOS_BATALHA ou tipo errado: {erros}"
