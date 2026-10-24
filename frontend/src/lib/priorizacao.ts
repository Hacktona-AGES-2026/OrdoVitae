// Motor de priorização da fila — porte do mockup.html.
// Enquanto o backend não existe, recalcula aqui os 30 dias a partir dos dados
// normalizados (fila_cirurgica + eventos_clinicos). Quando a API estiver pronta,
// ela deve devolver `DiaFila[]` neste mesmo formato e este arquivo some.

import bruto from "@/data/fila-30dias.json"

export type Classe = "A1" | "A2" | "B" | "C" | "D"
export type Faixa = 1 | 2 | 3 | 4 | 5

export const CLASSES: Classe[] = ["A1", "A2", "B", "C", "D"]
export const PRAZO: Record<Classe, number> = { A1: 15, A2: 21, B: 60, C: 180, D: 360 }
export const FAIXA_NOME: Record<Faixa, string> = {
  1: "Câncer confirmado",
  2: "Suspeita de câncer",
  3: "Urgência clínica",
  4: "Sintomas moderados",
  5: "Eletivo sem urgência",
}

export type TipoEvento =
  | "biopsia"
  | "hba1c"
  | "pronto_socorro"
  | "internacao"
  | "exame_imagem"
  | "consulta_reavaliacao"
  | "contato_telefonico"
  | "falta"

export const TIPO_EVENTO_LABEL: Record<TipoEvento, string> = {
  biopsia: "Biópsia",
  hba1c: "HbA1c",
  pronto_socorro: "Pronto-socorro",
  internacao: "Internação",
  exame_imagem: "Exame de imagem",
  consulta_reavaliacao: "Reavaliação",
  contato_telefonico: "Contato",
  falta: "Falta",
}

/** Uma solicitação da fila normalizada (colunas de fila_cirurgica + derivados). */
export type Solicitacao = {
  idx: number
  sid: string
  pid: string
  nome: string
  sexo: "F" | "M"
  idade: number
  municipio: string
  especialidade: string
  procedimento: string
  cidOriginal: string
  cid: string
  cidDescricao: string
  dor: number | null
  limitacao: string
  asa: number | null
  comorbidades: string
  dataEntrada: string
  justificativa: string
  observacoes: string
  risco: number | null
  porte: string
  uti: string
  prioridadeManual: string
  alarme: boolean
  alarmeTermo: string
  oncologico: boolean
  incerto: boolean
  cidUrgente: boolean
  dataSaida: string | null
  hba1cCadastro: number | null
  eventos: Evento[]
}

export type Evento = {
  idx: number
  data: string
  dia: number
  tipo: TipoEvento
  resultado: string
  valor: number | null
}

/** Sinais clínicos vistos até o dia: quantos dias desde o evento mais recente de cada tipo. */
export type Sinais = {
  prontoSocorro: number | null
  internacao: number | null
  piora: number | null
  biopsiaPositiva: number | null
  hba1c: number | null
}

export type ItemFila = {
  idx: number
  posicao: number
  posicaoAnterior: number | null
  classe: Classe
  faixa: Faixa
  score: number
  gravidade: number
  diasEmFila: number
  prazo: number
  alemDoPrazo: number
}

export type DiaFila = {
  data: string
  ordem: ItemFila[]
}

// ---------- carga ----------

const DIA_MS = 86_400_000
const diaDe = (iso: string) => Math.floor(Date.parse(iso.slice(0, 10) + "T00:00:00Z") / DIA_MS)
const isoDe = (dia: number) => new Date(dia * DIA_MS).toISOString().slice(0, 10)

type Bruto = {
  meta: { ref: string; start: string; days: number; frames: number; rows: number; events: number; onco: number }
  cols: string[]
  rows: unknown[][]
  events: [number, string, number, number, number | null][]
  types: TipoEvento[]
  results: string[]
}
const P = bruto as unknown as Bruto

export const META = P.meta

export const solicitacoes: Solicitacao[] = P.rows.map((a, idx) => {
  const r = Object.fromEntries(P.cols.map((c, i) => [c, a[i]])) as Record<string, never>
  return {
    idx,
    sid: r.sid,
    pid: r.pid,
    nome: r.nome,
    sexo: r.sexo,
    idade: r.idade,
    municipio: r.mun,
    especialidade: r.esp,
    procedimento: r.proc,
    cidOriginal: r.cid_raw,
    cid: r.cid,
    cidDescricao: r.cid_desc,
    dor: r.dor,
    limitacao: r.lim ?? "",
    asa: r.asa ?? null,
    comorbidades: r.comorb ?? "",
    dataEntrada: r.entrada,
    justificativa: r.just ?? "",
    observacoes: r.obs ?? "",
    risco: r.risco ?? null,
    porte: r.porte ?? "",
    uti: r.uti ?? "",
    prioridadeManual: r.prio_raw ?? "",
    alarme: !!r.alarme,
    alarmeTermo: r.alarme_termo ?? "",
    oncologico: !!r.onco,
    incerto: !!r.incerto,
    cidUrgente: !!r.cid_urgente,
    dataSaida: r.exit ?? null,
    hba1cCadastro: r.hba_cad ?? null,
    eventos: [],
  }
})

P.events.forEach(([i, data, tipo, res, valor]) => {
  const s = solicitacoes[i]
  if (!s) return
  s.eventos.push({ idx: i, data, dia: diaDe(data), tipo: P.types[tipo], resultado: P.results[res] ?? "", valor })
})
solicitacoes.forEach((s) => s.eventos.sort((a, b) => a.dia - b.dia))

// ---------- regras ----------

export function sinais(s: Solicitacao, dia: number): Sinais {
  const out: Sinais = { prontoSocorro: null, internacao: null, piora: null, biopsiaPositiva: null, hba1c: null }
  const min = (atual: number | null, d: number) => (atual === null ? d : Math.min(atual, d))
  for (const e of s.eventos) {
    if (e.dia > dia) break
    const d = dia - e.dia
    if (e.tipo === "pronto_socorro") out.prontoSocorro = min(out.prontoSocorro, d)
    else if (e.tipo === "internacao") out.internacao = min(out.internacao, d)
    else if (e.tipo === "biopsia" && e.resultado === "positivo") out.biopsiaPositiva = min(out.biopsiaPositiva, d)
    else if (
      (e.tipo === "exame_imagem" && e.resultado === "progressao") ||
      (e.tipo === "consulta_reavaliacao" && e.resultado === "piora") ||
      (e.tipo === "contato_telefonico" && e.resultado === "relata_piora")
    )
      out.piora = min(out.piora, d)
    if (e.tipo === "hba1c" && e.valor != null) out.hba1c = out.hba1c === null ? e.valor : Math.max(out.hba1c, e.valor)
  }
  return out
}

const recente = (v: number | null, lim: number) => v !== null && v <= lim

function classificar(s: Solicitacao, z: Sinais): number {
  if (s.oncologico) {
    const grave =
      recente(z.piora, 90) || recente(z.prontoSocorro, 30) || recente(z.internacao, 30) ||
      s.cidUrgente || s.alarme || (s.dor != null && s.dor >= 9)
    return grave ? 0 : 1
  }
  if (z.biopsiaPositiva !== null || s.incerto) {
    return recente(z.piora, 90) || recente(z.prontoSocorro, 90) || recente(z.internacao, 90) || s.alarme ? 0 : 1
  }
  if (
    s.cidUrgente || recente(z.prontoSocorro, 180) || recente(z.internacao, 180) || recente(z.piora, 180) ||
    s.alarme || (s.dor != null && s.dor >= 7) || s.limitacao === "grave"
  )
    return 2
  if ((s.dor != null && s.dor >= 4) || s.limitacao === "moderada") return 3
  return 4
}

function gravidade(s: Solicitacao, z: Sinais): number {
  const escala = (d: number | null, faixas: number[]) => {
    if (d === null) return 0
    const lims = [30, 90, 180, 365]
    const k = lims.findIndex((l) => d <= l)
    return faixas[k === -1 ? 4 : k]
  }
  let v = 0
  if (s.oncologico) v += 25
  else if (z.biopsiaPositiva !== null) v += 12
  v += escala(z.piora, [14, 12, 8, 5, 3])
  v += escala(z.prontoSocorro, [12, 9, 6, 3, 2])
  v += escala(z.internacao, [14, 10, 7, 4, 2])
  if (s.cidUrgente) v += 6
  if (s.alarme) v += 5
  if (s.dor != null) v += Math.min(s.dor, 10)
  v += s.limitacao === "grave" ? 8 : s.limitacao === "moderada" ? 4 : s.limitacao === "leve" ? 1 : 0
  const hba = z.hba1c ?? s.hba1cCadastro
  if (hba != null) v += hba >= 9 ? 4 : hba >= 8.5 ? 2 : 0
  return Math.min(v, 60)
}

function faixaDe(s: Solicitacao, z: Sinais, c: number): Faixa {
  if (s.oncologico) return 1
  if (z.biopsiaPositiva !== null || s.incerto) return 2
  return c === 2 ? 3 : c === 3 ? 4 : 5
}

export function sinaisTexto(s: Solicitacao, z: Sinais): string[] {
  const it: [string, number][] = []
  if (!s.oncologico && z.biopsiaPositiva !== null) it.push(["biópsia positiva sem CID C*", 95])
  if (!s.oncologico && s.incerto) it.push(["lesão de comportamento incerto", 60])
  if (z.piora !== null) it.push([`piora documentada há ${z.piora} dias`, 80])
  if (z.internacao !== null) it.push([`internação há ${z.internacao} dias`, 78])
  if (z.prontoSocorro !== null) it.push([`pronto-socorro há ${z.prontoSocorro} dias`, 76])
  if (s.cidUrgente) it.push(["CID de urgência", 70])
  if (s.dor != null && s.dor >= 4) it.push([`dor ${Math.round(s.dor)}/10`, s.dor >= 7 ? 65 : 25])
  if (s.limitacao === "grave") it.push(["limitação funcional grave", 55])
  else if (s.limitacao === "moderada") it.push(["limitação moderada", 18])
  if (s.alarme) it.push([s.alarmeTermo ? `sinal de alarme: ${s.alarmeTermo}` : "sinal de alarme no relato clínico", 50])
  return it.sort((a, b) => b[1] - a[1]).map((x) => x[0])
}

export function justificar(s: Solicitacao, item: ItemFila, z: Sinais): string {
  const lista = sinaisTexto(s, z)
  let det = lista.length
    ? lista.slice(0, 3).join("; ")
    : item.faixa <= 2
      ? "sem evento de piora registrado"
      : "sem sinais de gravidade registrados"
  det = det.charAt(0).toUpperCase() + det.slice(1)
  const pz = item.alemDoPrazo > 0 ? `${item.alemDoPrazo} além` : "no prazo"
  return `${item.classe} — ${FAIXA_NOME[item.faixa].toLowerCase()} (${s.cidOriginal}): ${det}. Espera ${item.diasEmFila} dias (prazo ${item.prazo} dias, ${pz}).`
}

// ---------- 30 dias ----------

function calcularDias(): DiaFila[] {
  const inicio = diaDe(P.meta.start)
  const dias: DiaFila[] = []
  let anterior = new Map<number, number>()
  for (let f = 0; f < P.meta.frames; f++) {
    const dia = inicio + f
    const ativos: (ItemFila & { scoreBruto: number })[] = []
    for (const s of solicitacoes) {
      if (diaDe(s.dataEntrada) > dia) continue
      if (s.dataSaida && diaDe(s.dataSaida) <= dia) continue
      const z = sinais(s, dia)
      const c = classificar(s, z)
      const classe = CLASSES[c]
      const diasEmFila = dia - diaDe(s.dataEntrada)
      const prazo = PRAZO[classe]
      const alem = diasEmFila - prazo
      const grav = gravidade(s, z)
      const espera = 25 * Math.min(Math.max(alem, 0) / prazo, 1) + 15 * Math.min(diasEmFila / 1095, 1)
      const scoreBruto = grav + espera
      ativos.push({
        idx: s.idx,
        posicao: 0,
        posicaoAnterior: null,
        classe,
        faixa: faixaDe(s, z, c),
        score: Math.min(100, Math.floor(scoreBruto + 0.5)),
        gravidade: grav,
        diasEmFila,
        prazo,
        alemDoPrazo: alem,
        scoreBruto,
      })
    }
    ativos.sort((a, b) => {
      const sa = solicitacoes[a.idx], sb = solicitacoes[b.idx]
      return (
        a.faixa - b.faixa ||
        CLASSES.indexOf(a.classe) - CLASSES.indexOf(b.classe) ||
        b.scoreBruto - a.scoreBruto ||
        b.diasEmFila - a.diasEmFila ||
        sb.idade - sa.idade ||
        (sa.sid < sb.sid ? -1 : 1)
      )
    })
    const atual = new Map<number, number>()
    const ordem: ItemFila[] = ativos.map(({ scoreBruto, ...item }, k) => {
      void scoreBruto
      atual.set(item.idx, k + 1)
      return { ...item, posicao: k + 1, posicaoAnterior: f > 0 ? (anterior.get(item.idx) ?? null) : null }
    })
    dias.push({ data: isoDe(dia), ordem })
    anterior = atual
  }
  return dias
}

export const diasFila: DiaFila[] = calcularDias()

/** Posição da solicitação em cada um dos 30 dias (null = fora da fila). */
export function historicoPosicao(idx: number): (number | null)[] {
  return diasFila.map((d) => d.ordem.find((i) => i.idx === idx)?.posicao ?? null)
}

export const diaNumero = diaDe

export const formatarData = (iso: string) => iso.slice(0, 10).split("-").reverse().join("/")
