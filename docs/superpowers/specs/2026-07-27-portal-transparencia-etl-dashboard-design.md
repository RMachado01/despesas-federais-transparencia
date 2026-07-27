# Portal da Transparência ETL + Dashboard — Design

## Objetivo

Projeto de portfólio para vaga de Data Engineer: pipeline ETL que extrai dados de despesas públicas federais da API do Portal da Transparência, transforma em um modelo analítico simples e apresenta em um dashboard Streamlit. Equilíbrio entre engenharia de pipeline sólida e um dashboard apresentável — nenhum dos dois é apenas decorativo.

## Escopo

- Dataset: despesas/gastos públicos federais (execução orçamentária, contratos, empenhos).
- Fonte: API oficial do Portal da Transparência (transparencia.gov.br/api-de-dados), autenticada por token via `.env`.
- Armazenamento: DuckDB local (arquivo único, sem servidor).
- Orquestração: script Python sequencial (`run_pipeline.py`), sem Airflow/Prefect.
- Dashboard: Streamlit, lendo diretamente do DuckDB.
- Deploy: GitHub (código completo) + Streamlit Community Cloud (dashboard público, usando um snapshot do DuckDB commitado no repo).

Fora de escopo: outros datasets (servidores, benefícios sociais), orquestrador dedicado, banco gerenciado em nuvem, autenticação de usuários no dashboard.

## Arquitetura

```
[API Portal da Transparência]
    → src/extract/  (requests, paginação, retry, salva JSON bruto em data/raw/AAAA-MM/)
    → src/transform/ (pandas: limpeza, tipagem, normalização → DataFrames)
    → src/load/      (grava em DuckDB: data/warehouse.duckdb)
    → run_pipeline.py (orquestra extract → transform → load, logging por etapa)
    → app/streamlit_app.py (lê do DuckDB, exibe filtros/KPIs/gráficos)
```

### Componentes

- **`src/extract/client.py`** — cliente HTTP para a API (token em header, paginação via parâmetro `pagina`, retry com backoff em erros 429/5xx). Salva cada página de resposta como JSON bruto em `data/raw/<ano>-<mes>/`, permitindo reprocessar sem nova chamada à API.
- **`src/transform/clean.py`** — lê os JSONs brutos, normaliza valores monetários (string → float), datas (ISO), categorias de órgão/função. Produz um modelo simples: tabela fato `despesas` (data, órgão, favorecido, valor, função) e dimensões leves `orgaos`, `favorecidos`.
- **`src/load/warehouse.py`** — grava as tabelas transformadas no DuckDB. Carga idempotente: cada execução é identificada por período de referência (ano-mês); ao reprocessar um período, os registros antigos daquele período são substituídos, não duplicados.
- **`run_pipeline.py`** — chama extract → transform → load em sequência para um intervalo de datas informado via CLI (ex.: `--ano 2025 --mes 6`). Logging estruturado (nível INFO/ERROR) em `logs/pipeline.log` e no console. Se uma etapa falhar, a execução para e registra o erro — não segue silenciosamente para a etapa seguinte.
- **`app/streamlit_app.py`** — dashboard com:
  - Filtros: período (data início/fim), órgão, faixa de valor.
  - KPIs: total gasto no período, número de registros, ticket médio.
  - Gráficos: série temporal de gastos, ranking de órgãos por valor, distribuição por função de governo.
- **`tests/`** — testes unitários para as regras de `transform` (parsing de valores/datas, casos de dados malformados) e um teste de integração leve rodando o pipeline sobre uma amostra fixa de JSON (sem chamar a API real).

### Fluxo de dados e idempotência

Cada execução do pipeline opera sobre um período (ano-mês) explícito. Isso evita ambiguidade sobre "o que já foi carregado" e torna trivial reprocessar um mês específico se os dados de origem mudarem.

### Tratamento de erros

- Extração: retry com backoff exponencial (máx. 3 tentativas) para erros transitórios (429, 5xx); erros 4xx (exceto 429) abortam com mensagem clara sobre o período afetado.
- Transformação: registros que falham na normalização (ex.: valor não numérico) são logados e descartados individualmente, sem interromper o restante do lote; um resumo de quantos registros foram descartados é logado ao final.
- Carga: falha de escrita no DuckDB aborta a execução do período atual sem corromper períodos já carregados (transação por período).

## Estrutura de diretórios

```
Project/
├── src/
│   ├── extract/client.py
│   ├── transform/clean.py
│   └── load/warehouse.py
├── app/streamlit_app.py
├── data/
│   ├── raw/            # JSON bruto por período (gitignored)
│   └── warehouse.duckdb
├── tests/
├── run_pipeline.py
├── requirements.txt
├── .env.example
├── .gitignore
└── README.md
```

## Deploy

- Repositório público no GitHub com README (arquitetura, como rodar localmente, prints do dashboard).
- Dashboard publicado no Streamlit Community Cloud, apontando para o repo; usa um snapshot do `warehouse.duckdb` commitado (dados já processados de um período de exemplo), já que o Community Cloud não executa pipelines agendados.
- Token da API nunca commitado — apenas `.env.example` como referência; usuário que clonar o repo roda o pipeline com seu próprio token para gerar dados atualizados localmente.

## Testes

- Unitários: regras de limpeza/transformação (valores monetários, datas, categorias, registros malformados).
- Integração leve: pipeline completo rodando sobre uma amostra fixa de JSON (fixture), validando que as tabelas finais no DuckDB têm o formato esperado.
- Sem testes E2E do dashboard nesta fase (fora de escopo para o prazo).
