import json

import duckdb

from run_pipeline import rodar_periodo


def test_rodar_periodo_com_dados_ja_baixados(tmp_path):
    # aqui eu não bato na API de verdade: simulo que o extract já rodou pra
    # 2 dos orgaos configurados (26000 e 36000) e salvou o JSON no lugar
    # certo, e testo só transform + load a partir dai. isso evita depender
    # de internet/token pra rodar os testes.
    #
    # os outros orgaos configurados em ORGAOS_SUPERIORES não tem arquivo
    # raw pra esse ano - o pipeline deve pular eles sem quebrar (util pra
    # reprocessar parcialmente sem precisar rebaixar tudo de novo).
    pasta_raw = tmp_path / "raw" / "2024"
    pasta_raw.mkdir(parents=True)

    with open(pasta_raw / "orgao_26000.json", "w") as f:
        json.dump([{"orgao": "Fundo Nacional de Desenvolvimento da Educacao", "orgaoSuperior": "Ministerio da Educacao", "pago": "150.000,00"}], f)
    with open(pasta_raw / "orgao_36000.json", "w") as f:
        json.dump([{"orgao": "Fundacao Oswaldo Cruz", "orgaoSuperior": "Ministerio da Saude", "pago": "320.500,75"}], f)

    caminho_db = str(tmp_path / "warehouse.duckdb")

    rodar_periodo(ano=2024, caminho_db=caminho_db, pasta_raw_base=str(tmp_path / "raw"), pular_extracao=True)

    con = duckdb.connect(caminho_db)
    total = con.execute("SELECT COUNT(*) FROM despesas").fetchone()[0]
    con.close()

    assert total == 2
