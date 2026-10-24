import { LayoutGrid, List } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { DetalheDialog } from "@/components/fila/detalhe-dialog"
import { FeedDia } from "@/components/fila/feed-dia"
import { FilaCards } from "@/components/fila/fila-cards"
import { FilaLista } from "@/components/fila/fila-lista"
import { FiltrosFila, type Filtros } from "@/components/fila/filtros"
import { Paginacao } from "@/components/fila/paginacao"
import { Player } from "@/components/fila/player"
import { ThemeToggle } from "@/components/theme-toggle"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { useAprovacoes } from "@/lib/aprovacoes"
import { cn } from "@/lib/utils"
import { diaNumero, diasFila, formatarData, META, type ItemFila } from "@/lib/priorizacao"

const TOTAL = diasFila.length
const POR_PAGINA = { lista: 15, cards: 24 } as const
type Visao = keyof typeof POR_PAGINA

function Stat({ valor, label, alerta }: { valor: number; label: string; alerta?: boolean }) {
  return (
    <span
      className={cn(
        "rounded-full px-2.5 py-1 text-xs whitespace-nowrap",
        alerta ? "bg-destructive/10 text-destructive" : "bg-muted text-muted-foreground",
      )}
    >
      <b className={cn("font-semibold tabular-nums", !alerta && "text-foreground")}>{valor.toLocaleString("pt-BR")}</b>{" "}
      {label}
    </span>
  )
}

function App() {
  const [frame, setFrameBruto] = useState(0)
  const [tocando, setTocando] = useState(false)
  const [velocidade, setVelocidade] = useState(700)
  const [visao, setVisao] = useState<Visao>("lista")
  const [filtros, setFiltros] = useState<Filtros>({ faixas: [], classes: [], prazo: "todos" })
  const [pagina, setPagina] = useState(1)
  const [aberto, setAberto] = useState<ItemFila | null>(null)
  const { statusDe, aprovar } = useAprovacoes()

  const setFrame = useCallback((f: number) => setFrameBruto(Math.max(0, Math.min(TOTAL - 1, f))), [])
  const pausar = useCallback(() => setTocando(false), [])
  const alternar = () => {
    if (tocando) return pausar()
    if (frame >= TOTAL - 1) setFrame(0)
    setTocando(true)
  }

  useEffect(() => {
    if (!tocando) return
    const id = setInterval(() => {
      setFrameBruto((f) => {
        if (f >= TOTAL - 1) {
          setTocando(false)
          return f
        }
        return f + 1
      })
    }, velocidade)
    return () => clearInterval(id)
  }, [tocando, velocidade])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (aberto || (e.target as HTMLElement).closest("input, button, select, [role=slider], [role=combobox]")) return
      if (e.key === " ") {
        e.preventDefault()
        alternar()
      } else if (e.key === "ArrowRight") {
        pausar()
        setFrame(frame + 1)
      } else if (e.key === "ArrowLeft") {
        pausar()
        setFrame(frame - 1)
      }
    }
    window.addEventListener("keydown", onKey)
    return () => window.removeEventListener("keydown", onKey)
  })

  const atual = diasFila[frame]
  const dia = diaNumero(atual.data)

  const stats = useMemo(
    () => ({
      naFila: atual.ordem.length,
      subidas: atual.ordem.filter((i) => i.posicaoAnterior !== null && i.posicaoAnterior - i.posicao >= 5).length,
      foraDoPrazo: atual.ordem.filter((i) => i.alemDoPrazo > 0).length,
    }),
    [atual],
  )

  const filtrados = useMemo(
    () =>
      atual.ordem.filter(
        (i) =>
          (filtros.faixas.length === 0 || filtros.faixas.includes(i.faixa)) &&
          (filtros.classes.length === 0 || filtros.classes.includes(i.classe)) &&
          (filtros.prazo === "todos" || (filtros.prazo === "fora" ? i.alemDoPrazo > 0 : i.alemDoPrazo <= 0)),
      ),
    [atual, filtros],
  )

  const porPagina = POR_PAGINA[visao]
  const totalPaginas = Math.max(1, Math.ceil(filtrados.length / porPagina))
  const paginaAtual = Math.min(pagina, totalPaginas)
  const visiveis = filtrados.slice((paginaAtual - 1) * porPagina, paginaAtual * porPagina)

  const irParaPagina = (p: number) => {
    setPagina(p)
    document.getElementById("fila")?.scrollIntoView({ behavior: "smooth", block: "start" })
  }
  const abrir = (item: ItemFila) => {
    pausar()
    setAberto(item)
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <header className="border-b">
        <div className="mx-auto flex max-w-[110rem] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
          <div>
            <p className="flex items-center gap-2 text-[11px] font-semibold tracking-widest text-muted-foreground uppercase">
              <span className="size-1.5 rounded-full bg-success ring-3 ring-success/20" />
              Fila cirúrgica · recalculada a cada dia
            </p>
            <h1 className="font-heading text-xl font-semibold tracking-tight">
              OrdoVitae <span className="font-normal text-muted-foreground">— fila de prioridade, {TOTAL} dias</span>
            </h1>
          </div>
          <div className="flex flex-wrap items-center gap-2 text-xs">
            <span className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground">
              <b className="text-foreground tabular-nums">{META.rows}</b> solicitações ·{" "}
              <b className="text-foreground">{TOTAL}</b> dias
            </span>
            <span className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground">
              Ref. <b className="text-foreground">{formatarData(META.ref)}</b>
            </span>
            <ThemeToggle />
          </div>
        </div>
      </header>

      <main className="mx-auto grid max-w-[110rem] items-start gap-4 px-4 py-4 sm:px-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,7fr)]">
        <FeedDia frame={frame} statusDe={statusDe} onAprovar={aprovar} onAbrir={abrir} />

        <section id="fila" className="flex min-w-0 scroll-mt-4 flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-heading text-base font-semibold">Fila priorizada</h2>
              <Stat valor={stats.naFila} label="na fila" />
              <Stat valor={stats.subidas} label="subidas (≥5)" />
              <Stat valor={stats.foraDoPrazo} label="fora do prazo" alerta />
            </div>
            <Tabs
              value={visao}
              onValueChange={(v) => {
                setVisao(v as Visao)
                setPagina(1)
              }}
            >
              <TabsList>
                <TabsTrigger value="lista">
                  <List />
                  Lista
                </TabsTrigger>
                <TabsTrigger value="cards">
                  <LayoutGrid />
                  Cards
                </TabsTrigger>
              </TabsList>
            </Tabs>
          </div>

          <FiltrosFila
            valor={filtros}
            onChange={(f) => {
              setFiltros(f)
              setPagina(1)
            }}
          />

          <Paginacao
            pagina={paginaAtual}
            totalPaginas={totalPaginas}
            totalItens={filtrados.length}
            porPagina={porPagina}
            onPagina={setPagina}
          />

          {filtrados.length === 0 ? (
            <p className="py-12 text-center text-sm text-muted-foreground">Nenhuma solicitação com esses filtros neste dia.</p>
          ) : visao === "lista" ? (
            <FilaLista itens={visiveis} dia={dia} primeiroDia={frame === 0} onAbrir={abrir} />
          ) : (
            <FilaCards itens={visiveis} dia={dia} primeiroDia={frame === 0} onAbrir={abrir} />
          )}

          <Paginacao
            pagina={paginaAtual}
            totalPaginas={totalPaginas}
            totalItens={filtrados.length}
            porPagina={porPagina}
            onPagina={irParaPagina}
          />
        </section>
      </main>

      <footer className="mx-auto max-w-[110rem] px-4 pb-36 text-xs leading-relaxed text-muted-foreground sm:px-6">
        <b className="text-foreground">Como ler.</b> Cada quadro é um dia. A cada dia a fila é recalculada com os
        eventos ocorridos até aquela data: espera, prazo da classe, índice e posição mudam. A seta mostra o movimento em
        relação ao dia anterior; subidas de 5 posições ou mais aparecem no resumo à esquerda para aprovação. O último dia
        ({formatarData(META.ref)}) corresponde à <span className="font-mono">fila_priorizada.csv</span>.
      </footer>

      <Player
        frame={frame}
        total={TOTAL}
        data={atual.data}
        primeiraData={diasFila[0].data}
        ultimaData={diasFila[TOTAL - 1].data}
        tocando={tocando}
        velocidade={velocidade}
        onFrame={(f) => {
          pausar()
          setFrame(f)
        }}
        onTocar={alternar}
        onVelocidade={setVelocidade}
      />

      <DetalheDialog item={aberto} frame={frame} dia={dia} onClose={() => setAberto(null)} />
    </div>
  )
}

export default App
