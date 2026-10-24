# Spec — Módulo de extração (Rodrigo)

## O que é

Recebe um dado novo (solicitação ou evento) e devolve uma lista de **achados**.
O motor só entende achados. Ele nunca lê texto livre nem chama LLM.

```
dado novo ──> extração ──> list[Achado] ──> motor
```

- Pasta: `backend/extracao/`
- Contrato: `Achado`, `CodigoAchado`, `Dimensao`, `Evidencia`, `Origem` em `backend/motor/modelos.py`. **Não altere esse arquivo sem falar com o Francisco/Nico.**
- Entrada: linhas já normalizadas (CID sem ponto e em maiúsculas, categorias em minúsculas, como no `scriptPadronizacaoNormalizacao/script.py`).

## Funções a implementar

```python
def extrair_solicitacao(sol: dict, resposta_llm: list[dict] | None = None) -> list[Achado]: ...
def extrair_evento(ev: dict, resposta_llm: list[dict] | None = None) -> list[Achado]: ...
```

`resposta_llm` é a extração do LLM já feita antes (o simulador lê do banco e manda junto).
Se vier `None`, use só as regras. **Nada aqui chama a API do LLM em tempo real.**

## Parte 1: regras (fazer primeiro, já destrava o motor)

### Solicitação (no dia da entrada na fila)

`data_fato` = `data_entrada_fila`. `Evidencia(fonte="solicitacao", ref="<solicitacao_id>:<campo>")`.

| Condição | Achado | Dimensão |
|---|---|---|
| `cid_principal` começa com `C` | `CID_MALIGNO` | gravidade |
| CID entre `D37` e `D48`, ou começa com `R91` | `CID_SUSPEITO` | gravidade |
| CID em `{I200, K403, K400, K420, K430, K800, N132, I832}` | `CID_URGENTE` | gravidade |
| `intensidade_dor_eva` >= 7 | `DOR_INTENSA` | gravidade |
| `intensidade_dor_eva` entre 4 e 6 | `DOR_MODERADA` | gravidade |
| `limitacao_funcional` = grave | `LIMITACAO_GRAVE` | gravidade |
| `limitacao_funcional` = moderada | `LIMITACAO_MODERADA` | gravidade |
| `justificativa_clinica` com menos de 30 caracteres | `DADOS_INSUFICIENTES` | alerta |
| regex de alarme na `justificativa_clinica` (abaixo) | `SINAL_ALARME` (com `trecho`) | gravidade |

Use o CID, **nunca** `flag_oncologico`. **Não use** `prioridade_regulacao`, procedimento, sexo, idade nem município.

Regex de alarme (tirado do verificador oficial, `dataset/verificar_fila_priorizada.py`):
```
encarcer|estrangul|colangite|icter|pancreatite|enterorragia|melena|hematemese|suboclus|perda ponderal|disfagia|sepse|hidronefrose|perda de funcao|transfund|hemoptise|rouquidao|linfonodo.*(?:fixo|palpavel)|sangramento espontaneo|acamad|ulcera de pressao|quedas de repeticao|glaucoma facomorfico|retencao de co2|dano neurologico|psa em elevacao|dessaturacao|angina em repouso|sincope|crescimento rapido|retencao urinaria aguda|massa anexial|ca-125
```

### Evento

`data_fato` = `data_evento`. `Evidencia(fonte="evento", ref=evento_id, trecho=descricao)`.

| `tipo_evento` / `resultado` | Achado | Dimensão |
|---|---|---|
| `biopsia` / `positivo` | `BIOPSIA_POSITIVA` | gravidade |
| `pronto_socorro` / qualquer | `PRONTO_SOCORRO` | deterioração |
| `internacao` / qualquer | `INTERNACAO` | deterioração |
| `exame_imagem` / `progressao` | `PROGRESSAO_IMAGEM` | deterioração |
| `consulta_reavaliacao` / `piora` | `REAVALIACAO_PIORA` | deterioração |
| `consulta_reavaliacao` / `melhora` | `MELHORA` | deterioração |
| `contato_telefonico` / `relata_piora` | `PIORA_RELATADA` | deterioração |
| `contato_telefonico` / `relata_melhora` | `MELHORA` | deterioração |
| `contato_telefonico` / `nao_atendeu` | `PERDA_CONTATO` | alerta |
| `contato_telefonico` / `desistiu` ou `informou_cirurgia_outro_servico` | `SAIU_DA_FILA` | alerta |
| `falta` / qualquer | `PERDA_CONTATO` | alerta |
| `hba1c` com `valor_numerico` > 8.5 | `HBA1C_DESCONTROLADA` (deterioração) **e** `OTIMIZAR_CLINICAMENTE` (alerta) | — |
| demais (biópsia negativa, imagem estável, atendeu…) | nenhum | — |

## Parte 2: LLM nos textos livres (depois que a parte 1 estiver pronta)

Textos lidos: `justificativa_clinica` (solicitação), `descricao` (evento) e `observacoes`.

**Rodada única offline**: um script `backend/scripts/extrair_llm.py` passa por todos os textos e grava na tabela:

```sql
CREATE TABLE extracoes_llm (
    ref TEXT PRIMARY KEY,      -- "SOL-…:justificativa_clinica" | "EVT-…" | "SOL-…:observacoes"
    modelo TEXT,
    resposta_json TEXT,        -- lista no formato abaixo, já validada
    criado_em TEXT
);
```

**Pedido ao LLM** (temperatura 0): o texto + a lista de códigos permitidos (os de `CodigoAchado`, exceto os de CID, dor e limitação, que vêm por regra). Resposta em JSON:

```json
[{"codigo": "PIORA_RELATADA", "data_fato": "2026-08-10", "trecho": "piora da dor ha 2 meses"}]
```

**Validação obrigatória antes de gravar**, descartando o item que falhar:
- `codigo` existe em `CodigoAchado`;
- `trecho` é um pedaço **literal** do texto original, para impedir alucinação;
- `data_fato` é uma data ISO ou `null` (nunca inventada; se o texto não diz a data, fica `null`).

Achados do LLM saem com `origem=Origem.LLM`. A deduplicação com as regras é feita no motor (`motor.avaliacao.deduplicar`).

## Como saber que está pronto

Rodando a parte 1 sobre o dataset inteiro, os números devem bater aproximadamente com estes:
- `CID_MALIGNO`: 177 solicitações
- `BIOPSIA_POSITIVA`: 147 eventos
- `SAIU_DA_FILA`: 18 eventos
- `PRONTO_SOCORRO`: 203 eventos; `INTERNACAO`: 41

Testes em `backend/tests/test_extracao.py` (unittest, no mesmo estilo de `test_motor.py`).
