from src.transform.clean import normalizar_despesas


def test_normalizar_despesas_converte_valor_brasileiro_pra_float():
    # a API devolve o campo "pago" (valor efetivamente pago) em formato
    # brasileiro, tipo "1.234,56". uso "pago" como "valor" porque é o
    # numero mais proximo de "quanto foi gasto de verdade" - empenhado e
    # liquidado são estagios anteriores do processo de despesa
    bruto = [
        {"orgao": "Ministerio A", "orgaoSuperior": "Superior A", "pago": "1.234,56"},
        {"orgao": "Ministerio B", "orgaoSuperior": "Superior A", "pago": "500,00"},
    ]

    df = normalizar_despesas(bruto, ano=2024)

    assert df.loc[0, "valor"] == 1234.56
    assert df.loc[1, "valor"] == 500.00


def test_normalizar_despesas_mantem_orgao_e_orgao_superior():
    # guardamos os dois niveis: "orgao" é a entidade vinculada (ex: uma
    # universidade federal) e "orgao_superior" é o ministerio dela. o
    # dashboard usa orgao_superior pra comparacao no topo (só 8 categorias)
    # e orgao pra drill-down
    bruto = [{"orgao": "Universidade Federal X", "orgaoSuperior": "Ministerio da Educacao", "pago": "100,00"}]

    df = normalizar_despesas(bruto, ano=2024)

    assert df.loc[0, "orgao"] == "Universidade Federal X"
    assert df.loc[0, "orgao_superior"] == "Ministerio da Educacao"
    assert df.loc[0, "ano"] == 2024


def test_normalizar_despesas_descarta_registro_com_valor_invalido():
    # já vi isso acontecer nos dados reais: de vez em quando vem um valor
    # vazio ou "null" como string. em vez de quebrar o pipeline inteiro,
    # a gente ignora esse registro e loga o motivo
    bruto = [
        {"orgao": "Ministerio A", "orgaoSuperior": "Superior A", "pago": "100,00"},
        {"orgao": "Ministerio B", "orgaoSuperior": "Superior A", "pago": ""},
    ]

    df = normalizar_despesas(bruto, ano=2024)

    assert len(df) == 1
    assert df.loc[0, "orgao"] == "Ministerio A"
