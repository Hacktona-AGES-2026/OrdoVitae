# OrdoVitae — Frontend

Painel da fila cirúrgica priorizada. Mostra 30 dias de fila, recalculada dia a dia, com um player para avançar no tempo, o resumo do que mudou em cada dia e o detalhe de cada solicitação.

> **Estado atual:** ainda não há backend. Os dados vêm de um JSON estático e a priorização é calculada no próprio navegador. A seção [Integração com o backend](#integração-com-o-backend) explica o que trocar quando a API existir.

## Stack

| Camada | Escolha |
|---|---|
| Build / dev server | Vite |
| UI | React 19 + TypeScript |
| Estilo | Tailwind CSS v4 (plugin `@tailwindcss/vite`, sem `tailwind.config`) |
| Componentes | shadcn/ui (estilo `base-nova`, sobre Base UI) |
| Gráficos | Recharts, via o componente `chart` do shadcn |
| Ícones | lucide-react |
| Lint | oxlint |

## Como rodar

```bash
npm install
npm run dev       # http://localhost:5173
npm run build     # type-check (tsc -b) + build de produção
npm run lint
```

## Estrutura de pastas

```
src/
├── main.tsx                 # ponto de entrada
├── App.tsx                  # página única: estado global, layout, filtros, paginação
├── index.css                # Tailwind + tokens de tema (claro/escuro)
├── data/
│   └── fila-30dias.json     # MOCK: fila + eventos (exportado do mockup.html)
├── lib/
│   ├── priorizacao.ts       # MOCK do backend: tipos + motor de priorização dos 30 dias
│   ├── aprovacoes.ts        # aprovação das subidas (stub, pronto para API)
│   └── utils.ts             # cn() — combinação de classes Tailwind
└── components/
    ├── ui/                  # componentes shadcn (gerados pelo CLI)
    ├── fila/                # componentes da tela da fila
    │   ├── player.tsx         # player flutuante (dia, play/pausa, velocidade, slider)
    │   ├── feed-dia.tsx       # resumo do dia: subidas (com aprovar), eventos, entradas, saídas
    │   ├── filtros.tsx        # filtros de faixa, classe e prazo
    │   ├── fila-lista.tsx     # visão em lista (cards retangulares de largura total)
    │   ├── fila-cards.tsx     # visão em grade de cards
    │   ├── paginacao.tsx      # paginação (exibida acima e abaixo da fila)
    │   ├── detalhe-dialog.tsx # modal de detalhe da solicitação
    │   └── marcadores.tsx     # peças visuais: faixa, movimento, prazo
    ├── theme-toggle.tsx     # alternância claro/escuro
    └── dashboard/           # LEGADO: primeiro protótipo, só o swalis.tsx ainda é usado
```

## Fluxo de dados

```
fila-30dias.json ──► lib/priorizacao.ts ──► diasFila: DiaFila[] ──► App.tsx ──► componentes
  (mock)              (motor no navegador,    (30 dias, cada um     (frame atual,
                       roda uma vez ao         com a fila ordenada)   filtros, página)
                       carregar o módulo)
```

1. `priorizacao.ts` lê o JSON, monta a lista de `Solicitacao` (cada uma com seus eventos) e calcula `diasFila` uma única vez, quando o módulo é carregado.
2. `App.tsx` guarda o estado da tela: dia atual (`frame`), reprodução, visão (lista ou cards), filtros, página e item aberto no modal.
3. Os componentes recebem os dados já prontos por props. Nenhum componente busca dados sozinho.

### Modelo de dados

Os tipos estão em [`src/lib/priorizacao.ts`](src/lib/priorizacao.ts):

- **`Solicitacao`**: dados estáticos de uma solicitação (paciente, CID, procedimento, textos livres, flags derivadas como `oncologico` e `incerto`) e seus `eventos`.
- **`Evento`**: biópsia, HbA1c, pronto-socorro, internação, exame de imagem, reavaliação, contato ou falta, com data e resultado.
- **`ItemFila`**: a solicitação em um dia específico. Traz `posicao`, `posicaoAnterior`, `classe` (A1–D), `faixa` (1–5), `score`, `gravidade`, `diasEmFila`, `prazo` e `alemDoPrazo`.
- **`DiaFila`**: `{ data, ordem: ItemFila[] }`, a fila completa e ordenada de um dia.

### Regras de priorização (resumo)

- **Faixa:**

  | Faixa | Descrição |
  |---|---|
  | 1 | Câncer confirmado (CID `C*`) |
  | 2 | Suspeita de câncer (biópsia positiva ou lesão incerta) |
  | 3 | Urgência clínica |
  | 4 | Sintomas moderados |
  | 5 | Eletivo sem urgência |

- **Classe SWALIS e prazo:**

  | Classe | Prazo |
  |---|---|
  | A1 | 15 dias |
  | A2 | 21 dias |
  | B | 60 dias |
  | C | 180 dias |
  | D | 360 dias |

- **Índice (0–100):** gravidade clínica (até 60 pontos) mais tempo e atraso em relação ao prazo (até 40 pontos).
- **Ordenação:** faixa → classe → índice → dias de espera → idade → id da solicitação.

Essas regras são uma cópia temporária. O lugar definitivo delas é o backend.

## Estado e interações (`App.tsx`)

| Estado | O que controla |
|---|---|
| `frame` / `tocando` / `velocidade` | Dia exibido e reprodução automática (player) |
| `visao` | `"lista"` (padrão, 15 por página) ou `"cards"` (24 por página) |
| `filtros` | Faixas, classes e prazo (`todos`, `fora` ou `no_prazo`). Mudar o filtro volta para a página 1 |
| `pagina` | Página atual, limitada ao total depois de filtrar |
| `aberto` | Item exibido no modal. Abrir um item pausa o player |

Atalhos de teclado: **espaço** reproduz ou pausa; **← / →** voltam ou avançam um dia. Ficam desativados com o modal aberto.

### Aprovação de subidas

Uma *subida* é quando a solicitação ganha 5 posições ou mais de um dia para o outro. As subidas aparecem no resumo à esquerda, cada uma com o botão de aprovar.

- **Status possíveis:** `pendente`, `enviando` ou `aprovado` (`useAprovacoes()` em [`src/lib/aprovacoes.ts`](src/lib/aprovacoes.ts)).
- **Chave:** `data:solicitacao_id`, porque a mesma solicitação pode subir em dias diferentes.
- **Hoje:** `APROVACAO_AUTOMATICA = true`, então tudo já nasce aprovado.

## Design system

- **Componentes:** sempre os de `src/components/ui`. Para adicionar um novo:
  ```bash
  npx shadcn@latest add <componente>
  ```
  Os arquivos gerados importam `cn` do pacote `cn`, que é do próprio shadcn. Não troque esse import. Rode `npm run build` depois: o CLI às vezes gera um `import * as React` sem uso, que quebra o type-check.
- **Cores:** sempre por token, nunca em hexadecimal no componente. Os tokens ficam em `src/index.css`, com valores para o tema claro (`:root`) e para o escuro (`.dark`):

  | Token | Uso | Classes |
  |---|---|---|
  | `--faixa-1` … `--faixa-5` | Faixas de prioridade | `bg-faixa-1`, `text-faixa-3`… |
  | `--swalis-a1` … `--swalis-d` | Classes SWALIS | `bg-swalis-a1/15`… |
  | `--success`, `--destructive` | No prazo / fora do prazo, subida / descida | `text-success`, `bg-destructive/10`… |
  | `--chart-1` … `--chart-5` | Gráficos | `var(--chart-1)` |

- **Tema:** a classe `dark` no `<html>` liga o escuro. Um script em `index.html` aplica o tema antes de a página renderizar, para não piscar. O `ThemeToggle` salva a escolha no `localStorage`.
- **Idioma:** a interface e os nomes de domínio ficam em português (`solicitacoes`, `diasEmFila`, `faixa`).

## Integração com o backend

Hoje, `lib/priorizacao.ts` faz o papel do backend. Para integrar:

1. **Contrato:** a API deve devolver os dias da fila no formato `DiaFila[]`, mais as `Solicitacao` referenciadas por `idx` ou id. A tela só lê esses tipos; o motor de cálculo não é usado por ela.
2. **Trocar a fonte:** substituir `solicitacoes` e `diasFila` por dados vindos da API, carregados no `App` (por exemplo com um hook `useFila()` que tenha estado de carregamento e erro).
3. **Remover o mock:** apagar `src/data/fila-30dias.json` e o motor de `priorizacao.ts` (`classificar`, `gravidade`, `calcularDias`…). Mantenha os tipos e os textos de exibição (`FAIXA_NOME`, `TIPO_EVENTO_LABEL`, `PRAZO`).
4. **Justificativas:** hoje `justificar()` e `sinaisTexto()` montam os textos no front. O ideal é que venham prontos da API, junto com o item.
5. **Aprovações** (`lib/aprovacoes.ts`):
   1. Trocar `APROVACAO_AUTOMATICA` para `false`.
   2. Carregar o status vindo do servidor em `statusInicial`.
   3. Implementar o POST em `enviarAprovacao`. O endpoint sugerido é `POST /api/fila/subidas/{chave}/aprovar`.
6. **Paginação e filtros:** hoje são feitos no cliente, sobre cerca de 900 itens por dia. Se o volume crescer, passe-os para a API como parâmetros de consulta.

### Sobre os dados de origem

O script `scriptPadronizacaoNormalizacao/script.py` normaliza os CSVs e grava um SQLite com `procedimentos`, `fila_cirurgica`, `eventos_clinicos` e `referencias_swalis`. Ele **não** calcula priorização: classe, faixa, índice e posição diária ainda precisam ser implementados no backend, a partir dessa base.

## Pendências conhecidas

- `components/dashboard/` e `data/mock-fila.ts` são o primeiro protótipo e não são mais usados, exceto `dashboard/swalis.tsx` (o badge de classe). Mova esse arquivo para `components/fila/` e apague o resto.
- O bundle tem cerca de 700 kB, a maior parte do Recharts e do JSON do mock. O aviso de tamanho no build é esperado até o mock sair.
- Não há testes automatizados ainda.
