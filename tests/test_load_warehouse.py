import tempfile

import duckdb
import pandas as pd

from src.load.warehouse import criar_tabelas, salvar_despesas


def test_salvar_despesas_cria_e_popula_tabela(tmp_path):
    caminho_db = str(tmp_path / "test.duckdb")
    df = pd.DataFrame([
        {"orgao": "Ministerio A", "valor": 1000.0, "ano": 2025, "mes": 6},
    ])

    criar_tabelas(caminho_db)
    salvar_despesas(df, caminho_db)

    con = duckdb.connect(caminho_db)
    resultado = con.execute("SELECT orgao, valor, ano, mes FROM despesas").fetchall()
    con.close()

    assert resultado == [("Ministerio A", 1000.0, 2025, 6)]


def test_salvar_despesas_substitui_periodo_existente_sem_duplicar():
    # essa é a regra de idempotencia: se eu rodar o pipeline duas vezes pro
    # mesmo ano/mes, não pode duplicar linha. tem que substituir o periodo.
    with tempfile.TemporaryDirectory() as tmp:
        caminho_db = f"{tmp}/test.duckdb"
        criar_tabelas(caminho_db)

        primeira_carga = pd.DataFrame([{"orgao": "Ministerio A", "valor": 1000.0, "ano": 2025, "mes": 6}])
        salvar_despesas(primeira_carga, caminho_db)

        segunda_carga = pd.DataFrame([{"orgao": "Ministerio A", "valor": 1500.0, "ano": 2025, "mes": 6}])
        salvar_despesas(segunda_carga, caminho_db)

        con = duckdb.connect(caminho_db)
        resultado = con.execute("SELECT valor FROM despesas WHERE ano=2025 AND mes=6").fetchall()
        con.close()

        assert resultado == [(1500.0,)]
