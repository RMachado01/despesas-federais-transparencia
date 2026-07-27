import json
import os

import responses
from responses import matchers

from src.extract.client import fetch_despesas_por_orgao, salvar_pagina_bruta


@responses.activate
def test_fetch_despesas_por_orgao_stops_on_empty_page():
    # a API não manda um campo "tem_mais_paginas", ela só devolve [] quando acabou
    # simulei isso aqui: página 1 tem 2 itens, página 2 vem vazia
    responses.add(
        responses.GET,
        "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-orgao",
        json=[{"orgao": "Ministerio A", "valor": "1000,00"}, {"orgao": "Ministerio B", "valor": "2000,00"}],
        status=200,
        match=[matchers.query_param_matcher({"ano": "2025", "mes": "6", "pagina": "1"})],
    )
    responses.add(
        responses.GET,
        "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-orgao",
        json=[],
        status=200,
        match=[matchers.query_param_matcher({"ano": "2025", "mes": "6", "pagina": "2"})],
    )

    resultado = fetch_despesas_por_orgao(ano=2025, mes=6, token="fake-token")

    assert len(resultado) == 2
    assert resultado[0]["orgao"] == "Ministerio A"


def test_salvar_pagina_bruta_grava_json(tmp_path):
    dados = [{"orgao": "Ministerio A", "valor": "1000,00"}]

    caminho = salvar_pagina_bruta(dados, ano=2025, mes=6, pasta_base=str(tmp_path))

    assert os.path.exists(caminho)
    with open(caminho) as f:
        conteudo = json.load(f)
    assert conteudo == dados
