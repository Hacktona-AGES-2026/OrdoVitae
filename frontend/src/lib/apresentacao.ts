// Adaptadores DTO → tela: rótulos em português, normalização dos campos em texto da ficha
// e utilitários de data da timeline. Nenhum componente deve ler `ficha.dados` direto.

import type { AchadoDTO, Classe, DadosSolicitacao, FichaDTO, ItemFilaDTO, SugestaoDTO, TipoSugestao } from "@/api/tipos"

export const CLASSES: Classe[] = ["A1", "A2", "B", "C", "D"]

export const PRAZO_CLASSE: Record<Classe, number> = { A1: 15, A2: 21, B: 60, C: 180, D: 360 }

export const DESCRICAO_CLASSE: Record<Classe, string> = {
  A1: "Progressão rápida, risco de vida ou de perda de órgão/função",
  A2: "Progressão rápida, risco de agravamento ou incapacidade",
  B: "Dor, disfunção ou incapacidade importantes",
  C: "Dor ou disfunção moderadas, sem tendência a agravar",
  D: "Sem dor, disfunção ou incapacidade relevantes",
}

export const TIPO_SUGESTAO_LABEL: Record<TipoSugestao, string> = {
  classificacao_inicial: "Classificação inicial",
  subir: "Subir prioridade",
  descer: "Descer prioridade",
  remover: "Remover da fila",
  alerta: "Alerta",
}

const ACHADO_LABEL: Record<string, string> = {
  CID_MALIGNO: "CID maligno",
  CID_SUSPEITO: "CID suspeito",
  CID_URGENTE: "CID de urgência",
  BIOPSIA_POSITIVA: "Biópsia positiva",
  SINAL_ALARME: "Sinal de alarme",
  DOR_INTENSA: "Dor intensa",
  DOR_MODERADA: "Dor moderada",
  LIMITACAO_GRAVE: "Limitação grave",
  LIMITACAO_MODERADA: "Limitação moderada",
  INTERNACAO: "Internação",
  PRONTO_SOCORRO: "Pronto-socorro",
  PROGRESSAO_IMAGEM: "Progressão em imagem",
  REAVALIACAO_PIORA: "Piora na reavaliação",
  PIORA_RELATADA: "Piora relatada",
  MELHORA: "Melhora",
  HBA1C_DESCONTROLADA: "HbA1c descontrolada",
  PERDA_CONTATO: "Perda de contato",
  SAIU_DA_FILA: "Saiu da fila",
  OTIMIZAR_CLINICAMENTE: "Otimizar clinicamente",
  DADOS_INSUFICIENTES: "Dados insuficientes",
}

export const rotuloAchado = (codigo: string) =>
  ACHADO_LABEL[codigo] ?? codigo.toLowerCase().replace(/_/g, " ").replace(/^./, (c) => c.toUpperCase())

const ALERTA_LABEL: Record<string, string> = {
  hba1c_descontrolada: "HbA1c descontrolada",
  perda_contato: "Perda de contato",
  dados_insuficientes: "Dados insuficientes",
  sem_asa: "Sem ASA",
  critico: "Situação crítica",
  prazo_estourado: "Prazo estourado",
  otimizar_clinicamente: "Otimizar clinicamente",
  saiu_da_fila: "Saiu da fila",
}

/** O tipo de alerta pode vir composto: "hba1c_descontrolada,perda_contato". */
export const rotulosAlerta = (tipo: string) => tipo.split(",").map((t) => ALERTA_LABEL[t] ?? t.replace(/_/g, " "))

export const FONTE_LABEL: Record<string, string> = {
  solicitacao: "Solicitação",
  evento: "Evento",
  observacao: "Observação",
}

/** Achado DADOS_INSUFICIENTES (justificativa clínica pobre) já conhecido no dia exibido. */
export function temDadosInsuficientes(f: FichaDTO | undefined, data: string) {
  return !!f?.achados.some((a) => a.codigo === "DADOS_INSUFICIENTES" && (!a.dataFato || a.dataFato <= data))
}

/** Achado que indica piora/gravidade (vermelho) ou só alerta (âmbar). */
export const achadoGrave = (a: AchadoDTO) => a.dimensao !== "alerta" && a.codigo !== "MELHORA"

// ---------- ficha → paciente ----------

export type Paciente = {
  sid: string
  pacienteId: string
  nome: string
  sexo: string
  idade: number | null
  municipio: string
  distanciaKm: number | null
  procedimento: string
  especialidade: string
  cid: string
  cidDescricao: string
  dor: number | null
  limitacao: string
  asa: string
  comorbidades: string
  justificativa: string
  observacoes: string
  dataEntrada: string
  prioridadeManual: string
}

const txt = (d: DadosSolicitacao, k: string) => (d[k] ?? "").toString().trim()
const num = (d: DadosSolicitacao, k: string) => {
  const v = txt(d, k).replace(",", ".")
  return v === "" || Number.isNaN(Number(v)) ? null : Number(v)
}

export function paciente(f: FichaDTO): Paciente {
  const d = f.dados
  return {
    sid: f.solicitacaoId,
    pacienteId: txt(d, "paciente_id"),
    nome: txt(d, "nome_paciente") || f.solicitacaoId,
    sexo: txt(d, "sexo").toUpperCase(),
    idade: num(d, "idade"),
    municipio: tituloCaixa(txt(d, "municipio")),
    distanciaKm: num(d, "distancia_hospital_km"),
    procedimento: txt(d, "procedimento"),
    especialidade: txt(d, "especialidade"),
    cid: formatarCid(txt(d, "cid_principal")),
    cidDescricao: txt(d, "cid_descricao"),
    dor: num(d, "intensidade_dor_eva"),
    limitacao: txt(d, "limitacao_funcional").toLowerCase(),
    asa: txt(d, "asa"),
    comorbidades: txt(d, "comorbidades"),
    justificativa: txt(d, "justificativa_clinica"),
    observacoes: txt(d, "observacoes"),
    dataEntrada: txt(d, "data_entrada_fila"),
    prioridadeManual: txt(d, "prioridade_regulacao").toLowerCase(),
  }
}

const MINUSCULAS = new Set(["de", "da", "do", "das", "dos", "e"])

/** Município chega com caixa inconsistente ("PELOTAS", "porto alegre"). */
export function tituloCaixa(t: string) {
  return t
    .toLowerCase()
    .split(/\s+/)
    .map((p, i) => (i > 0 && MINUSCULAS.has(p) ? p : p.charAt(0).toUpperCase() + p.slice(1)))
    .join(" ")
}

/** CID chega com ou sem ponto ("K409" / "K40.9"); exibe sempre com ponto. */
export function formatarCid(cid: string) {
  const c = cid.replace(/[.\s]/g, "").toUpperCase()
  return c.length > 3 ? `${c.slice(0, 3)}.${c.slice(3)}` : c
}

// ---------- fila ----------

export type Movimento = { tipo: "primeiro" | "nova" | "subiu" | "desceu" | "estavel"; delta: number }

/** Até 4 posições é "arrasto" da fila (outros entram/saem); a partir de 5 é movimento real. */
export const LIMIAR_SALTO = 5

export function movimento(item: ItemFilaDTO, primeiroDia: boolean): Movimento {
  if (primeiroDia) return { tipo: "primeiro", delta: 0 }
  if (item.posicaoAnterior === null) return { tipo: "nova", delta: 0 }
  const d = item.posicaoAnterior - item.posicao
  if (d >= LIMIAR_SALTO) return { tipo: "subiu", delta: d }
  if (d <= -LIMIAR_SALTO) return { tipo: "desceu", delta: -d }
  return { tipo: "estavel", delta: Math.abs(d) }
}

/** Sugestões que mexem na fila e são decididas pelo regulador. */
export const sugestaoDeMudanca = (s: SugestaoDTO) => s.tipo !== "classificacao_inicial"

// ---------- datas ----------

const DIA_MS = 86_400_000

export const formatarData = (iso: string) => iso.slice(0, 10).split("-").reverse().join("/")
export const formatarDataCurta = (iso: string) => formatarData(iso).slice(0, 5)

export function somarDias(iso: string, dias: number) {
  return new Date(Date.parse(iso + "T00:00:00Z") + dias * DIA_MS).toISOString().slice(0, 10)
}

/** Datas da timeline: os `n` dias até `hoje`, inclusive. */
export function diasDaTimeline(hoje: string, n: number) {
  return Array.from({ length: n }, (_, i) => somarDias(hoje, i - (n - 1)))
}

export const formatarScore = (v: number | null | undefined) =>
  v == null ? "–" : v.toLocaleString("pt-BR", { maximumFractionDigits: 1 })
