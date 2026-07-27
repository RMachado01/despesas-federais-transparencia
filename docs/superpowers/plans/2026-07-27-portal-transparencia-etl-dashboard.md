# Portal da Transparência ETL + Dashboard Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build a working ETL pipeline (API → DuckDB) and a Streamlit dashboard for federal government expenditure data from the Portal da Transparência.

**Architecture:** Sequential Python scripts (extract → transform → load) writing to a local DuckDB file, orchestrated by a single CLI entrypoint (`run_pipeline.py`), read by a Streamlit app. No external services beyond the Portal da Transparência API.

**Tech Stack:** Python 3.11+, `requests`, `pandas`, `duckdb`, `streamlit`, `python-dotenv`, `pytest`.

**Writing style constraint (applies to every file in this plan):** Code comments, docstrings, README, and commit messages must read like they were written by a real junior data engineer learning the ropes — plain language, occasional first-person notes on tricky bits (e.g. `# a API retorna valor como string tipo "1.234,56", separei o parse numa função só`), no marketing-speak, no em dashes, no "leveraging"/"robust"/"seamless" buzzwords. Use the humanizer skill's guidance (avoid inflated language, avoid uniform three-item lists, avoid AI-tell vocabulary) when drafting README.md and docstrings.

---

## Task 0: Project Scaffolding

**Files:**
- Create: `requirements.txt`
- Create: `.env.example`
- Create: `.gitignore`
- Create: `data/raw/.gitkeep`
- Create: `src/__init__.py`
- Create: `src/extract/__init__.py`
- Create: `src/transform/__init__.py`
- Create: `src/load/__init__.py`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create directory structure and empty package markers**

```bash
mkdir -p src/extract src/transform src/load app data/raw data/warehouse tests/fixtures
touch src/__init__.py src/extract/__init__.py src/transform/__init__.py src/load/__init__.py tests/__init__.py
touch data/raw/.gitkeep
```

- [ ] **Step 2: Write `requirements.txt`**

```
requests==2.32.3
pandas==2.2.3
duckdb==1.1.3
streamlit==1.40.1
python-dotenv==1.0.1
pytest==8.3.3
```

- [ ] **Step 3: Write `.env.example`**

```
# gerar token gratuito em https://api.portaldatransparencia.gov.br/swagger-ui.html (botao "cadastre-se")
PORTAL_TRANSPARENCIA_TOKEN=coloque_seu_token_aqui
```

- [ ] **Step 4: Write `.gitignore`**

```
.venv/
__pycache__/
*.pyc
.env
data/raw/*
!data/raw/.gitkeep
logs/
.pytest_cache/
```

- [ ] **Step 5: Commit**

```bash
git add requirements.txt .env.example .gitignore src/ tests/ data/raw/.gitkeep
git commit -m "chore: estrutura inicial do projeto"
```

---

## Task 2: Extract — API Client

**Files:**
- Create: `src/extract/client.py`
- Test: `tests/test_extract_client.py`

The Portal da Transparência "despesas por órgão" endpoint is `GET /api-de-dados/despesas/documentos` — but for a manageable first slice we use `GET /api-de-dados/despesas/por-orgao` which returns aggregated spend per órgão for a given year/month and paginates via the `pagina` query param (max 15 results per page, stops when a page comes back empty).

- [ ] **Step 1: Write the failing test**

```python
# tests/test_extract_client.py
import json
import responses  # não temos no requirements ainda, ver step 2b

from src.extract.client import fetch_despesas_por_orgao


@responses.activate
def test_fetch_despesas_por_orgao_stops_on_empty_page():
    # a API não manda um campo "tem_mais_paginas", ela só devolve [] quando acabou
    # simulei isso aqui: página 1 tem 2 itens, página 2 vem vazia
    responses.add(
        responses.GET,
        "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-orgao",
        json=[{"orgao": "Ministerio A", "valor": "1000,00"}, {"orgao": "Ministerio B", "valor": "2000,00"}],
        status=200,
        match=[responses.matchers.query_param_matcher({"ano": "2025", "mes": "6", "pagina": "1"})],
    )
    responses.add(
        responses.GET,
        "https://api.portaldatransparencia.gov.br/api-de-dados/despesas/por-orgao",
        json=[],
        status=200,
        match=[responses.matchers.query_param_matcher({"ano": "2025", "mes": "6", "pagina": "2"})],
    )

    resultado = fetch_despesas_por_orgao(ano=2025, mes=6, token="fake-token")

    assert len(resultado) == 2
    assert resultado[0]["orgao"] == "Ministerio A"
```

- [ ] **Step 2a: Add `responses` to requirements-dev**

Create `requirements-dev.txt`:
```
responses==0.25.3
pytest==8.3.3
```

- [ ] **Step 2b: Install test deps and run test to verify it fails**

```bash
pip install -r requirements.txt -r requirements-dev.txt
pytest tests/test_extract_client.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.extract.client'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/extract/client.py
"""
cliente pra API do Portal da Transparencia.

resumo rapido de como a API funciona (levei um tempo pra entender isso lendo
o swagger deles): cada endpoint pagina em blocos de 15 itens, e não tem um
campo "total_de_paginas" ou parecido. o jeito de saber que acabou é pedir a
próxima página e receber uma lista vazia de volta. por isso o loop abaixo é
um while True com break na lista vazia, não um for com range fixo.
"""
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
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_extract_client.py -v
```
Expected: PASS

- [ ] **Step 5: Add a raw-save helper and its test**

```python
# tests/test_extract_client.py (append to same file)
import os

from src.extract.client import salvar_pagina_bruta


def test_salvar_pagina_bruta_grava_json(tmp_path):
    dados = [{"orgao": "Ministerio A", "valor": "1000,00"}]

    caminho = salvar_pagina_bruta(dados, ano=2025, mes=6, pasta_base=str(tmp_path))

    assert os.path.exists(caminho)
    with open(caminho) as f:
        conteudo = json.load(f)
    assert conteudo == dados
```

```python
# src/extract/client.py (append)
import json
import os


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
```

- [ ] **Step 6: Run full test file**

```bash
pytest tests/test_extract_client.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 7: Commit**

```bash
git add src/extract/client.py tests/test_extract_client.py requirements-dev.txt
git commit -m "feat: cliente da API de despesas por orgao, com paginacao e salvamento de raw"
```

---

## Task 3: Transform — Cleaning and Normalization

**Files:**
- Create: `src/transform/clean.py`
- Test: `tests/test_transform_clean.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_transform_clean.py
import pandas as pd

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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_transform_clean.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.transform.clean'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/transform/clean.py
"""
aqui a gente pega o JSON cru que veio da API e transforma numa tabela
arrumada. a parte mais chata foi o formato de numero: a API devolve valor
em formato brasileiro tipo "1.234,56" (ponto de milhar, virgula decimal),
então tem que inverter isso antes de converter pra float.
"""
import logging

import pandas as pd

logger = logging.getLogger(__name__)


def normalizar_despesas(registros_brutos: list[dict], ano: int, mes: int) -> pd.DataFrame:
    """Limpa a lista de despesas por orgao e devolve um DataFrame pronto pra carga."""
    linhas_ok = []
    descartados = 0

    for registro in registros_brutos:
        valor = _parse_valor_brasileiro(registro.get("valor"))
        orgao = registro.get("orgao")

        if valor is None or not orgao:
            descartados += 1
            continue

        linhas_ok.append({"orgao": orgao, "valor": valor, "ano": ano, "mes": mes})

    if descartados:
        logger.warning("descartei %d registro(s) de %d-%d por dado invalido", descartados, ano, mes)

    return pd.DataFrame(linhas_ok, columns=["orgao", "valor", "ano", "mes"])


def _parse_valor_brasileiro(valor_str) -> float | None:
    """Converte "1.234,56" pra 1234.56. Devolve None se não der pra converter."""
    if not valor_str:
        return None

    try:
        # tira ponto de milhar, troca virgula decimal por ponto
        limpo = str(valor_str).replace(".", "").replace(",", ".")
        return float(limpo)
    except ValueError:
        return None
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_transform_clean.py -v
```
Expected: PASS (3 tests)

- [ ] **Step 5: Commit**

```bash
git add src/transform/clean.py tests/test_transform_clean.py
git commit -m "feat: normalizacao de despesas (parse de valor BR, descarte de registros invalidos)"
```

---

## Task 4: Load — DuckDB Warehouse

**Files:**
- Create: `src/load/warehouse.py`
- Test: `tests/test_load_warehouse.py`

- [ ] **Step 1: Write the failing test**

```python
# tests/test_load_warehouse.py
import duckdb
import pandas as pd

from src.load.warehouse import salvar_despesas, criar_tabelas


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
    import tempfile
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_load_warehouse.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'src.load.warehouse'`

- [ ] **Step 3: Write minimal implementation**

```python
# src/load/warehouse.py
"""
carga no duckdb. a regra que importa aqui é: reprocessar um periodo (ano+mes)
não pode duplicar dado, tem que substituir. por isso o DELETE antes do
INSERT, tudo dentro da mesma transacao pra não ficar num estado quebrado
se der erro no meio.
"""
import duckdb
import pandas as pd


def criar_tabelas(caminho_db: str) -> None:
    con = duckdb.connect(caminho_db)
    con.execute("""
        CREATE TABLE IF NOT EXISTS despesas (
            orgao VARCHAR,
            valor DOUBLE,
            ano INTEGER,
            mes INTEGER
        )
    """)
    con.close()


def salvar_despesas(df: pd.DataFrame, caminho_db: str) -> None:
    """Grava o DataFrame de despesas, substituindo qualquer dado do mesmo ano/mes."""
    if df.empty:
        return

    ano = int(df["ano"].iloc[0])
    mes = int(df["mes"].iloc[0])

    con = duckdb.connect(caminho_db)
    try:
        con.execute("BEGIN TRANSACTION")
        con.execute("DELETE FROM despesas WHERE ano = ? AND mes = ?", [ano, mes])
        con.execute("INSERT INTO despesas SELECT * FROM df")
        con.execute("COMMIT")
    except Exception:
        con.execute("ROLLBACK")
        raise
    finally:
        con.close()
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_load_warehouse.py -v
```
Expected: PASS (2 tests)

- [ ] **Step 5: Commit**

```bash
git add src/load/warehouse.py tests/test_load_warehouse.py
git commit -m "feat: carga idempotente no duckdb (substitui por periodo, sem duplicar)"
```

---

## Task 5: Pipeline Orchestration

**Files:**
- Create: `run_pipeline.py`
- Test: `tests/test_run_pipeline.py`

- [ ] **Step 1: Write the failing integration test (using a fixture, no real API call)**

```python
# tests/fixtures/despesas_exemplo.json
```
```json
[
    {"orgao": "Ministerio da Educacao", "valor": "150.000,00"},
    {"orgao": "Ministerio da Saude", "valor": "320.500,75"}
]
```

```python
# tests/test_run_pipeline.py
import json
import duckdb

from run_pipeline import rodar_periodo


def test_rodar_periodo_com_dados_ja_baixados(tmp_path, monkeypatch):
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
```

- [ ] **Step 2: Run test to verify it fails**

```bash
pytest tests/test_run_pipeline.py -v
```
Expected: FAIL with `ModuleNotFoundError: No module named 'run_pipeline'`

- [ ] **Step 3: Write minimal implementation**

```python
# run_pipeline.py
"""
ponto de entrada do pipeline. roda extract -> transform -> load pra um
ano/mes especifico.

uso:
    python run_pipeline.py --ano 2025 --mes 6

fiz assim (ano+mes obrigatorios, sem "rodar tudo") porque a API cobre
bastante historico e eu não queria puxar tudo de uma vez enquanto ainda
to testando o pipeline. dá pra rodar mes a mes e ir acumulando no duckdb.
"""
import argparse
import json
import logging
import os

from dotenv import load_dotenv

from src.extract.client import fetch_despesas_por_orgao, salvar_pagina_bruta
from src.transform.clean import normalizar_despesas
from src.load.warehouse import criar_tabelas, salvar_despesas

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(name)s: %(message)s",
    handlers=[logging.StreamHandler(), logging.FileHandler("logs/pipeline.log")] if os.path.isdir("logs") else [logging.StreamHandler()],
)
logger = logging.getLogger(__name__)

CAMINHO_DB_PADRAO = "data/warehouse.duckdb"


def rodar_periodo(ano: int, mes: int, caminho_db: str = CAMINHO_DB_PADRAO, pasta_raw_base: str = "data/raw", pular_extracao: bool = False) -> None:
    """Roda o pipeline completo pra um periodo. pular_extracao existe so pra facilitar teste/reprocessamento local."""
    logger.info("iniciando pipeline pra %d-%02d (pular_extracao=%s)", ano, mes, pular_extracao)

    if not pular_extracao:
        logger.info("extraindo dados da API...")
        token = os.environ.get("PORTAL_TRANSPARENCIA_TOKEN")
        if not token:
            raise RuntimeError("faltou configurar PORTAL_TRANSPARENCIA_TOKEN no .env")
        dados_brutos = fetch_despesas_por_orgao(ano=ano, mes=mes, token=token)
        salvar_pagina_bruta(dados_brutos, ano=ano, mes=mes, pasta_base=pasta_raw_base)
    else:
        caminho_raw = os.path.join(pasta_raw_base, f"{ano:04d}-{mes:02d}", "despesas_por_orgao.json")
        with open(caminho_raw, encoding="utf-8") as f:
            dados_brutos = json.load(f)

    logger.info("transformando %d registros brutos...", len(dados_brutos))
    df_limpo = normalizar_despesas(dados_brutos, ano=ano, mes=mes)

    logger.info("carregando %d registros no duckdb...", len(df_limpo))
    criar_tabelas(caminho_db)
    salvar_despesas(df_limpo, caminho_db)

    logger.info("pipeline concluido pra %d-%02d", ano, mes)


if __name__ == "__main__":
    load_dotenv()

    parser = argparse.ArgumentParser(description="Roda o pipeline de despesas do Portal da Transparencia pra um ano/mes")
    parser.add_argument("--ano", type=int, required=True)
    parser.add_argument("--mes", type=int, required=True)
    args = parser.parse_args()

    rodar_periodo(ano=args.ano, mes=args.mes)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
pytest tests/test_run_pipeline.py -v
```
Expected: PASS

- [ ] **Step 5: Run full test suite to confirm nothing broke**

```bash
pytest -v
```
Expected: all tests PASS

- [ ] **Step 6: Commit**

```bash
git add run_pipeline.py tests/test_run_pipeline.py tests/fixtures/
git commit -m "feat: orquestracao do pipeline (extract -> transform -> load) via CLI"
```

---

## Task 6: Seed Sample Data for the Dashboard

Since the API needs a personal token that isn't available in this environment, we generate a realistic local dataset by writing raw JSON fixtures for a few months and running the pipeline against them with `pular_extracao=True`. This gives the dashboard real data to show without requiring the token at plan-execution time; the README explains how to swap in real API data later.

**Files:**
- Create: `scripts/gerar_dados_exemplo.py`
- Create: `data/raw/2025-01/despesas_por_orgao.json` through `data/raw/2025-06/despesas_por_orgao.json` (generated, not hand-written)

- [ ] **Step 1: Write a small generator script (no test needed, it's a one-off dev utility)**

```python
# scripts/gerar_dados_exemplo.py
"""
script pra gerar uns dados de exemplo realistas, só pra dar pra rodar o
dashboard localmente sem precisar de token da API agora. não é parte do
pipeline "de verdade", é só pra popular o warehouse.duckdb de demonstracao.

rodar: python scripts/gerar_dados_exemplo.py
"""
import json
import os
import random

ORGAOS = [
    "Ministerio da Educacao",
    "Ministerio da Saude",
    "Ministerio da Defesa",
    "Ministerio da Infraestrutura",
    "Ministerio do Desenvolvimento Social",
    "Ministerio da Agricultura",
    "Ministerio da Justica e Seguranca Publica",
    "Ministerio da Ciencia e Tecnologia",
]

random.seed(42)  # fixo pra dar sempre o mesmo resultado, facilita conferir

for mes in range(1, 7):
    pasta = f"data/raw/2025-{mes:02d}"
    os.makedirs(pasta, exist_ok=True)

    despesas = []
    for orgao in ORGAOS:
        valor = random.uniform(500_000, 15_000_000)
        valor_formatado = f"{valor:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        despesas.append({"orgao": orgao, "valor": valor_formatado})

    with open(f"{pasta}/despesas_por_orgao.json", "w", encoding="utf-8") as f:
        json.dump(despesas, f, ensure_ascii=False, indent=2)

    print(f"gerado {pasta}/despesas_por_orgao.json com {len(despesas)} orgaos")
```

- [ ] **Step 2: Run the generator**

```bash
python scripts/gerar_dados_exemplo.py
```
Expected: prints 6 lines, one per month, and creates `data/raw/2025-01` through `data/raw/2025-06`.

- [ ] **Step 3: Load all 6 months into the warehouse**

```bash
python -c "
from run_pipeline import rodar_periodo
for mes in range(1, 7):
    rodar_periodo(ano=2025, mes=mes, pular_extracao=True)
"
```
Expected: log lines showing each month completing, ends with `data/warehouse.duckdb` containing 48 rows (8 órgãos × 6 meses).

- [ ] **Step 4: Verify row count**

```bash
python -c "import duckdb; print(duckdb.connect('data/warehouse.duckdb').execute('SELECT COUNT(*) FROM despesas').fetchone())"
```
Expected: `(48,)`

- [ ] **Step 5: Commit (note: `data/raw/*` is gitignored per Task 0, but the warehouse snapshot is not — we want it in the repo for the Streamlit Cloud deploy)**

```bash
git add scripts/gerar_dados_exemplo.py
git add -f data/warehouse.duckdb
git commit -m "chore: script de dados de exemplo + snapshot do warehouse pra demo"
```

---

## Task 7: Streamlit Dashboard

**Files:**
- Create: `app/streamlit_app.py`

No automated test for this task — Streamlit apps are best verified by running them. Manual verification steps are included instead.

- [ ] **Step 1: Write the dashboard**

```python
# app/streamlit_app.py
"""
dashboard de despesas publicas federais. le direto do duckdb, sem
cache complicado por enquanto - o volume de dados é pequeno o suficiente
pra não precisar.
"""
import duckdb
import pandas as pd
import streamlit as st

CAMINHO_DB = "data/warehouse.duckdb"

st.set_page_config(page_title="Despesas Federais - Portal da Transparencia", layout="wide")


@st.cache_resource
def conectar():
    return duckdb.connect(CAMINHO_DB, read_only=True)


def carregar_despesas(con) -> pd.DataFrame:
    return con.execute("SELECT orgao, valor, ano, mes FROM despesas ORDER BY ano, mes").df()


con = conectar()
df = carregar_despesas(con)

st.title("Despesas publicas federais")
st.caption("Dados de exemplo gerados localmente. Pra usar dados reais, rode run_pipeline.py com um token da API (ver README).")

# --- filtros ---
col_filtro1, col_filtro2 = st.columns(2)
with col_filtro1:
    orgaos_selecionados = st.multiselect("Orgao", options=sorted(df["orgao"].unique()), default=None)
with col_filtro2:
    meses_selecionados = st.multiselect("Mes", options=sorted(df["mes"].unique()), default=None)

df_filtrado = df.copy()
if orgaos_selecionados:
    df_filtrado = df_filtrado[df_filtrado["orgao"].isin(orgaos_selecionados)]
if meses_selecionados:
    df_filtrado = df_filtrado[df_filtrado["mes"].isin(meses_selecionados)]

# --- KPIs ---
col1, col2, col3 = st.columns(3)
col1.metric("Total gasto", f"R$ {df_filtrado['valor'].sum():,.2f}")
col2.metric("Numero de registros", len(df_filtrado))
media = df_filtrado["valor"].mean() if len(df_filtrado) else 0
col3.metric("Valor medio por registro", f"R$ {media:,.2f}")

# --- serie temporal ---
st.subheader("Gasto por mes")
serie = df_filtrado.groupby("mes")["valor"].sum().reset_index()
st.line_chart(serie, x="mes", y="valor")

# --- ranking por orgao ---
st.subheader("Ranking por orgao")
ranking = df_filtrado.groupby("orgao")["valor"].sum().sort_values(ascending=False).reset_index()
st.bar_chart(ranking, x="orgao", y="valor")

# --- tabela crua, pra quem quiser conferir os numeros ---
with st.expander("Ver dados brutos"):
    st.dataframe(df_filtrado)
```

- [ ] **Step 2: Run it locally and eyeball the result**

```bash
streamlit run app/streamlit_app.py
```
Expected: browser opens at localhost:8501, shows title, filters, 3 KPI tiles with non-zero values, a line chart with 6 points, and a bar chart with 8 bars.

- [ ] **Step 3: Commit**

```bash
git add app/streamlit_app.py
git commit -m "feat: dashboard streamlit com filtros, kpis e graficos"
```

---

## Task 8: README

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write the README**

```markdown
# Despesas Federais - Portal da Transparencia

Projeto pessoal pra praticar pipeline de dados: pego despesas publicas
federais na API do Portal da Transparencia, arrumo os dados e jogo num
dashboard.

Fiz esse projeto pra ter algo pra mostrar em processo seletivo de Data
Engineer, focando em ter um pipeline que funciona de ponta a ponta (não so
um notebook bonito).

## Como funciona

```
API do Portal da Transparencia
    -> src/extract   (baixa e salva o JSON cru)
    -> src/transform  (limpa e normaliza)
    -> src/load       (grava no duckdb)
    -> run_pipeline.py (roda tudo isso em sequencia, por ano/mes)
    -> app/streamlit_app.py (dashboard que le do duckdb)
```

Usei DuckDB porque roda embutido (não precisa instalar banco nenhum) e é
rapido pra esse tipo de consulta analitica. Nao usei Airflow nem nada
parecido de proposito - pro tamanho desse projeto, um script python
sequencial com log decente resolve, e um orquestrador ia ser complexidade
sem necessidade.

## Rodando localmente

1. Clona o repo e instala as dependencias:

   ```bash
   pip install -r requirements.txt
   ```

2. O repo ja vem com um `data/warehouse.duckdb` de exemplo (dados gerados
   sinteticamente, ver `scripts/gerar_dados_exemplo.py`), entao da pra
   rodar o dashboard direto:

   ```bash
   streamlit run app/streamlit_app.py
   ```

3. Se quiser dados reais da API:

   - Cria um token gratuito em https://api.portaldatransparencia.gov.br/swagger-ui.html
   - Copia `.env.example` pra `.env` e coloca o token
   - Roda o pipeline pro periodo que quiser:

     ```bash
     python run_pipeline.py --ano 2025 --mes 6
     ```

   - Isso substitui os dados daquele mes no `data/warehouse.duckdb` (roda de
     novo quantas vezes quiser, não duplica).

## Rodando os testes

```bash
pip install -r requirements-dev.txt
pytest -v
```

## O que da pra melhorar

Coisas que ficaram de fora por tempo, mas que eu faria numa v2:

- Endpoint mais granular (despesas por documento, não so agregado por
  orgao) pra dar pra filtrar por favorecido
- Deploy automatico do pipeline (hoje o dado do dashboard publicado é um
  snapshot, não atualiza sozinho)
- Mais testes de erro da API (hoje so testei os casos de retry e 4xx puro)
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: readme com explicacao do projeto e como rodar"
```

---

## Task 9: Final Verification

- [ ] **Step 1: Run the full test suite one more time**

```bash
pytest -v
```
Expected: all tests pass, no warnings about missing modules.

- [ ] **Step 2: Confirm the dashboard still runs against the committed snapshot**

```bash
streamlit run app/streamlit_app.py
```
Expected: same as Task 7 Step 2.

- [ ] **Step 3: Check git log reads like a normal commit history**

```bash
git log --oneline
```
Expected: sequence of small, descriptive commits from Task 0 through Task 8, no giant single commit.
