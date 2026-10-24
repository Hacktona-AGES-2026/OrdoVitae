import { useQueryClient } from "@tanstack/react-query"
import { Download, FastForward, LayoutGrid, List, Loader2, ServerCrash, Timer } from "lucide-react"
import { useCallback, useEffect, useMemo, useState } from "react"

import { API_URL, ErroApi, api } from "@/api/cliente"
import {
  diaCarregado,
  preCarregarDias,
  useAvancarDia,
  useConfigurarSimulacao,
  useDatas,
  useFichas,
  useFilaDoDia,
  usePendentes,
  useSimulacao,
  useSugestoes,
} from "@/api/consultas"
import type { ItemFilaDTO, SugestaoDTO } from "@/api/tipos"
import { DetalheDialog } from "@/components/fila/detalhe-dialog"
import { FeedDia } from "@/components/fila/feed-dia"
import { FilaCards } from "@/components/fila/fila-cards"
import { FilaLista } from "@/components/fila/fila-lista"
import { Paginacao } from "@/components/fila/paginacao"
import { Player } from "@/components/fila/player"
import { ThemeToggle } from "@/components/theme-toggle"
import { Button, buttonVariants } from "@/components/ui/button"
import { Skeleton } from "@/components/ui/skeleton"
import { Tabs, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { formatarData, LIMIAR_SALTO } from "@/lib/apresentacao"
import { cn } from "@/lib/utils"

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
      <b className={cn("font-semibold tabular-nums", !alerta && "text-foreground")}>{valor.toLocaleString("pt-BR")}</b> {label}
    </span>
  )
}

/** PUT /simulacao: desligada, as sugestões do motor ficam pendentes para o regulador aprovar. */
function ChaveAutoAprovar({ ligada }: { ligada: boolean }) {
  const configurar = useConfigurarSimulacao()
  return (
    <button
      type="button"
      role="switch"
      aria-checked={ligada}
      disabled={configurar.isPending}
      onClick={() => configurar.mutate(!ligada)}
      title="Ligada: o motor aprova as próprias sugestões. Desligada: ficam pendentes para o regulador."
      className={cn(
        "inline-flex items-center gap-2 rounded-full px-2.5 py-1 transition-colors",
        ligada ? "bg-swalis-b/20 text-foreground" : "bg-muted text-muted-foreground hover:bg-muted/70",
      )}
    >
      <span className={cn("relative h-3.5 w-6 rounded-full transition-colors", ligada ? "bg-foreground" : "bg-foreground/25")}>
        <span className={cn("absolute top-0.5 size-2.5 rounded-full bg-background transition-[left]", ligada ? "left-3" : "left-0.5")} />
      </span>
      Aprovação automática <b>{ligada ? "ligada" : "desligada"}</b>
    </button>
  )
}

function Cabecalho({ hoje, autoAprovar }: { hoje: string | null; autoAprovar?: boolean }) {
  return (
    <header className="border-b">
      <div className="mx-auto flex max-w-[110rem] flex-wrap items-center justify-between gap-4 px-4 py-4 sm:px-6">
        <div>
          <p className="flex items-center gap-2 text-[11px] font-semibold tracking-widest text-muted-foreground uppercase">
            <span className="size-1.5 rounded-full bg-success ring-3 ring-success/20" />
            Fila cirúrgica · recalculada a cada dia
          </p>
          <h1 className="font-heading text-xl font-semibold tracking-tight">
            OrdoVitae <span className="font-normal text-muted-foreground">— linha do tempo da fila</span>
          </h1>
        </div>
        <div className="flex flex-wrap items-center gap-2 text-xs">
          {hoje && (
            <span className="rounded-full bg-muted px-2.5 py-1 text-muted-foreground">
              Hoje na simulação <b className="text-foreground">{formatarData(hoje)}</b>
            </span>
          )}
          {autoAprovar !== undefined && <ChaveAutoAprovar ligada={autoAprovar} />}
          {hoje && (
            <a href={api.exportarCsvUrl()} className={buttonVariants({ variant: "outline", size: "sm" })}>
              <Download />
              fila_priorizada.csv
            </a>
          )}
          <ThemeToggle />
        </div>
      </div>
    </header>
  )
}

function TelaEstado({ icone, titulo, children }: { icone: React.ReactNode; titulo: string; children: React.ReactNode }) {
  return (
    <div className="mx-auto flex max-w-lg flex-col items-center gap-3 px-4 py-24 text-center">
      <span className="text-muted-foreground [&_svg]:size-8">{icone}</span>
      <h2 className="font-heading text-lg font-semibold">{titulo}</h2>
      <div className="text-sm text-muted-foreground">{children}</div>
    </div>
  )
}

function SemFotos({ hoje, autoAprovar }: { hoje: string | null; autoAprovar: boolean }) {
  const avancar = useAvancarDia()
  return (
    <div className="min-h-screen bg-background text-foreground">
      <Cabecalho hoje={hoje} autoAprovar={autoAprovar} />
      <TelaEstado icone={<Timer />} titulo={hoje ? "Nenhum dia fotografado ainda" : "A simulação ainda não começou"}>
        <p>
          Cada dia simulado guarda uma foto da fila. Com o backend rodando com <code className="font-mono">SIMULADOR=1</code>, avance o
          primeiro dia para começar.
        </p>
        <Button className="mt-4" disabled={avancar.isPending} onClick={() => avancar.mutate(1)}>
          {avancar.isPending ? <Loader2 className="animate-spin" /> : <FastForward />}
          Simular primeiro dia
        </Button>
        {avancar.error && <p className="mt-2 text-destructive">{avancar.error.message}</p>}
      </TelaEstado>
    </div>
  )
}

function App() {
  const simulacao = useSimulacao()
  const datas = useDatas()
  const hoje = simulacao.data?.hoje ?? null

  if (simulacao.isPending || datas.isPending)
    return (
      <div className="min-h-screen bg-background text-foreground">
        <Cabecalho hoje={null} />
        <TelaEstado icone={<Loader2 className="animate-spin" />} titulo="Conectando ao backend…">
          {API_URL}
        </TelaEstado>
      </div>
    )

  const erro = simulacao.error ?? datas.error
  if (erro)
    return (
      <div className="min-h-screen bg-background text-foreground">
        <Cabecalho hoje={null} />
        <TelaEstado icone={<ServerCrash />} titulo="API indisponível">
          <p>{erro.message}</p>
          <p className="mt-2">
            Suba o backend (<code className="font-mono">SIMULADOR=1 uvicorn api.main:app</code> dentro de <code>backend/</code>) ou ajuste{" "}
            <code className="font-mono">VITE_API_URL</code>.
          </p>
        </TelaEstado>
      </div>
    )

  const autoAprovar = simulacao.data?.autoAprovar ?? false
  const dias = datas.data ?? []
  if (!hoje || dias.length === 0) return <SemFotos hoje={hoje} autoAprovar={autoAprovar} />

  return <Painel hoje={hoje} datas={dias} autoAprovar={autoAprovar} />
}

function Painel({ hoje, datas, autoAprovar }: { hoje: string; datas: string[]; autoAprovar: boolean }) {
  const qc = useQueryClient()
  const total = datas.length
  const ultimo = total - 1

  // null = acompanha o dia mais recente (a timeline cresce enquanto a simulação anda)
  const [frameEscolhido, setFrameEscolhido] = useState<number | null>(null)
  const frame = Math.min(frameEscolhido ?? ultimo, ultimo)
  const [tocando, setTocando] = useState(false)
  const [velocidade, setVelocidade] = useState(1200)
  const [visao, setVisao] = useState<Visao>("lista")
  const [pagina, setPagina] = useState(1)
  const [aberto, setAberto] = useState<string | null>(null)

  const data = datas[frame]
  const ehHoje = data === hoje
  const primeiroDia = frame === 0

  const filaQ = useFilaDoDia(data, hoje)
  const sugestoesQ = useSugestoes()
  const pendentesQ = usePendentes()
  const avancar = useAvancarDia()

  const setFrame = useCallback((f: number) => setFrameEscolhido(f >= ultimo ? null : Math.max(0, f)), [ultimo])
  const pausar = useCallback(() => setTocando(false), [])
  const simular = useCallback(() => {
    if (!avancar.isPending) avancar.mutate(1, { onSuccess: () => setFrameEscolhido(null) })
  }, [avancar])
  const alternar = () => {
    if (tocando) return pausar()
    setTocando(true)
  }

  // pré-carrega os próximos dias (foto antiga é imutável e fica em cache)
  useEffect(() => {
    preCarregarDias(qc, datas.slice(frame + 1, frame + 4), hoje)
  }, [qc, datas, frame, hoje])

  // play: no meio da timeline reproduz as fotos; no último dia passa a simular dias novos no backend
  useEffect(() => {
    if (!tocando) return
    const id = setInterval(() => {
      if (frame < ultimo) {
        if (diaCarregado(qc, datas[frame + 1])) setFrame(frame + 1)
      } else if (!avancar.isPending && !filaQ.isFetching) {
        simular()
      }
    }, velocidade)
    return () => clearInterval(id)
  }, [tocando, velocidade, frame, ultimo, datas, qc, setFrame, simular, avancar.isPending, filaQ.isFetching])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (aberto || (e.target as HTMLElement).closest("input, textarea, button, select, [role=slider], [role=combobox]")) return
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

  const semFoto = filaQ.error instanceof ErroApi && filaQ.error.status === 404
  const dia = filaQ.isPlaceholderData || semFoto ? undefined : filaQ.data
  const ordem = useMemo(() => dia?.ordem ?? [], [dia])

  const pendentes = useMemo(() => pendentesQ.data ?? new Map<string, SugestaoDTO[]>(), [pendentesQ.data])
  const totalPendentes = useMemo(
    () => [...pendentes.values()].filter((ss) => ss.some((s) => s.tipo !== "classificacao_inicial")).length,
    [pendentes],
  )

  const stats = useMemo(
    () => ({
      naFila: ordem.length,
      saltos: primeiroDia ? 0 : ordem.filter((i) => i.posicaoAnterior !== null && Math.abs(i.posicaoAnterior - i.posicao) >= LIMIAR_SALTO).length,
      foraDoPrazo: ordem.filter((i) => i.alemDoPrazo > 0).length,
      criticos: ordem.filter((i) => i.critico).length,
    }),
    [ordem, primeiroDia],
  )

  const porPagina = POR_PAGINA[visao]
  const totalPaginas = Math.max(1, Math.ceil(ordem.length / porPagina))
  const paginaAtual = Math.min(pagina, totalPaginas)
  const visiveis = ordem.slice((paginaAtual - 1) * porPagina, paginaAtual * porPagina)
  const fichas = useFichas(useMemo(() => visiveis.map((i) => i.solicitacaoId), [visiveis]))

  const abrir = (sid: string) => {
    pausar()
    setAberto(sid)
  }
  const irParaPagina = (p: number) => {
    setPagina(p)
    document.getElementById("fila")?.scrollIntoView({ behavior: "smooth", block: "start" })
  }

  const paginacao = (onPagina: (p: number) => void) => (
    <Paginacao pagina={paginaAtual} totalPaginas={totalPaginas} totalItens={ordem.length} porPagina={porPagina} onPagina={onPagina} />
  )
  const propsFila = {
    itens: visiveis,
    fichas,
    pendentes,
    data,
    hoje,
    primeiroDia,
    onAbrir: (i: ItemFilaDTO) => abrir(i.solicitacaoId),
  }

  return (
    <div className="min-h-screen bg-background text-foreground">
      <Cabecalho hoje={hoje} autoAprovar={autoAprovar} />

      <main className="mx-auto grid max-w-[110rem] items-start gap-4 px-4 py-4 sm:px-6 lg:grid-cols-[minmax(0,3fr)_minmax(0,7fr)]">
        <FeedDia
          data={data}
          hoje={hoje}
          dia={dia}
          primeiroDia={primeiroDia}
          sugestoes={sugestoesQ.data}
          carregandoSugestoes={sugestoesQ.isPending}
          onAbrir={abrir}
        />

        <section id="fila" className="flex min-w-0 scroll-mt-4 flex-col gap-3">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex flex-wrap items-center gap-2">
              <h2 className="font-heading text-base font-semibold">
                Fila de {formatarData(data)}
                {ehHoje && <span className="ml-1.5 text-xs font-normal text-muted-foreground">(hoje, ao vivo)</span>}
              </h2>
              <Stat valor={stats.naFila} label="na fila" />
              <Stat valor={stats.saltos} label={`saltos (≥${LIMIAR_SALTO})`} />
              <Stat valor={stats.foraDoPrazo} label="fora do prazo" alerta />
              {stats.criticos > 0 && <Stat valor={stats.criticos} label={stats.criticos === 1 ? "crítico" : "críticos"} alerta />}
              {totalPendentes > 0 && (
                <Stat valor={totalPendentes} label={totalPendentes === 1 ? "aprovação pendente" : "aprovações pendentes"} />
              )}
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

          {semFoto ? (
            <TelaEstado icone={<Timer />} titulo="Sem foto da fila neste dia">
              O backend só guarda a fila dos dias em que a simulação avançou com <code className="font-mono">avancar-dia</code>.
            </TelaEstado>
          ) : filaQ.error ? (
            <TelaEstado icone={<ServerCrash />} titulo="Erro ao carregar a fila">
              {filaQ.error.message}
            </TelaEstado>
          ) : !dia ? (
            <div className="flex flex-col gap-2">
              {Array.from({ length: 6 }, (_, i) => (
                <Skeleton key={i} className="h-24 w-full rounded-xl" />
              ))}
            </div>
          ) : (
            <>
              {paginacao(setPagina)}
              {ordem.length === 0 ? (
                <p className="py-12 text-center text-sm text-muted-foreground">Nenhuma solicitação na fila neste dia.</p>
              ) : visao === "lista" ? (
                <FilaLista {...propsFila} />
              ) : (
                <FilaCards {...propsFila} />
              )}
              {paginacao(irParaPagina)}
            </>
          )}
        </section>
      </main>

      <footer className="mx-auto max-w-[110rem] px-4 pb-40 text-xs leading-relaxed text-muted-foreground sm:px-6">
        <b className="text-foreground">Como ler.</b> Cada dia da linha do tempo é a foto da fila guardada pelo backend; o último é a fila
        viva. No último dia, o play (ou “Simular +1 dia”) avança a simulação: o backend injeta as chegadas do dia seguinte do dataset e
        recalcula a fila. Com a aprovação automática desligada, as sugestões do motor aparecem no card para o regulador aprovar.
      </footer>

      <Player
        frame={frame}
        total={total}
        data={data}
        primeiraData={datas[0]}
        ultimaData={datas[ultimo]}
        tocando={tocando}
        carregando={filaQ.isFetching}
        simulando={avancar.isPending}
        velocidade={velocidade}
        onFrame={(f) => {
          pausar()
          setFrame(f)
        }}
        onTocar={alternar}
        onSimular={() => {
          pausar()
          simular()
        }}
        onVelocidade={setVelocidade}
      />

      <DetalheDialog
        sid={aberto}
        item={ordem.find((i) => i.solicitacaoId === aberto) ?? null}
        data={data}
        hoje={hoje}
        primeiroDia={primeiroDia}
        totalNaFila={ordem.length}
        onClose={() => setAberto(null)}
      />
    </div>
  )
}

export default App
