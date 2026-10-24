// Contratos da API do backend (backend/api/dtos.py). JSON em camelCase; datas em ISO "AAAA-MM-DD".
// Mantenha este arquivo espelhando os DTOs — é o único lugar que conhece o formato de rede.

export type Classe = "A1" | "A2" | "B" | "C" | "D"

export type SimulacaoDTO = {
  /** Dia atual da simulação. null = nenhum dado recebido ainda. */
  hoje: string | null
  autoAprovar: boolean
}

/**
 * Uma posição da fila. Na fila de hoje todos os campos vêm; nas fotos de dias passados
 * os campos opcionais (scoreClinico… critico) chegam como null.
 */
export type ItemFilaDTO = {
  solicitacaoId: string
  posicao: number
  posicaoAnterior: number | null
  classe: Classe
  score: number
  diasEmFila: number
  prazo: number
  /** Dias além do prazo da classe (0 quando dentro do prazo). */
  alemDoPrazo: number
  scoreClinico: number | null
  ordoClinico: number | null
  risco: number | null
  riscoMotivo: string | null
  asaEstimado: boolean | null
  oncologico: boolean | null
  provisorio: boolean | null
  critico: boolean | null
}

/** Envelope de toda coleção paginada da API. */
export type Pagina<T> = {
  itens: T[]
  total: number
  limite: number
  offset: number
}

export type ResumoFilaDTO = {
  naFila: number
  saltos: number
  foraDoPrazo: number
  criticos: number
}

/** Fila de um dia, paginada: `ordem` é a página; `resumo` e `movimentos` valem para o dia inteiro. */
export type DiaFilaDTO = {
  data: string | null
  ordem: ItemFilaDTO[]
  total: number
  limite: number
  offset: number
  resumo: ResumoFilaDTO
  movimentos: ItemFilaDTO[]
}

export type DimensaoAchado = "gravidade" | "deterioracao" | "alerta"

export type AchadoDTO = {
  codigo: string
  dimensao: DimensaoAchado
  dataFato: string | null
  fonte: string
  ref: string
  trecho: string
  origem: "regra" | "llm"
  confianca: number
}

export type TipoSugestao = "classificacao_inicial" | "subir" | "descer" | "remover" | "alerta"
export type StatusSugestao = "pendente" | "aprovada" | "rejeitada" | "substituida"

export type PreviaDTO = {
  posicaoDe: number | null
  posicaoPara: number | null
  scoreDe: number | null
  scorePara: number | null
}

export type SugestaoDTO = {
  id: number
  solicitacaoId: string
  tipo: TipoSugestao
  status: StatusSugestao
  classeDe: Classe | null
  classePara: Classe | null
  ordoClinicoDe: number | null
  ordoClinicoPara: number | null
  urgente: boolean
  justificativa: string
  motivos: AchadoDTO[]
  criadaEm: string
  decididaEm: string | null
  decididaPor: string
  comentario: string
  /** Só nas pendentes: posição atual → posição se aprovada. */
  previa: PreviaDTO | null
  /** Branch feat/justificativa-comparativa: quantos pacientes ele ultrapassa e por quê. Opcionais até o merge. */
  ultrapassados?: number
  /** Texto final para o regulador (redigido pelo LLM a partir dos fatos; template curto se o LLM falhar). */
  explicacao?: string
  justificativaComparativa?: string
}

export type PosicaoHistoricoDTO = { data: string; posicao: number; score: number }

/** `dados` é a linha da solicitação como recebida (colunas de fila_cirurgica.csv, valores em texto). */
export type DadosSolicitacao = Record<string, string | null | undefined>

export type FichaDTO = {
  solicitacaoId: string
  dados: DadosSolicitacao
  ativa: boolean
  classe: Classe
  ordoClinico: number
  provisorio: boolean
  risco: number
  riscoMotivo: string
  posicao: number | null
  achados: AchadoDTO[]
  historico: PosicaoHistoricoDTO[]
  sugestoes: SugestaoDTO[]
}

export type TipoAlerta =
  | "hba1c_descontrolada"
  | "perda_contato"
  | "dados_insuficientes"
  | "sem_asa"
  | "critico"
  | "prazo_estourado"
  | (string & {})

export type AlertaDTO = {
  /** Pode vir composto ("hba1c_descontrolada,perda_contato") quando a sugestão tem vários motivos. */
  tipo: TipoAlerta
  solicitacaoId: string
  detalhe: string
  sugestaoId: number | null
}

export type ErroDTO = { erro: string; detalhe: string }

// ---------- motor secundário: decisão compartilhada médico–paciente ----------

export type NivelAtencao = "critico" | "moderado" | "informativo" | "nenhum"

export type ItemDecisaoDTO = {
  codigo: string
  categoria: string
  nivelAtencao: NivelAtencao
  titulo: string
  descricaoMedica: string
  recomendacaoConduta: string
  trechoEvidencia: string
  fonte: string
  /** false = a preferência/conduta do paciente conflita com a gravidade clínica. */
  validoParaDecisao: boolean
  conflitoClinico: string
}

/** GET /solicitacoes/{sid}/decisao-compartilhada — calculada com os dados recebidos até `dataReferencia`. */
export type DecisaoCompartilhadaDTO = {
  solicitacaoId: string
  dataReferencia: string | null
  elegivelDecisaoCompartilhada: boolean
  statusAdesao: string
  nivelAtencaoMaximo: NivelAtencao
  temConflitoClinico: boolean
  /** Texto de conclusão para o atendente. */
  resumoMedico: string
  /** Houve achados extraídos por LLM na análise. */
  usouLlm: boolean
  itens: ItemDecisaoDTO[]
}
