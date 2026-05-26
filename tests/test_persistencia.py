"""
Testes unitários para core/persistencia.py.

Cobre:
  - carregar  : retorna defaults quando não há arquivo; lê e mescla JSON salvo;
                recupera de JSON corrompido; sanitiza campos lista e índice inteiro
  - salvar    : grava JSON em disco; é no-op em cloud; mescla com estado existente
  - inicializar_session : injeta valores em session_state; respeita chaves já
                          definidas; ignora None; converte datas ISO
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import core.persistencia as persistencia
from core.persistencia import (
    carregar,
    inicializar_session,
    salvar,
    _default_prefs,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _patch(tmp_file: Path, is_cloud: bool = False):
    """Context manager que substitui _PREFS_FILE e _IS_CLOUD no módulo."""
    return (
        patch.object(persistencia, "_PREFS_FILE", tmp_file),
        patch.object(persistencia, "_IS_CLOUD", is_cloud),
    )


# ---------------------------------------------------------------------------
# _default_prefs
# ---------------------------------------------------------------------------

class TestDefaultPrefs:
    def test_contem_portfolio(self):
        assert "_portfolio" in _default_prefs()

    def test_portfolio_lista_vazia(self):
        assert _default_prefs()["_portfolio"] == []

    def test_analysis_pos_idx_zero(self):
        assert _default_prefs()["_analysis_pos_idx"] == 0

    def test_nao_compartilha_estado_entre_chamadas(self):
        d1 = _default_prefs()
        d2 = _default_prefs()
        d1["_portfolio"].append("x")
        assert d2["_portfolio"] == []


# ---------------------------------------------------------------------------
# carregar
# ---------------------------------------------------------------------------

class TestCarregar:
    def test_sem_arquivo_retorna_defaults(self, tmp_path):
        arquivo = tmp_path / "nao_existe.json"
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            res = carregar()
        assert res == _default_prefs()

    def test_cloud_retorna_defaults_sem_ler_arquivo(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        arquivo.write_text(json.dumps({"port_valor": 99_000.0}), encoding="utf-8")
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", True):
            res = carregar()
        assert res["port_valor"] == _default_prefs()["port_valor"]

    def test_arquivo_valido_mesclado_com_defaults(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        arquivo.write_text(json.dumps({"port_valor": 25_000.0}), encoding="utf-8")
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            res = carregar()
        assert res["port_valor"] == 25_000.0
        # Chaves não salvas ainda têm o default
        assert res["sim_prazo_saida"] == _default_prefs()["sim_prazo_saida"]

    def test_json_corrompido_retorna_defaults(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        arquivo.write_text("{ isso nao e json valido }", encoding="utf-8")
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            res = carregar()
        assert res == _default_prefs()

    def test_campo_lista_corrompido_resetado(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        # _portfolio deveria ser lista, mas foi salvo como string
        arquivo.write_text(json.dumps({"_portfolio": "corrompido"}), encoding="utf-8")
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            res = carregar()
        assert res["_portfolio"] == []

    def test_analysis_pos_idx_nao_int_resetado(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        arquivo.write_text(json.dumps({"_analysis_pos_idx": "errado"}), encoding="utf-8")
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            res = carregar()
        assert res["_analysis_pos_idx"] == 0


# ---------------------------------------------------------------------------
# salvar
# ---------------------------------------------------------------------------

class TestSalvar:
    def test_escreve_json_em_disco(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            salvar({"port_valor": 30_000.0})
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        assert dados["port_valor"] == 30_000.0

    def test_cloud_nao_escreve(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", True):
            salvar({"port_valor": 30_000.0})
        assert not arquivo.exists()

    def test_mescla_com_existente(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        # Estado inicial com sim_prazo_saida
        arquivo.write_text(json.dumps({"sim_prazo_saida": 7}), encoding="utf-8")
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            salvar({"port_valor": 20_000.0})
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        assert dados["sim_prazo_saida"] == 7
        assert dados["port_valor"] == 20_000.0

    def test_date_serializada_como_iso(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            salvar({"port_data": date(2024, 6, 15)})
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        assert dados["port_data"] == "2024-06-15"

    def test_sobrescreve_chave_existente(self, tmp_path):
        arquivo = tmp_path / "prefs.json"
        arquivo.write_text(json.dumps({"port_valor": 5_000.0}), encoding="utf-8")
        with patch.object(persistencia, "_PREFS_FILE", arquivo), \
             patch.object(persistencia, "_IS_CLOUD", False):
            salvar({"port_valor": 15_000.0})
        dados = json.loads(arquivo.read_text(encoding="utf-8"))
        assert dados["port_valor"] == 15_000.0

    def test_excecao_na_escrita_e_silenciada(self):
        # Cobre linhas 136-137: quando open() lança exceção, salvar ignora silenciosamente.
        mock_path = MagicMock(spec=Path)
        mock_path.exists.return_value = False
        mock_path.open.side_effect = PermissionError("sem permissão")
        with patch.object(persistencia, "_PREFS_FILE", mock_path), \
             patch.object(persistencia, "_IS_CLOUD", False):
            salvar({"port_valor": 10_000.0})  # não deve lançar exceção


# ---------------------------------------------------------------------------
# inicializar_session
# ---------------------------------------------------------------------------

class TestInicializarSession:
    def _run(self, prefs: dict, state: dict | None = None) -> dict:
        """Executa inicializar_session com um dict real como session_state."""
        session = {} if state is None else dict(state)
        with patch.object(persistencia.st, "session_state", session):
            inicializar_session(prefs)
        return session

    def test_injeta_chave_nova(self):
        state = self._run({"port_valor": 10_000.0})
        assert state["port_valor"] == 10_000.0

    def test_nao_sobrescreve_chave_existente(self):
        state = self._run({"port_valor": 10_000.0}, state={"port_valor": 999.0})
        assert state["port_valor"] == 999.0

    def test_ignora_none(self):
        state = self._run({"port_cat": None})
        assert "port_cat" not in state

    def test_converte_data_iso(self):
        state = self._run({"port_data": "2024-03-15"})
        assert state["port_data"] == date(2024, 3, 15)

    def test_data_corrompida_nao_injeta(self):
        state = self._run({"port_data": "nao-e-data"})
        assert "port_data" not in state

    def test_multiplas_chaves(self):
        state = self._run({"port_valor": 5_000.0, "sim_prazo_saida": 4})
        assert state["port_valor"] == 5_000.0
        assert state["sim_prazo_saida"] == 4

    def test_chave_nao_data_nao_convertida(self):
        # Strings normais não sofrem conversão
        state = self._run({"bat_perfil": "Conservador"})
        assert state["bat_perfil"] == "Conservador"
