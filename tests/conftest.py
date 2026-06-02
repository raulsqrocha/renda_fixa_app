import sys
import os
from unittest.mock import MagicMock

# Garante que o diretório raiz do projeto está no path para imports de core.*
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Mock streamlit antes de importar qualquer módulo do projeto.
# Torna @st.cache_data(ttl=...) um decorator no-op em contexto de teste,
# evitando dependência do runtime do Streamlit para testar funções puras.
_st_mock = MagicMock()
_st_mock.cache_data.side_effect = lambda ttl=None, show_spinner=True, **kw: lambda f: f
sys.modules["streamlit"] = _st_mock
