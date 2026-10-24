# Motor

Recebe **achados** (de `backend/extracao/`) e devolve classe SWALIS, sugestões e a ordem da fila.
Não lê texto, não chama LLM, não acessa banco.

| Arquivo | O que faz |
|---|---|
| `modelos.py` | Contratos: `Achado`, `Avaliacao`, `Sugestao` |
| `config.py` | Pontos, meia-vida, limiares e pisos — **toda escolha clínica fica aqui** |
| `avaliacao.py` | Etapa 1: achados de 1 solicitação → gravidade, deterioração, classe |
| `decisor.py` | Etapa 2: classe aprovada × proposta → sugestões com justificativa |
| `fila.py` | Ordena pelas classes aprovadas + trava da regra de ouro |

Testes: `cd backend && python3 -m unittest discover -s tests -t .`

Regulador aprova **mudança de classe**. Ordem dentro da classe é automática:
mais perto de estourar o prazo → mais antigo → id.
