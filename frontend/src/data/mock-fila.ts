// Dados estáticos de exemplo — substituir pela API quando o backend estiver pronto.
// Inspirado no dicionário de dados da fila cirúrgica (data de referência 23/10/2026).

export type ClasseSwalis = "A1" | "A2" | "B" | "C" | "D"

export const PRAZO_SWALIS: Record<ClasseSwalis, number> = {
  A1: 15,
  A2: 21,
  B: 60,
  C: 180,
  D: 360,
}

export const DESCRICAO_SWALIS: Record<ClasseSwalis, string> = {
  A1: "Risco iminente / malignidade confirmada",
  A2: "Alta urgência, piora documentada",
  B: "Urgência moderada",
  C: "Eletiva com sintomas",
  D: "Eletiva sem limitação",
}

export type Severidade = "critico" | "atencao" | "info"

export type Alerta = {
  label: string
  severidade: Severidade
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

export type Evento = {
  data: string
  tipo: TipoEvento
  resultado: string
  descricao: string
}

export type Solicitacao = {
  solicitacaoId: string
  pacienteId: string
  nome: string
  sexo: "F" | "M"
  idade: number
  municipio: string
  distanciaKm: number | null
  procedimento: string
  especialidade: string
  porte: "pequeno" | "medio" | "grande" | "especial"
  cid: string
  cidDescricao: string
  swalis: ClasseSwalis
  prioridadeManual: "alta" | "media" | "baixa" | null
  score: number
  posicao: number
  posicaoOntem: number
  diasEmFila: number
  dorEva: number | null
  limitacao: "nenhuma" | "leve" | "moderada" | "grave" | null
  comorbidades: string[]
  asa: number | null
  preOp: {
    avaliacaoAnestesica: "realizada" | "pendente" | "vencida"
    examesValidos: boolean
    hba1cControlada: boolean | null
  }
  alertas: Alerta[]
  /** Score de priorização nos últimos 14 dias (mais antigo → hoje). */
  historicoScore: number[]
  /** Série de HbA1c (%), quando houver. */
  hba1c: { data: string; valor: number }[]
  eventos: Evento[]
}

export const DATA_REFERENCIA = "2026-10-23"

export const fila: Solicitacao[] = [
  {
    solicitacaoId: "SOL-2025-00048",
    pacienteId: "PAC-00348",
    nome: "Vera Teixeira Brizola",
    sexo: "F",
    idade: 70,
    municipio: "Porto Alegre",
    distanciaKm: 19,
    procedimento: "Mastectomia / setorectomia de mama",
    especialidade: "Mastologia",
    porte: "medio",
    cid: "C50.4",
    cidDescricao: "Neoplasia maligna do quadrante superior externo da mama",
    swalis: "A1",
    prioridadeManual: "baixa",
    score: 96,
    posicao: 1,
    posicaoOntem: 4,
    diasEmFila: 607,
    dorEva: 2,
    limitacao: "nenhuma",
    comorbidades: ["HAS", "obesidade", "tabagismo", "DPOC"],
    asa: 3,
    preOp: { avaliacaoAnestesica: "realizada", examesValidos: true, hba1cControlada: null },
    alertas: [
      { label: "Biópsia positiva", severidade: "critico" },
      { label: "Prioridade manual divergente", severidade: "atencao" },
      { label: "Relata piora", severidade: "atencao" },
    ],
    historicoScore: [71, 71, 72, 72, 72, 73, 73, 74, 74, 75, 88, 92, 94, 96],
    hba1c: [],
    eventos: [
      { data: "2026-10-20", tipo: "contato_telefonico", resultado: "relata_piora", descricao: "Paciente relata piora de sintomas por telefone." },
      { data: "2026-09-02", tipo: "exame_imagem", resultado: "progressao", descricao: "US mama: aumento da lesão, 2,8 cm." },
      { data: "2025-02-10", tipo: "biopsia", resultado: "positivo", descricao: "Core biopsy: carcinoma ductal invasivo." },
    ],
  },
  {
    solicitacaoId: "SOL-2026-00512",
    pacienteId: "PAC-00731",
    nome: "Ernesto Kunz Dalla Rosa",
    sexo: "M",
    idade: 64,
    municipio: "Santa Maria",
    distanciaKm: 290,
    procedimento: "Colectomia parcial videolaparoscópica",
    especialidade: "Coloproctologia",
    porte: "grande",
    cid: "C18.7",
    cidDescricao: "Neoplasia maligna do cólon sigmoide",
    swalis: "A1",
    prioridadeManual: "alta",
    score: 93,
    posicao: 2,
    posicaoOntem: 1,
    diasEmFila: 34,
    dorEva: 5,
    limitacao: "moderada",
    comorbidades: ["HAS", "DM2"],
    asa: 2,
    preOp: { avaliacaoAnestesica: "pendente", examesValidos: true, hba1cControlada: true },
    alertas: [
      { label: "Prazo SWALIS vencido", severidade: "critico" },
      { label: "Pré-anestésica pendente", severidade: "atencao" },
      { label: "Mora a 290 km", severidade: "info" },
    ],
    historicoScore: [90, 90, 91, 91, 91, 92, 92, 92, 93, 93, 93, 93, 93, 93],
    hba1c: [
      { data: "2026-02", valor: 7.4 },
      { data: "2026-05", valor: 7.1 },
      { data: "2026-08", valor: 6.9 },
    ],
    eventos: [
      { data: "2026-10-15", tipo: "falta", resultado: "avaliacao_pre_anestesica", descricao: "Não compareceu — sem transporte." },
      { data: "2026-09-19", tipo: "biopsia", resultado: "positivo", descricao: "AP: adenocarcinoma moderadamente diferenciado." },
    ],
  },
  {
    solicitacaoId: "SOL-2025-00504",
    pacienteId: "PAC-00211",
    nome: "Camila Bitencourt Prestes",
    sexo: "F",
    idade: 52,
    municipio: "Porto Alegre",
    distanciaKm: 23,
    procedimento: "Safenectomia / tratamento cirúrgico de varizes",
    especialidade: "Cirurgia Vascular",
    porte: "medio",
    cid: "I83.1",
    cidDescricao: "Varizes dos membros inferiores com inflamação",
    swalis: "A2",
    prioridadeManual: "alta",
    score: 84,
    posicao: 3,
    posicaoOntem: 3,
    diasEmFila: 301,
    dorEva: 6,
    limitacao: "grave",
    comorbidades: ["obesidade"],
    asa: 2,
    preOp: { avaliacaoAnestesica: "pendente", examesValidos: false, hba1cControlada: null },
    alertas: [
      { label: "Internação recente (UPA)", severidade: "critico" },
      { label: "Tromboflebite recorrente", severidade: "atencao" },
      { label: "Exames pré-op vencidos", severidade: "atencao" },
    ],
    historicoScore: [70, 70, 71, 71, 76, 76, 77, 77, 78, 82, 83, 83, 84, 84],
    hba1c: [],
    eventos: [
      { data: "2026-10-11", tipo: "internacao", resultado: "alta", descricao: "Internação por tromboflebite — 4 dias." },
      { data: "2026-09-28", tipo: "pronto_socorro", resultado: "observacao", descricao: "UPA Zona Norte: dor e edema em MIE." },
      { data: "2026-06-14", tipo: "pronto_socorro", resultado: "atendido_liberado", descricao: "UPA Zona Norte: dor em MMII." },
    ],
  },
  {
    solicitacaoId: "SOL-2025-00412",
    pacienteId: "PAC-00638",
    nome: "Marlene Lopes Fontoura",
    sexo: "F",
    idade: 50,
    municipio: "Camaquã",
    distanciaKm: 129,
    procedimento: "Mastectomia / setorectomia de mama",
    especialidade: "Mastologia",
    porte: "medio",
    cid: "D48.6",
    cidDescricao: "Neoplasia de comportamento incerto da mama",
    swalis: "A2",
    prioridadeManual: "media",
    score: 79,
    posicao: 4,
    posicaoOntem: 2,
    diasEmFila: 337,
    dorEva: 3,
    limitacao: "nenhuma",
    comorbidades: ["DM2", "tabagismo", "DPOC", "depressão"],
    asa: 3,
    preOp: { avaliacaoAnestesica: "pendente", examesValidos: true, hba1cControlada: false },
    alertas: [
      { label: "HbA1c 10,1% — descontrolada", severidade: "critico" },
      { label: "BI-RADS 5", severidade: "atencao" },
    ],
    historicoScore: [82, 82, 82, 83, 83, 83, 83, 84, 84, 84, 84, 80, 79, 79],
    hba1c: [
      { data: "2025-11", valor: 8.1 },
      { data: "2026-02", valor: 8.6 },
      { data: "2026-05", valor: 9.4 },
      { data: "2026-08", valor: 10.1 },
    ],
    eventos: [
      { data: "2026-08-14", tipo: "hba1c", resultado: "resultado", descricao: "HbA1c 10,1% — encaminhada à endocrinologia." },
      { data: "2026-05-30", tipo: "contato_telefonico", resultado: "atendeu", descricao: "Confirma interesse em operar." },
    ],
  },
  {
    solicitacaoId: "SOL-2026-00673",
    pacienteId: "PAC-00177",
    nome: "José Pires Teixeira",
    sexo: "M",
    idade: 83,
    municipio: "Porto Alegre",
    distanciaKm: 16,
    procedimento: "Ressecção transuretral de próstata (RTU)",
    especialidade: "Urologia",
    porte: "medio",
    cid: "N40",
    cidDescricao: "Hiperplasia da próstata",
    swalis: "B",
    prioridadeManual: "alta",
    score: 62,
    posicao: 5,
    posicaoOntem: 5,
    diasEmFila: 91,
    dorEva: 1,
    limitacao: "leve",
    comorbidades: ["DM2", "ICC", "fibrilação atrial"],
    asa: 3,
    preOp: { avaliacaoAnestesica: "realizada", examesValidos: true, hba1cControlada: true },
    alertas: [
      { label: "Prazo SWALIS vencido", severidade: "atencao" },
      { label: "ICC + FA", severidade: "info" },
    ],
    historicoScore: [58, 58, 59, 59, 59, 60, 60, 60, 61, 61, 61, 62, 62, 62],
    hba1c: [
      { data: "2026-03", valor: 7.0 },
      { data: "2026-07", valor: 7.2 },
    ],
    eventos: [
      { data: "2026-09-30", tipo: "consulta_reavaliacao", resultado: "estavel", descricao: "IPSS 24, mantém sintomas obstrutivos." },
    ],
  },
  {
    solicitacaoId: "SOL-2026-00348",
    pacienteId: "PAC-00674",
    nome: "Arlindo Schneider Medeiros",
    sexo: "M",
    idade: 51,
    municipio: "Porto Alegre",
    distanciaKm: 8,
    procedimento: "Safenectomia / tratamento cirúrgico de varizes",
    especialidade: "Cirurgia Vascular",
    porte: "medio",
    cid: "I83.9",
    cidDescricao: "Varizes dos membros inferiores sem úlcera ou inflamação",
    swalis: "C",
    prioridadeManual: "baixa",
    score: 41,
    posicao: 6,
    posicaoOntem: 7,
    diasEmFila: 180,
    dorEva: 4,
    limitacao: "moderada",
    comorbidades: ["DM2", "tabagismo"],
    asa: 2,
    preOp: { avaliacaoAnestesica: "realizada", examesValidos: false, hba1cControlada: true },
    alertas: [{ label: "Exames pré-op vencidos", severidade: "atencao" }],
    historicoScore: [36, 36, 37, 37, 37, 38, 38, 38, 39, 39, 40, 40, 41, 41],
    hba1c: [
      { data: "2025-12", valor: 7.1 },
      { data: "2026-02", valor: 6.6 },
    ],
    eventos: [
      { data: "2026-07-05", tipo: "consulta_reavaliacao", resultado: "estavel", descricao: "CEAP C2. Dor e edema, sem melhora clínica." },
    ],
  },
  {
    solicitacaoId: "SOL-2024-00219",
    pacienteId: "PAC-00090",
    nome: "Iracema Fagundes Lopes",
    sexo: "F",
    idade: 67,
    municipio: "Pelotas",
    distanciaKm: 250,
    procedimento: "Facectomia com implante de LIO",
    especialidade: "Oftalmologia",
    porte: "pequeno",
    cid: "H25.1",
    cidDescricao: "Catarata senil nuclear",
    swalis: "C",
    prioridadeManual: null,
    score: 38,
    posicao: 7,
    posicaoOntem: 6,
    diasEmFila: 712,
    dorEva: 0,
    limitacao: "moderada",
    comorbidades: ["HAS"],
    asa: 2,
    preOp: { avaliacaoAnestesica: "vencida", examesValidos: false, hba1cControlada: null },
    alertas: [
      { label: "3 contatos sem resposta", severidade: "atencao" },
      { label: "Sem prioridade cadastrada", severidade: "info" },
    ],
    historicoScore: [40, 40, 40, 40, 39, 39, 39, 39, 39, 38, 38, 38, 38, 38],
    hba1c: [],
    eventos: [
      { data: "2026-10-02", tipo: "contato_telefonico", resultado: "nao_atendeu", descricao: "Não atendeu (3ª tentativa)." },
      { data: "2026-08-21", tipo: "contato_telefonico", resultado: "nao_atendeu", descricao: "Não atendeu." },
    ],
  },
  {
    solicitacaoId: "SOL-2026-00801",
    pacienteId: "PAC-00512",
    nome: "Paulo Henrique Zanella",
    sexo: "M",
    idade: 38,
    municipio: "Canoas",
    distanciaKm: 21,
    procedimento: "Herniorrafia inguinal",
    especialidade: "Cirurgia Geral",
    porte: "pequeno",
    cid: "K40.9",
    cidDescricao: "Hérnia inguinal unilateral sem obstrução ou gangrena",
    swalis: "D",
    prioridadeManual: "media",
    score: 22,
    posicao: 8,
    posicaoOntem: 8,
    diasEmFila: 46,
    dorEva: 2,
    limitacao: "leve",
    comorbidades: [],
    asa: 1,
    preOp: { avaliacaoAnestesica: "realizada", examesValidos: true, hba1cControlada: null },
    alertas: [],
    historicoScore: [21, 21, 21, 21, 21, 21, 22, 22, 22, 22, 22, 22, 22, 22],
    hba1c: [],
    eventos: [
      { data: "2026-09-08", tipo: "contato_telefonico", resultado: "atendeu", descricao: "Mantém desejo de operar." },
    ],
  },
]

/** Entradas e saídas da fila nos últimos 14 dias (para o gráfico de movimento). */
export const movimentoFila = [
  { dia: "10/10", entradas: 9, saidas: 6 },
  { dia: "11/10", entradas: 4, saidas: 2 },
  { dia: "12/10", entradas: 2, saidas: 0 },
  { dia: "13/10", entradas: 11, saidas: 7 },
  { dia: "14/10", entradas: 8, saidas: 9 },
  { dia: "15/10", entradas: 12, saidas: 8 },
  { dia: "16/10", entradas: 7, saidas: 10 },
  { dia: "17/10", entradas: 10, saidas: 6 },
  { dia: "18/10", entradas: 3, saidas: 1 },
  { dia: "19/10", entradas: 1, saidas: 0 },
  { dia: "20/10", entradas: 13, saidas: 9 },
  { dia: "21/10", entradas: 9, saidas: 11 },
  { dia: "22/10", entradas: 8, saidas: 7 },
  { dia: "23/10", entradas: 10, saidas: 8 },
]

/** Distribuição da fila inteira (941 solicitações) por classe SWALIS. */
export const distribuicaoSwalis: { classe: ClasseSwalis; total: number; vencidos: number }[] = [
  { classe: "A1", total: 38, vencidos: 21 },
  { classe: "A2", total: 74, vencidos: 40 },
  { classe: "B", total: 196, vencidos: 88 },
  { classe: "C", total: 382, vencidos: 103 },
  { classe: "D", total: 251, vencidos: 12 },
]
