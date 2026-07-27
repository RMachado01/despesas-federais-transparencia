from src.transform.clean import normalizar_despesas


def test_normalizar_despesas_converte_valor_brasileiro_pra_float():
    bruto = [
        {"orgao": "Ministerio A", "valor": "1.234,56"},
        {"orgao": "Ministerio B", "valor": "500,00"},
    ]

    df = normalizar_despesas(bruto, ano=2025, mes=6)

    assert df.loc[0, "valor"] == 1234.56
    assert df.loc[1, "valor"] == 500.00


def test_normalizar_despesas_adiciona_periodo():
    bruto = [{"orgao": "Ministerio A", "valor": "100,00"}]

    df = normalizar_despesas(bruto, ano=2025, mes=6)

    assert df.loc[0, "ano"] == 2025
    assert df.loc[0, "mes"] == 6


def test_normalizar_despesas_descarta_registro_com_valor_invalido():
    # já vi isso acontecer nos dados reais: de vez em quando vem um valor
    # vazio ou "null" como string. em vez de quebrar o pipeline inteiro,
    # a gente ignora esse registro e loga o motivo
    bruto = [
        {"orgao": "Ministerio A", "valor": "100,00"},
        {"orgao": "Ministerio B", "valor": ""},
    ]

    df = normalizar_despesas(bruto, ano=2025, mes=6)

    assert len(df) == 1
    assert df.loc[0, "orgao"] == "Ministerio A"
