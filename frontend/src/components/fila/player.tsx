import { ChevronLeft, ChevronRight, FastForward, Loader2, Pause, Play, SkipForward } from "lucide-react"

import { Button } from "@/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/components/ui/select"
import { Slider } from "@/components/ui/slider"
import { formatarData } from "@/lib/apresentacao"
import { cn } from "@/lib/utils"

const VELOCIDADES = [
  { label: "1×", ms: 2000 },
  { label: "2×", ms: 1200 },
  { label: "4×", ms: 600 },
  { label: "8×", ms: 300 },
]

type Props = {
  frame: number
  total: number
  data: string
  primeiraData: string
  ultimaData: string
  tocando: boolean
  carregando: boolean
  /** Backend avançando o relógio da simulação neste momento. */
  simulando: boolean
  velocidade: number
  onFrame: (f: number) => void
  onTocar: () => void
  onSimular: () => void
  onProximaSugestao: () => void
  onVelocidade: (ms: number) => void
}

/** Player flutuante: navega pelos dias já fotografados e, no último dia, simula o próximo. */
export function Player(p: Props) {
  const noFim = p.frame >= p.total - 1
  return (
    <div
      role="region"
      aria-label="Linha do tempo da simulação"
      className="fixed inset-x-0 bottom-4 z-30 mx-auto flex w-[calc(100%-2rem)] flex-col gap-2 rounded-2xl bg-popover/90 px-4 py-3 text-popover-foreground shadow-xl ring-1 ring-foreground/10 backdrop-blur-md md:w-1/2 md:min-w-[38rem]"
    >
      <div className="flex items-center gap-3">
        <div className="w-28 shrink-0">
          <p className="font-heading text-sm leading-tight font-semibold">
            Dia {p.frame + 1}
            <span className="font-normal text-muted-foreground"> / {p.total}</span>
          </p>
          <p className="flex items-center gap-1 text-[11px] text-muted-foreground tabular-nums">
            {formatarData(p.data)}
            {(p.carregando || p.simulando) && <Loader2 className="size-3 animate-spin" aria-label="Carregando" />}
          </p>
        </div>
        <div className="flex flex-1 items-center justify-center gap-1.5">
          <Button variant="ghost" size="icon" aria-label="Dia anterior" onClick={() => p.onFrame(p.frame - 1)}>
            <ChevronLeft />
          </Button>
          <Button
            size="icon-lg"
            className="rounded-full"
            aria-label={p.tocando ? "Pausar" : noFim ? "Simular dias seguidos" : "Reproduzir"}
            onClick={p.onTocar}
          >
            {p.tocando ? <Pause /> : <Play />}
          </Button>
          <Button variant="ghost" size="icon" aria-label="Próximo dia" disabled={noFim} onClick={() => p.onFrame(p.frame + 1)}>
            <ChevronRight />
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={p.simulando}
            onClick={p.onSimular}
            title="O backend injeta as chegadas do dia seguinte do dataset e recalcula a fila"
          >
            <FastForward />
            Simular +1 dia
          </Button>
          <Button
            variant="outline"
            size="sm"
            disabled={p.simulando}
            onClick={p.onProximaSugestao}
            title="Avança a simulação até o próximo dia em que o motor sugere uma mudança"
          >
            <SkipForward />
            Próxima sugestão
          </Button>
        </div>
        <div className="flex shrink-0 justify-end">
          <Select value={String(p.velocidade)} onValueChange={(v) => p.onVelocidade(Number(v))}>
            <SelectTrigger size="sm" className="w-16" aria-label="Velocidade">
              <SelectValue>{(v: string) => VELOCIDADES.find((x) => String(x.ms) === v)?.label}</SelectValue>
            </SelectTrigger>
            <SelectContent>
              {VELOCIDADES.map((v) => (
                <SelectItem key={v.ms} value={String(v.ms)}>
                  {v.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>
      </div>
      <div className="flex items-center gap-3 text-[11px] text-muted-foreground tabular-nums">
        <span>{formatarData(p.primeiraData).slice(0, 5)}</span>
        <Slider
          aria-label="Dia"
          min={0}
          max={Math.max(p.total - 1, 0)}
          step={1}
          value={[p.frame]}
          onValueChange={(v) => p.onFrame(Array.isArray(v) ? v[0] : v)}
          className="flex-1"
        />
        <span className={cn(noFim && "font-semibold text-foreground")}>{formatarData(p.ultimaData).slice(0, 5)}</span>
      </div>
      {p.tocando && noFim && (
        <p className="text-center text-[11px] text-muted-foreground">Simulando ao vivo: cada passo avança um dia no backend.</p>
      )}
    </div>
  )
}
