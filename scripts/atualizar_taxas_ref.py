"""
Atualiza _TAXAS_REF em core/dados.py com as taxas do dia atual.

Uso (a partir da raiz do projeto):
    python scripts/atualizar_taxas_ref.py

O script:
  1. Baixa o CSV do Tesouro Transparente
  2. Extrai as taxas de compra de todos os títulos em TITULOS_CONFIG
  3. Gera o novo bloco _TAXAS_REF com data atualizada
  4. Substitui automaticamente o bloco em core/dados.py
  5. Exibe um diff resumido do que mudou

Requer apenas as dependências do requirements.txt (requests, pandas).
"""

import re
import sys
import os
from datetime import date
from io import StringIO

import requests
import pandas as pd

# ---------------------------------------------------------------------------
# Resolve o caminho raiz do projeto (funciona se rodado de qualquer diretório)
# ---------------------------------------------------------------------------

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, _ROOT)

from core.dados import TITULOS_CONFIG, URL_TESOURO_CSV, construir_nome_titulo  # noqa: E402

DADOS_PY = os.path.join(_ROOT, "core", "dados.py")

# ---------------------------------------------------------------------------
# 1. Busca as taxas atuais
# ---------------------------------------------------------------------------

def buscar_taxas_atuais() -> dict[str, float]:
    print("Buscando CSV do Tesouro Transparente...")
    resp = requests.get(URL_TESOURO_CSV, timeout=30)
    resp.raise_for_status()

    df_raw = pd.read_csv(
        StringIO(resp.text),
        sep=";",
        decimal=",",
        dayfirst=True,
        parse_dates=["Data Vencimento", "Data Base"],
    )
    df_raw.columns = df_raw.columns.str.strip()
    data_ref = df_raw["Data Base"].max()
    df = df_raw[df_raw["Data Base"] == data_ref].copy()
    print(f"  Data de referência: {data_ref.date()}")

    def _f(v) -> float:
        try:
            return float(str(v).replace(",", ".").replace(" ", "")) or 0.0
        except Exception:
            return 0.0

    taxas: dict[str, float] = {}
    for _, row in df.iterrows():
        venc = row["Data Vencimento"]
        if pd.isnull(venc):
            continue
        nome = construir_nome_titulo(str(row["Tipo Titulo"]), venc.year)
        if nome and nome in TITULOS_CONFIG:
            taxa = _f(row.get("Taxa Compra Manha", 0))
            if taxa > 0:
                taxas[nome] = round(taxa, 2)

    print(f"  Taxas encontradas: {len(taxas)} títulos")
    return taxas


# ---------------------------------------------------------------------------
# 2. Completa títulos ausentes no CSV com os valores atuais do código
# ---------------------------------------------------------------------------

def completar_com_existentes(taxas_novas: dict, conteudo_py: str) -> dict:
    """Para títulos não encontrados no CSV (ex: RendA+, Educar+), mantém o valor atual."""
    m = re.search(r"_TAXAS_REF:\s*dict\s*=\s*\{(.+?)\}", conteudo_py, re.DOTALL)
    if not m:
        return taxas_novas

    existentes: dict[str, float] = {}
    for line in m.group(1).splitlines():
        match = re.search(r'"([^"]+)":\s*([\d.]+)', line)
        if match:
            existentes[match.group(1)] = float(match.group(2))

    merged = dict(existentes)
    merged.update(taxas_novas)
    return merged


# ---------------------------------------------------------------------------
# 3. Gera o novo bloco _TAXAS_REF
# ---------------------------------------------------------------------------

def gerar_bloco(taxas: dict[str, float], data_ref: str) -> str:
    linhas = [f"# Taxas de referência para o fallback — extraídas do Tesouro Transparente em {data_ref}"]
    linhas.append("_TAXAS_REF: dict = {")

    grupos = [
        ("IPCA+ Principal",            [k for k in taxas if k.startswith("Tesouro IPCA+") and "Semestrais" not in k]),
        ("IPCA+ Juros Semestrais",      [k for k in taxas if "Semestrais" in k]),
        ("Renda+ Aposentadoria Extra",  [k for k in taxas if "RendA+" in k]),
        ("Educar+",                     [k for k in taxas if "Educar+" in k]),
    ]

    for label, chaves in grupos:
        if not chaves:
            continue
        linhas.append(f"    # {label}")
        for k in sorted(chaves, key=lambda x: (x, taxas[x])):
            linhas.append(f'    "{k}": {taxas[k]},')

    linhas.append("}")
    return "\n".join(linhas)


# ---------------------------------------------------------------------------
# 4. Substitui o bloco em core/dados.py
# ---------------------------------------------------------------------------

PADRAO = re.compile(
    r"# Taxas de refer[eê]ncia para o fallback.*?^_TAXAS_REF:\s*dict\s*=\s*\{.*?^\}",
    re.DOTALL | re.MULTILINE,
)


def aplicar_patch(novo_bloco: str) -> bool:
    with open(DADOS_PY, encoding="utf-8") as f:
        conteudo = f.read()

    if not PADRAO.search(conteudo):
        print("ERRO: padrão _TAXAS_REF não encontrado em core/dados.py.")
        print("       Cole manualmente o bloco abaixo em core/dados.py:\n")
        print(novo_bloco)
        return False

    novo_conteudo = PADRAO.sub(novo_bloco, conteudo)

    with open(DADOS_PY, "w", encoding="utf-8") as f:
        f.write(novo_conteudo)

    return True


# ---------------------------------------------------------------------------
# 5. Diff resumido
# ---------------------------------------------------------------------------

def mostrar_diff(taxas_antigas: dict, taxas_novas: dict) -> None:
    print("\n--- Variações em relação ao fallback anterior ---")
    alterados = 0
    for nome in sorted(taxas_novas):
        novo = taxas_novas[nome]
        antigo = taxas_antigas.get(nome)
        if antigo is None:
            print(f"  + {nome}: {novo:.2f}% (NOVO)")
            alterados += 1
        elif abs(novo - antigo) >= 0.01:
            delta = novo - antigo
            sinal = "+" if delta > 0 else ""
            print(f"  ~ {nome}: {antigo:.2f}% -> {novo:.2f}%  ({sinal}{delta:.2f} pp)")
            alterados += 1
    for nome in sorted(taxas_antigas):
        if nome not in taxas_novas:
            print(f"  - {nome}: {taxas_antigas[nome]:.2f}% (REMOVIDO)")
            alterados += 1
    if alterados == 0:
        print("  Nenhuma variacao relevante (>= 0,01 pp).")
    print(f"\n  Total: {len(taxas_novas)} títulos | {alterados} alterações")


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    try:
        taxas_novas = buscar_taxas_atuais()
    except Exception as e:
        print(f"ERRO ao buscar CSV do Tesouro: {e}")
        sys.exit(1)

    with open(DADOS_PY, encoding="utf-8") as f:
        conteudo_atual = f.read()

    # Extrai taxas antigas para o diff
    taxas_antigas: dict[str, float] = {}
    m = re.search(r"_TAXAS_REF:\s*dict\s*=\s*\{(.+?)\}", conteudo_atual, re.DOTALL)
    if m:
        for line in m.group(1).splitlines():
            match = re.search(r'"([^"]+)":\s*([\d.]+)', line)
            if match:
                taxas_antigas[match.group(1)] = float(match.group(2))

    # Completa com existentes para títulos não publicados no CSV (ex: alguns RendA+/Educar+)
    taxas_finais = completar_com_existentes(taxas_novas, conteudo_atual)

    data_hoje = date.today().strftime("%d/%m/%Y")
    novo_bloco = gerar_bloco(taxas_finais, data_hoje)

    print("\nAplicando patch em core/dados.py...")
    ok = aplicar_patch(novo_bloco)

    if ok:
        mostrar_diff(taxas_antigas, taxas_finais)
        print(f"\ncore/dados.py atualizado com sucesso. ({data_hoje})")
    else:
        sys.exit(1)
