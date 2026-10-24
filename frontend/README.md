# OrdoVitae — Frontend

Painel do regulador da fila cirúrgica. Mostra a **linha do tempo** da fila (uma foto por dia, guardada pelo backend), o que mudou em cada dia, as sugestões do motor para aprovar ou rejeitar e a ficha completa de cada solicitação.

Consome a API FastAPI de [`backend/`](../backend/README.md). Não há mais dados mockados no front.

## Stack

| Camada | Escolha |
|---|---|
| Build / dev server | Vite |
| UI | React 19 + TypeScript |
| Dados do servidor | TanStack Query (cache, pré-carregamento, mutações) |
| Estilo | Tailwind CSS v4 (plugin `@tailwindcss/vite`, sem `tailwind.config`) |
| Componentes | shadcn/ui (estilo `base-nova`, sobre Base UI) |
| Gráficos | Recharts, via o componente `chart` do shadcn |
| Ícones | lucide-react |
| Lint | oxlint |

## Como rodar

1. **Backend com o simulador** (`SIMULADOR=1` liga as rotas que injetam o dataset dia a dia). Da raiz do repositório:
   ```bash
   python -m venv .venv
   .venv/Scripts/python -m pip install -r requirements.txt
   cd backend
   SIMULADOR=1 ORDO_DB_URL=sqlite:///../database/dev.sqlite3 ../.venv/Scripts/python -m uvicorn api.main:app --port 8000
   ```
   Preparar a demo (em outro terminal):
   ```bash
   curl -X POST localhost:8000/simulacao/reiniciar
   curl -X POST localhost:8000/simulacao/pular-ate -H "Content-Type: application/json" -d '{"data":"2026-09-15"}'   # ≈1 min
   curl -X PUT  localhost:8000/simulacao -H "Content-Type: application/json" -d '{"autoAprovar":false}'
   ```
   Daí em diante a tela conduz: **Simular +1 dia** (ou play no último dia) avança a simulação, e com a aprovação automática
   desligada as sugestões do motor aparecem nos cards para aprovar.
2. **Front:**
   ```bash
   cd frontend
   npm install
   npm run dev        # http://localhost:5173
   ```

| Variável | Padrão | Para quê |
|---|---|---|
| `VITE_API_URL` | `http://localhost:8000` | Endereço da API (veja `.env.example`) |

O backend libera CORS para `http://localhost:5173` (`ORDO_CORS`).

Outros comandos: `npm run build` (type-check + build) e `npm run lint`.

## Estrutura de pastas

```
src/
├── main.tsx                 # ponto de entrada + QueryClientProvider
├── App.tsx                  # estados de conexão + Painel (timeline, paginação)
├── index.css                # Tailwind + tokens de tema (claro/escuro)
├── api/                     # ÚNICA camada que fala com o backend
│   ├── tipos.ts               # contratos: espelho dos DTOs de backend/api/dtos.py
│   ├── cliente.ts             # fetch, VITE_API_URL, ErroApi, um método por rota
│   └── consultas.ts           # hooks TanStack Query (cache, prefetch, aprovar/rejeitar)
├── lib/
│   ├── apresentacao.ts      # adaptadores DTO → tela (rótulos, ficha → Paciente, datas)
│   └── utils.ts             # cn()
└── components/
    ├── ui/                  # componentes shadcn (gerados pelo CLI)
    ├── fila/
    │   ├── player.tsx           # player flutuante da timeline
    │   ├── feed-dia.tsx         # resumo do dia: sugestões do motor + saltos na fila
    │   ├── decisao-sugestao.tsx # status da sugestão e botões aprovar/rejeitar
    │   ├── fila-lista.tsx       # visão em lista (padrão)
    │   ├── fila-cards.tsx       # visão em grade
    │   ├── paginacao.tsx        # paginação (acima e abaixo da fila)
    │   ├── detalhe-dialog.tsx   # ficha: scores, histórico, achados, dados, sugestões
    │   └── marcadores.tsx       # classe, movimento, prazo, indicadores
    └── theme-toggle.tsx
```

**Regra de dependência:** componentes → `lib/apresentacao` e `api/consultas` → `api/cliente` → backend. Componentes não chamam `fetch` nem leem `ficha.dados` direto.

## Contratos da API usados

| Rota | Uso na tela | Observações |
|---|---|---|
| `GET /simulacao` | Define "hoje" | `hoje = null` → simulação não começou |
| `PUT /simulacao` `{autoAprovar}` | Chave "Aprovação automática" no cabeçalho | Desligada = sugestões ficam pendentes |
| `GET /simulacao/datas` | Dias da linha do tempo | Dias com foto, em ordem |
| `POST /simulacao/avancar-dia` `{dias}` | "Simular +1 dia" e play no último dia | Com `SIMULADOR=1`, injeta as chegadas do dataset e fotografa a fila |
| `GET /fila` | Fila viva (último dia da timeline) | Traz todos os campos, incluindo `critico`, `oncologico`, `provisorio` e a composição do score |
| `GET /fila?data=` | Foto de um dia passado | Só `posicao`, `posicaoAnterior`, `classe`, `score`, `diasEmFila`, `prazo`, `alemDoPrazo`; o resto vem `null`. **404** se não houver foto |
| `GET /solicitacoes/{sid}` | Nome, CID, procedimento (lista) e modal de detalhe | A fila **não traz dados do paciente**: a ficha é buscada só para os itens da página visível e do painel |
| `GET /sugestoes` | Painel do dia (filtrado por `criadaEm`) | Pendentes trazem `previa` (posição de → para) |
| `GET /sugestoes?status=pendente` | Bloco de aprovação no card | Mostra a justificativa (e a comparativa, quando o backend mandar) |
| `GET /solicitacoes/{sid}/decisao-compartilhada` | Card roxo no topo do modal | Motor secundário, calculado só com os dados recebidos até hoje |
| `POST /sugestoes/{id}/aprovar` | Botão Aprovar | 409 se já decidida |
| `POST /sugestoes/{id}/rejeitar` | Botão Rejeitar (no modal) | `comentario` obrigatório (422) |
| `GET /fila/exportar.csv` | Link no cabeçalho | `fila_priorizada.csv` |

### Como os contratos são tratados

- **Dados do paciente:** `ficha.dados` é a linha crua do CSV (tudo texto, caixa inconsistente). `paciente()` em `lib/apresentacao.ts` normaliza: idade e dor em número, CID com ponto (`K409` → `K40.9`), município em caixa de título.
- **Fotos de dias passados:** os indicadores que vêm `null` não aparecem.
- **Ficha vista num dia passado:** a ficha é o estado *atual*. Achados e sugestões posteriores ao dia exibido aparecem esmaecidos, com a marca "depois deste dia".
- **Movimento:** `posicaoAnterior` comparada à posição atual. Até 4 posições é estável (arrasto da fila); 5 ou mais é salto. No primeiro dia da timeline não há dia anterior.
- **Erros:** `ErroApi` carrega o status HTTP e o `detalhe` do backend. API fora do ar, simulação vazia, dia sem foto e erro genérico têm cada um sua tela.

### Cache (TanStack Query)

| Dado | Validade | Motivo |
|---|---|---|
| Foto de dia passado | Infinita | É imutável |
| Fila de hoje | 30 s | Muda com eventos e aprovações |
| Ficha | 5 min | Muda pouco; invalidada ao decidir uma sugestão |
| Sugestões | 1 min | Invalidadas ao aprovar ou rejeitar |

O player pré-carrega os 3 dias seguintes e só avança quando o próximo dia já chegou, então a reprodução não trava esperando a rede.

## Recursos da demonstração

- **Aprovar na lista:** card com sugestão pendente ganha borda âmbar e um bloco com tipo, classe de → para, prévia de posição, motivos e justificativa, com **Aprovar** e **Rejeitar** (comentário obrigatório).
- **Cards mudando de posição:** `lib/use-flip.ts` anima a troca de posição (FLIP) quando o dia muda ou uma aprovação reordena a fila.
- **Card da lista:** à esquerda, posição e os scores **clínico** e de **risco** lado a lado; flag **CRÍTICO** em vermelho (chip e borda); faixa **cinza-azulada** no rodapé quando há achado `DADOS_INSUFICIENTES`.
- **Decisão compartilhada (roxo):** no modal, o resumo do motor secundário para o atendente, com o aviso de que é gerado com apoio de LLM e está sujeito a erros.

## Estado da tela (`App.tsx`)

| Estado | O que controla |
|---|---|
| `frame` / `tocando` / `velocidade` | Dia da timeline (abre em hoje) e reprodução |
| `visao` | `"lista"` (15 por página) ou `"cards"` (24 por página) |
| `pagina` | Página atual, limitada ao total de páginas do dia |
| `aberto` | Solicitação no modal. Abrir pausa o player |

Atalhos de teclado: **espaço** reproduz ou pausa; **← / →** voltam ou avançam um dia.

## Design system

- **Componentes:** sempre os de `src/components/ui`. Para adicionar:
  ```bash
  npx shadcn@latest add <componente>
  ```
  Os arquivos importam `cn` do pacote `cn` (do próprio shadcn); não troque. Rode `npm run build` depois, porque o CLI às vezes gera um `import * as React` sem uso.
- **Cores:** sempre por token de `src/index.css`, com valores para o claro (`:root`) e o escuro (`.dark`). A cor de cada item vem da **classe SWALIS**:

  | Token | Uso |
  |---|---|
  | `--swalis-a1` … `--swalis-d` | Classe do item (barra lateral, badge, legenda) |
  | `--success` / `--destructive` | Subida / descida, no prazo / fora do prazo |
  | `--chart-*` | Gráficos |

- **Tema:** a classe `dark` no `<html>`; um script no `index.html` aplica o tema antes de renderizar.
- **Idioma:** interface e nomes de domínio em português; os tipos de `api/tipos.ts` seguem os nomes do backend.

## Pendências conhecidas

- **Simulador externo.** A tela atualiza quando ela mesma avança a simulação. Se outro processo chamar `avancar-dia`, a tela só percebe ao recarregar (falta `refetchInterval` ou SSE).
- **Justificativa comparativa.** `ultrapassados` e `justificativaComparativa` vêm da branch `feat/justificativa-comparativa`; o card já mostra quando existirem.
- **Fichas em lote.** Cada item visível custa uma chamada `/solicitacoes/{sid}` (≈350 ms). Um endpoint com os dados de exibição na própria fila, ou fichas em lote, eliminaria isso.
- **Alertas.** `GET /alertas` já está no cliente (`useAlertas`), mas ainda não tem tela.
- **Bundle.** Tem cerca de 860 kB, a maior parte do Recharts; dá para dividir com `import()` no modal.
- **Testes.** Não há testes automatizados ainda.
