# Backend

```
simulador ──HTTP──> api/ ──> servico/ ──> extracao/ + motor/
                                 │
                                 └── portas ◄── infra/ (SQLAlchemy → database/sistema.sqlite3)
```

| Pasta | O que é |
|---|---|
| `extracao/` | dado bruto → achados (regras + LLM opcional) |
| `motor/` | achados → classe SWALIS, scores, sugestões, ordem da fila (ver `motor/README.md`) |
| `servico/` | casos de uso e regras de negócio; depende só de `motor`, `extracao` e das **portas** (`servico/portas.py`) |
| `infra/` | implementação SQLAlchemy das portas, relógio da simulação e redator da justificativa |
| `api/` | FastAPI fina (sem regra de negócio); `api/dependencias.py` é o único lugar que liga serviço e infra |
| `scripts/replay_servico.py` | replay do dataset inteiro pelo serviço (faz o papel do simulador, em processo) |

## Rodar

Da raiz do repositório:

```bash
uv venv --python 3.14 .venv
uv pip install --python .venv -r requirements.txt
cd backend
../.venv/Scripts/python -m infra.db                  # cria database/sistema.sqlite3 vazio (só se não existir)
../.venv/Scripts/python -m uvicorn api.main:app --reload
```

Documentação interativa em `http://localhost:8000/docs`.

| Variável | Padrão | Para quê |
|---|---|---|
| `ORDO_DB_URL` | `sqlite:///…/database/sistema.sqlite3` | banco do sistema |
| `ORDO_PROCEDIMENTOS` | `procedimentos.csv` da raiz | catálogo (procedimento → risco cirúrgico) |
| `ORDO_REDATOR=llm` | template | justificativa reescrita por LLM (precisa de `GEMINI_KEY`; falhou → template) |
| `ORDO_CORS` | `http://localhost:5173` | origens do front, separadas por vírgula |

## Rotas

| Método | Rota | Caso de uso |
|---|---|---|
| POST | `/integracao/solicitacoes` `{dados, respostaLlm?}` | 201 · `receber_solicitacao` |
| POST | `/integracao/eventos` `{dados, respostaLlm?}` | 201 · `receber_evento` |
| GET | `/simulacao` | relógio e aprovação automática |
| PATCH | `/simulacao` `{autoAprovar?, hoje?, modo?}` | avança até `hoje` (`passo`: dia a dia com foto; `rapido`: aprovação automática) |
| DELETE | `/simulacao` | 204 · zera o banco (só com `SIMULADOR=1`) |
| GET | `/fila?data=&limite=&offset=` | fila viva ou foto de um dia, paginada |
| GET | `/fila/dias?de=&ate=&limite=` | fotos de até 31 dias (player), `limite` posições por dia |
| GET | `/fila.csv` | `fila_priorizada.csv` (entregável) |
| GET | `/solicitacoes/{sid}` | ficha: dados, achados com evidência, histórico, sugestões |
| GET | `/sugestoes?status=&limite=&offset=` | paginada; pendentes com prévia de posição e justificativa comparativa |
| GET | `/sugestoes/{id}` | uma sugestão |
| PATCH | `/sugestoes/{id}` `{status: aprovada\|rejeitada, comentario?}` | rejeitar exige comentário; decidir 2x → 409 |
| GET | `/alertas?tipo=&limite=&offset=` | paginada: HbA1c, perda de contato, dados insuficientes, sem ASA, crítico, prazo estourado |

Toda coleção é paginada (`limite` padrão 50, máximo 200) e volta como `{itens, total, limite, offset}`.

JSON em camelCase. Erros: 404 (não encontrado), 409 (transição inválida), 422 (comentário obrigatório / entrada inválida).

## Testes

```bash
cd backend
../.venv/Scripts/python -m unittest discover -s tests -t .              # ~1 s
ORDO_E2E=1 ../.venv/Scripts/python -m unittest tests.test_ponta_a_ponta  # ~45 s: replay + verificador oficial
```

- `test_servico.py`: uma regra de negócio por teste, com repositórios em memória (`tests/fakes.py`).
- `test_infra.py`: **teste de contrato** — a mesma bateria roda contra os fakes e contra o SQLite.
- `test_api.py`: rotas, camelCase e status HTTP, com `TestClient`.
- `test_ponta_a_ponta.py`: dataset inteiro pelo serviço → CSV → `verificar_fila_priorizada.py`.

## Decisões do serviço

- **Classe provisória:** paciente novo entra na fila com a classe proposta e `CLASSIFICACAO_INICIAL` pendente.
  Evento novo antes da aprovação só gera nova classificação se trouxer achado clínico (não alerta) e mudar o resultado.
- **Substituição (regra 3):** evento novo substitui só sugestões pendentes de *mudança de classe*, e só quando
  ele mesmo gera outra mudança de classe. `REMOVER` e alertas pendentes não são apagados.
- **Saída:** aprovar `REMOVER` registra o motivo (`desistencia`, `outro_servico`, `duplicata`) e fecha as outras
  pendentes do paciente. Duplicata = mesmo paciente + procedimento já ativo; sai a solicitação nova.
- **Relógio:** dia zero = data de entrada mais antiga recebida; persistido na tabela `simulacao`.

- **Observações (regra 11):** o replay tira `observacoes` da solicitação e as manda como evento
  `tipo_evento = "observacao"` junto do último evento do paciente, como `spikes/carga.py`.

## Pendências conhecidas

- `sem_urgencia` (critério do verificador) está em `servico/regras.py`; o lugar final é o motor.
