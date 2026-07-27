import json
import os

import responses
from responses import matchers

from src.extract.client import fetch_despesas_por_orgao, salvar_pagina_bruta


@responses.activate
def test_fetch_despesas_por_orgao_stops_on_empty_page():
    # a API não manda um campo "tem_mais_paginas", ela só devolve [] quando acabou
    # simulei isso aqui: página 1 tem 2 itens, página 2 vem vazia
    #
    # descobri rodando contra a API de verdade que ela NÃO aceita filtro de
    # mes nesse endpoint (só ano), e exige um orgaoSuperior (codigo SIAFI)
    # junto - sem isso ela devolve 400 com "Filtros minimos: pagina, ano,
    # ao menos um dos demais filtros". por isso o client pede orgao_superior.
    responses.add(
        responses.GET,
        "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-orgao",
        json=[
            {"ano": 2024, "orgao": "Fundo Nacional de Desenvolvimento da Educacao", "codigoOrgao": "26298",
             "orgaoSuperior": "Ministerio da Educacao", "codigoOrgaoSuperior": "26000",
             "empenhado": "94.588.918.368,01", "liquidado": "77.786.388.029,39", "pago": "77.721.908.268,51"},
            {"ano": 2024, "orgao": "Empresa Brasileira de Servicos Hospitalares", "codigoOrgao": "26443",
             "orgaoSuperior": "Ministerio da Educacao", "codigoOrgaoSuperior": "26000",
             "empenhado": "12.702.804.938,68", "liquidado": "10.281.632.555,28", "pago": "10.147.460.198,79"},
        ],
        status=200,
        match=[matchers.query_param_matcher({"ano": "2024", "orgaoSuperior": "26000", "pagina": "1"})],
    )
    responses.add(
        responses.GET,
        "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-orgao",
        json=[],
        status=200,
        match=[matchers.query_param_matcher({"ano": "2024", "orgaoSuperior": "26000", "pagina": "2"})],
    )

    resultado = fetch_despesas_por_orgao(ano=2024, orgao_superior="26000", token="fake-token")

    assert len(resultado) == 2
    assert resultado[0]["orgao"] == "Fundo Nacional de Desenvolvimento da Educacao"
    assert resultado[0]["pago"] == "77.721.908.268,51"


def test_salvar_pagina_bruta_grava_json(tmp_path):
    dados = [{"orgao": "Ministerio A", "pago": "1000,00"}]

    caminho = salvar_pagina_bruta(dados, ano=2024, orgao_superior="26000", pasta_base=str(tmp_path))

    assert os.path.exists(caminho)
    with open(caminho) as f:
        conteudo = json.load(f)
    assert conteudo == dados
