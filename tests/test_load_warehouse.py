import tempfile

import duckdb
import pandas as pd

from src.load.warehouse import criar_tabelas, salvar_despesas


def test_salvar_despesas_cria_e_popula_tabela(tmp_path):
    caminho_db = str(tmp_path / "test.duckdb")
    df = pd.DataFrame([
        {"orgao": "Ministerio A", "orgao_superior": "Superior A", "valor": 1000.0, "ano": 2024},
    ])

    criar_tabelas(caminho_db)
    salvar_despesas(df, caminho_db)

    con = duckdb.connect(caminho_db)
    resultado = con.execute("SELECT orgao, orgao_superior, valor, ano FROM despesas").fetchall()
    con.close()

    assert resultado == [("Ministerio A", "Superior A", 1000.0, 2024)]


def test_salvar_despesas_substitui_ano_existente_sem_duplicar():
    # essa é a regra de idempotencia: se eu rodar o pipeline duas vezes pro
    # mesmo ano, não pode duplicar linha. tem que substituir o ano inteiro.
    # (a chave de idempotencia é só o ano porque o pipeline sempre busca
    # TODOS os orgaos configurados de uma vez pra um ano)
    with tempfile.TemporaryDirectory() as tmp:
        caminho_db = f"{tmp}/test.duckdb"
        criar_tabelas(caminho_db)

        primeira_carga = pd.DataFrame([{"orgao": "Ministerio A", "orgao_superior": "Superior A", "valor": 1000.0, "ano": 2024}])
        salvar_despesas(primeira_carga, caminho_db)

        segunda_carga = pd.DataFrame([{"orgao": "Ministerio A", "orgao_superior": "Superior A", "valor": 1500.0, "ano": 2024}])
        salvar_despesas(segunda_carga, caminho_db)

        con = duckdb.connect(caminho_db)
        resultado = con.execute("SELECT valor FROM despesas WHERE ano=2024").fetchall()
        con.close()

        assert resultado == [(1500.0,)]
