# Pacote de normalização CSV

O pacote `normalization` separa o processamento conservador de CSV por
responsabilidade. O ponto de entrada compatível continua sendo
`database/normalize_csv_review.py`; a implementação fica nestes módulos:

| Módulo | Responsabilidade |
|---|---|
| [`contracts.py`](./contracts.py) | Validar contratos JSON, reconhecer formatos de data e ler CSV sem descartar células ou linhas. |
| [`field_rules.py`](./field_rules.py) | Aplicar normalizações determinísticas de campo, como categorias, números, datas e CID. |
| [`entry_validation.py`](./entry_validation.py) | Detectar inconsistências entre campos, duplicatas potenciais e classificar registros para revisão. |
| [`gemini_review.py`](./gemini_review.py) | Montar pedidos e validar respostas do Gemini; no modo offline, registrar que não houve chamada externa. |
| [`cli.py`](./cli.py) | Coordenar a execução, validar caminhos e gravar o CSV alternativo e a auditoria JSONL. |

## Fluxo

1. `cli.py` carrega o contrato e chama `contracts.py` para ler a origem.
2. `entry_validation.py` aplica as regras de `field_rules.py` e preserva todas
   as linhas, marcando as que precisam de revisão.
3. `gemini_review.py` só é usado para registros com problemas. A opção
   `--offline` impede o carregamento de credenciais e qualquer chamada de rede.
   A resposta do modelo é uma recomendação de auditoria, não altera os valores.
4. `cli.py` grava um CSV alternativo e um arquivo `.audit.jsonl`, recusando
   sobrescrever os arquivos de saída existentes.

## Executar

```powershell
python database\normalize_csv_review.py `
  --contract database\contracts\fila_cirurgica.json `
  --input dataset\fila_cirurgica.csv `
  --output database\dataset_normalizado\fila_cirurgica.csv `
  --offline
```

Para gerar as cópias das quatro tabelas e construir um SQLite separado, use o
orquestrador [run_ingestion.py](../run_ingestion.py). Ele executa o normalizador
em modo offline.

Os módulos de implementação têm entre 150 e 300 linhas. `__init__.py` é apenas
o marcador do pacote, e `normalize_csv_review.py` é uma fachada curta para
manter imports e comandos existentes sem duplicar a implementação.

## Testes

```powershell
python tests\test_normalize_csv_review.py
```

Os testes usam entradas sintéticas e clientes simulados; não enviam dados reais
ao Gemini.
