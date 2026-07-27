import json

import duckdb

from run_pipeline import rodar_periodo


def test_rodar_periodo_com_dados_ja_baixados(tmp_path):
    # aqui eu não bato na API de verdade: simulo que o extract já rodou e
    # salvou o JSON no lugar certo, e testo só transform + load a partir dai.
    # isso evita depender de internet/token pra rodar os testes.
    pasta_raw = tmp_path / "raw" / "2025-06"
    pasta_raw.mkdir(parents=True)
    with open("tests/fixtures/despesas_exemplo.json") as f:
        dados_exemplo = json.load(f)
    with open(pasta_raw / "despesas_por_orgao.json", "w") as f:
        json.dump(dados_exemplo, f)

    caminho_db = str(tmp_path / "warehouse.duckdb")

    rodar_periodo(ano=2025, mes=6, caminho_db=caminho_db, pasta_raw_base=str(tmp_path / "raw"), pular_extracao=True)

    con = duckdb.connect(caminho_db)
    total = con.execute("SELECT COUNT(*) FROM despesas").fetchone()[0]
    con.close()

    assert total == 2
