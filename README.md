# Analise de Producao Cientifica em Ciencias Sociais

Entrega tecnica para o teste de Business Intelligence com foco em ETL, modelagem SQLite, dashboard interativo em Streamlit, artefatos visuais para submissao e resumo executivo.

## Objetivo

Consolidar a base institucional de periodicos/QUALIS com metadados do SCImago para responder perguntas de negocio sobre qualidade editorial, impacto bibliometrico e benchmark internacional.

## Stack

- Python 3.12
- Pandas
- SQLite
- Streamlit
- Plotly
- SciPy

## Estrutura do projeto

- `scripts/etl.py`: carrega os CSVs, padroniza os campos e materializa o banco SQLite.
- `scripts/analyze.py`: calcula KPIs, correlacoes e insights em `artifacts/analysis_summary.json`.
- `scripts/export_assets.py`: gera exports derivados do dashboard em HTML/PNG/CSV para uso externo.
- `app.py`: dashboard Streamlit com filtros, KPIs, graficos e tabelas.
- `resumo_executivo.md`: sintese executiva dos achados.
- `artifacts/analysis_summary.json`: resumo agregado pronto para consulta rapida.

## Decisoes tecnicas

- A persistencia foi feita em SQLite para manter o projeto simples, portavel e sem dependencia de servidor.
- O ETL normaliza nomes de colunas para ASCII/snake_case, reduzindo ambiguidade entre bases de origens diferentes.
- `ISSN` e tratado como texto e passa por normalizacao para preservar zeros a esquerda e melhorar a taxa de casamento.
- Valores numericos com formato local sao convertidos para tipos numericos com funcoes dedicadas de parsing.
- A base SCImago possui multiplos ISSNs por periodico; por isso o pipeline explode essa lista em `fi2_journal_issn` antes da juncao.
- A camada analitica fica centralizada na view `vw_journal_analysis`, que unifica artigos do programa, metadados SCImago e classificacao geografica (`Brazil`, `International`, `Unmatched`).
- A view `vw_kpis` concentra indicadores resumidos para reutilizacao e simplificacao da aplicacao.
- O dashboard usa `st.cache_data` para evitar releitura desnecessaria do SQLite e melhorar a responsividade.
- As correlacoes usam Spearman porque `QUALIS` e uma escala ordinal, nao intervalar.
- O filtro temporal foi implementado com `coverage_end_year`, pois os insumos nao trazem um ano transacional por artigo.

## Decisoes de publicacao e seguranca

- Dados brutos em `data/raw/` nao sao versionados.
- O banco SQLite gerado localmente nao e publicado.
- Exports derivados de `artifacts/dashboard_assets/` nao sao publicados para evitar expor massa derivada desnecessaria em um repositorio publico.
- O repositório publica codigo, documentacao e o resumo agregado `artifacts/analysis_summary.json`, que nao contem credenciais nem dados operacionais sensiveis.
- Arquivos de ambiente local e possiveis segredos em `.env` e `.streamlit/` ficam fora do versionamento.

## Como executar

1. Coloque os CSVs em `data/raw/` com os nomes abaixo, ou informe os caminhos via linha de comando:

- `data/raw/artigos_fi1.csv`
- `data/raw/artigos_fi2.csv`

2. Crie o ambiente virtual:

```powershell
C:\Users\yurig\AppData\Local\Programs\Python\Python312\python.exe -m venv .venv
```

3. Instale as dependencias:

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

4. Rode o ETL:

```powershell
.\.venv\Scripts\python.exe scripts\etl.py
```

Opcionalmente, com caminhos explicitos:

```powershell
.\.venv\Scripts\python.exe scripts\etl.py --fi1 "C:\caminho\artigos_fi1.csv" --fi2 "C:\caminho\artigos_fi2.csv"
```

5. Gere o resumo analitico:

```powershell
.\.venv\Scripts\python.exe scripts\analyze.py
```

6. Exporte ativos visuais derivados:

```powershell
.\.venv\Scripts\python.exe scripts\export_assets.py
```

7. Inicie o dashboard:

```powershell
.\.venv\Scripts\streamlit.exe run app.py
```

## Perguntas de negocio cobertas

- Como esta distribuida a producao por estrato QUALIS.
- Qual a relacao entre QUALIS, SJR e media de citacoes.
- Como periodicos brasileiros se comparam aos internacionais em SJR, quartil e indice H.
- Quais sao os periodicos com maior SJR dentro do conjunto casado.

## Observacoes metodologicas

- A base `artigos_fi1.csv` contem 22.039 registros; a base `artigos_fi2.csv` contem 7.721 periodicos SCImago.
- A juncao por ISSN encontra apenas parte do universo total, o que e esperado dado o recorte parcial disponivel no SCImago.
- A correlacao `QUALIS x citacoes` usa toda a base do programa; analises com `SJR`, quartil e `H-index` usam apenas o subconjunto casado.
- O casamento por ISSN privilegia rastreabilidade e consistencia, mas nao resolve periodicos sem ISSN valido ou sem correspondencia na base externa.
