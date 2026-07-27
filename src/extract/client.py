"""
cliente pra API do Portal da Transparencia.

resumo rapido de como a API funciona (levei um tempo pra entender isso lendo
o swagger deles): cada endpoint pagina em blocos de 15 itens, e não tem um
campo "total_de_paginas" ou parecido. o jeito de saber que acabou é pedir a
próxima página e receber uma lista vazia de volta. por isso o loop abaixo é
um while True com break na lista vazia, não um for com range fixo.
"""
import json
import os
import time

import requests

BASE_URL = "https://api.portaldatransparencia.gov.br/api-de-dados"
MAX_TENTATIVAS = 3


def fetch_despesas_por_orgao(ano: int, mes: int, token: str) -> list[dict]:
    """Busca despesas por orgao pra um ano/mes, paginando ate a API parar de devolver coisa."""
    resultados = []
    pagina = 1

    while True:
        pagina_dados = _buscar_pagina(ano, mes, pagina, token)
        if not pagina_dados:
            break
        resultados.extend(pagina_dados)
        pagina += 1

    return resultados


def _buscar_pagina(ano: int, mes: int, pagina: int, token: str) -> list[dict]:
    params = {"ano": ano, "mes": mes, "pagina": pagina}
    headers = {"chave-api-dados": token}

    # a API as vezes devolve 429 (rate limit) ou 5xx quando ta congestionada,
    # aqui é só um retry burro com espera crescente. não é elegante mas resolve.
    ultimo_erro = None
    for tentativa in range(1, MAX_TENTATIVAS + 1):
        resposta = requests.get(f"{BASE_URL}/despesas/por-orgao", params=params, headers=headers, timeout=30)

        if resposta.status_code == 200:
            return resposta.json()

        if resposta.status_code in (429, 500, 502, 503, 504):
            ultimo_erro = f"status {resposta.status_code} na tentativa {tentativa}"
            time.sleep(2 ** tentativa)  # 2s, 4s, 8s
            continue

        # erro 4xx que não é rate limit (token invalido, parametro errado etc) -
        # aqui não adianta tentar de novo, então já explode com uma mensagem clara
        resposta.raise_for_status()

    raise RuntimeError(f"nao consegui buscar pagina {pagina} de {ano}-{mes} depois de {MAX_TENTATIVAS} tentativas: {ultimo_erro}")


def salvar_pagina_bruta(dados: list[dict], ano: int, mes: int, pasta_base: str = "data/raw") -> str:
    """Salva o JSON cru num arquivo, separado por pasta ano-mes.

    isso existe pra gente poder reprocessar o transform sem precisar bater
    na API de novo toda hora (e evitar tomar rate limit à toa enquanto
    debuga o parser).
    """
    pasta = os.path.join(pasta_base, f"{ano:04d}-{mes:02d}")
    os.makedirs(pasta, exist_ok=True)

    caminho = os.path.join(pasta, "despesas_por_orgao.json")
    with open(caminho, "w", encoding="utf-8") as f:
        json.dump(dados, f, ensure_ascii=False, indent=2)

    return caminho
