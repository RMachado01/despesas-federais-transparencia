# Despesas Federais - Portal da Transparencia

Projeto pessoal pra praticar pipeline de dados: pego despesas publicas
federais na API do Portal da Transparencia, arrumo os dados e jogo num
dashboard.

Fiz esse projeto pra ter algo pra mostrar em processo seletivo de Data
Engineer, focando em ter um pipeline que funciona de ponta a ponta com
dado real (não so um notebook bonito com CSV baixado uma vez).

## Como funciona

```text
API do Portal da Transparencia
    -> src/extract   (baixa e salva o JSON cru, por ano + ministerio)
    -> src/transform  (limpa e normaliza)
    -> src/load       (grava no duckdb)
    -> run_pipeline.py (roda tudo isso em sequencia, por ano)
    -> app/streamlit_app.py (dashboard que le do duckdb)
```

Usei DuckDB porque roda embutido (não precisa instalar banco nenhum) e é
rapido pra esse tipo de consulta analitica. Nao usei Airflow nem nada
parecido de proposito - pro tamanho desse projeto, um script python
sequencial com log decente resolve, e um orquestrador ia ser complexidade
sem necessidade.

### Detalhe que só descobri testando com token de verdade

O plano original era puxar despesa mes a mes. Só que o endpoint
`despesas/por-orgao` da API **não tem filtro de mes** - ele só aceita
`ano` (obrigatorio) + `pagina`, e exige informar um `orgaoSuperior`
(codigo SIAFI do ministerio) junto, senão devolve erro 400 dizendo que
falta filtro minimo.

Então o pipeline mudou de granularidade mensal pra anual, e passou a
rodar um loop por uma lista fixa de ministerios (`ORGAOS_SUPERIORES` em
`src/extract/client.py`). No fim ficou melhor pro dashboard - comparação
ano a ano é o que mais se usa em analise de gasto publico mesmo, mes a
mes ia gerar ruido.

A API tambem devolve tres estagios de despesa por registro: `empenhado`,
`liquidado` e `pago`. Uso `pago` como "valor" no dashboard, que é o
numero mais proximo de "dinheiro que realmente saiu do caixa".

## Rodando localmente

1. Clona o repo e instala as dependencias:

   ```bash
   pip install -r requirements.txt
   ```

2. O repo ja vem com um `data/warehouse.duckdb` de exemplo, populado com
   dados reais de 2019 a 2025 pros ministerios configurados, entao da pra
   rodar o dashboard direto:

   ```bash
   streamlit run app/streamlit_app.py
   ```

3. Se quiser atualizar com dados mais recentes (ou outro ano):

   - Cria um token gratuito em <https://api.portaldatransparencia.gov.br/swagger-ui.html>
     (tem um botao de cadastro no canto da pagina, confirma o email e o
     token chega/aparece na area logada)
   - Copia `.env.example` pra `.env` e coloca o token
   - Roda o pipeline pro ano que quiser (da pra passar `--ano` mais de uma vez):

     ```bash
     python run_pipeline.py --ano 2025
     python run_pipeline.py --ano 2020 --ano 2021 --ano 2022
     ```

   - Isso substitui os dados daquele ano no `data/warehouse.duckdb` (roda de
     novo quantas vezes quiser, não duplica).

## Rodando os testes

```bash
pip install -r requirements-dev.txt
pytest -v
```

## O que da pra melhorar

Coisas que ficaram de fora por tempo, mas que eu faria numa v2:

- Puxar a lista de ministerios dinamicamente do endpoint `orgaos-siafi`
  em vez de uma lista fixa no codigo
- Endpoint mais granular (despesas por documento) pra dar pra filtrar por
  favorecido especifico, não so por entidade vinculada
- Deploy automatico do pipeline (hoje o dado do dashboard publicado é um
  snapshot, não atualiza sozinho)
- Mais testes de erro da API (hoje so testei os casos de retry e 4xx puro)
