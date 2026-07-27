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
