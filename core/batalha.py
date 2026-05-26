"""
Funções de portfólio para a tela "Qual Ativo Escolher?".

Separadas de core/financas.py por serem exclusivas da análise de fronteira
eficiente (Markowitz) — não fazem parte da matemática financeira central.
"""

from typing import TypedDict

import numpy as np


class PortfolioAleatorio(TypedDict):
    ret_adv:   float
    ret_neu:   float
    ret_fav:   float
    risco_std: float


class CarteiraMistaResult(TypedDict):
    ret_adv:        float
    ret_neu:        float
    ret_fav:        float
    risco_std:      float
    peso_principal: float
    peso_liquida:   float
    nome_principal: str
    nome_liquida:   str
    tipo_principal: str


def gerar_portfolios_aleatorios(analises: list, n: int = 400, seed: int = 42) -> list[PortfolioAleatorio]:
    """
    Gera n portfólios aleatórios via amostragem Dirichlet (Monte Carlo).
    Usado para plotar a nuvem de pontos da fronteira eficiente de Markowitz.
    """
    k = len(analises)
    if k < 2:
        return []
    rng = np.random.default_rng(seed)
    adv = np.array([a["ret_adv"] for a in analises])
    neu = np.array([a["ret_neu"] for a in analises])
    fav = np.array([a["ret_fav"] for a in analises])
    out: list[PortfolioAleatorio] = []
    for _ in range(n):
        w     = rng.dirichlet(np.ones(k))
        r_adv = float(w @ adv)
        r_neu = float(w @ neu)
        r_fav = float(w @ fav)
        out.append(PortfolioAleatorio(
            ret_adv=r_adv,
            ret_neu=r_neu,
            ret_fav=r_fav,
            risco_std=float(np.std([r_adv, r_neu, r_fav])),
        ))
    return out


def carteira_mista(
    analise_principal: dict,
    analise_liquida: dict,
    peso_principal: float = 0.70,
) -> CarteiraMistaResult:
    """
    Métricas de uma carteira com dois ativos nos três cenários de taxa.

    Retorno combinado = média ponderada dos retornos de cada cenário.
    Risco = desvio-padrão dos três retornos ponderados.
    (Modelo co-movimento: mesmos choques macroeconômicos nos dois ativos.)
    """
    wl = 1.0 - peso_principal

    r_adv = peso_principal * analise_principal["ret_adv"] + wl * analise_liquida["ret_adv"]
    r_neu = peso_principal * analise_principal["ret_neu"] + wl * analise_liquida["ret_neu"]
    r_fav = peso_principal * analise_principal["ret_fav"] + wl * analise_liquida["ret_fav"]
    risco = float(np.std([r_adv, r_neu, r_fav]))

    return CarteiraMistaResult(
        ret_adv=r_adv,
        ret_neu=r_neu,
        ret_fav=r_fav,
        risco_std=risco,
        peso_principal=peso_principal,
        peso_liquida=wl,
        nome_principal=analise_principal["nome"],
        nome_liquida=analise_liquida["nome"],
        tipo_principal=analise_principal["tipo"],
    )
