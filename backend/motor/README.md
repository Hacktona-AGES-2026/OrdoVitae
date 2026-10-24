# Motor

Recebe **achados** (de `backend/extracao/`) e dados estruturados de risco, e devolve classe SWALIS,
scores, sugestões e a ordem da fila. Não lê texto, não chama LLM, não acessa banco.

| Arquivo | O que faz |
|---|---|
| `modelos.py` | Contratos: `Achado`, `Avaliacao`, `Sugestao` |
| `config.py` | Pontos, pesos, limiares, pisos, matriz de risco — **toda escolha clínica fica aqui** |
| `avaliacao.py` | Achados de 1 solicitação → gravidade, deterioração, classe SWALIS, estado clínico |
| `risco.py` | ASA (paciente) × risco do procedimento → score de risco |
| `decisor.py` | Estado aprovado × avaliação nova → sugestões com justificativa (só com achado novo) |
| `fila.py` | Score final, ordenação, regra de ouro, prévia de posição, alertas |

```
score clínico = estado clínico (pontos + chance de piora)      ← aprovado pelo regulador
              + urgência da classe SWALIS × 2                  ← aprovado pelo regulador
              + espera, ponderada pela urgência da classe      ← anda sozinha
score final   = score clínico × (1 − 0,2 × risco)
ordem         = score final → mais antigo → id, depois a trava da regra de ouro
```

A fila **não agrupa por classe**: a classe é parâmetro do score clínico.

Testes: `cd backend && python3 -m unittest discover -s tests -t .`
