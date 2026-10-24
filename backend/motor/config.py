"""Parâmetros do motor. Tudo que é escolha clínica fica aqui, num lugar só.

Valores iniciais definidos pela equipe, ancorados no SWALIS; validar com mentor
e registrar no DECISOES.md.
"""
from .modelos import CodigoAchado as C

# Pontos por achado. Deterioração decai com o tempo (ver MEIA_VIDA_DIAS).
PONTOS: dict[C, float] = {
    # gravidade
    C.CID_MALIGNO: 6,
    C.BIOPSIA_POSITIVA: 6,
    C.CID_URGENTE: 6,
    C.CID_SUSPEITO: 3,
    C.SINAL_ALARME: 3,
    C.DOR_INTENSA: 2,
    C.DOR_MODERADA: 1,
    C.LIMITACAO_GRAVE: 2,
    C.LIMITACAO_MODERADA: 1,
    # deterioração
    C.INTERNACAO: 3,
    C.PROGRESSAO_IMAGEM: 3,
    C.PRONTO_SOCORRO: 2,
    C.REAVALIACAO_PIORA: 2,
    C.PIORA_RELATADA: 1,
    C.MELHORA: -1,
}

# Um evento de deterioração vale metade a cada N dias.
MEIA_VIDA_DIAS = 90

# Classes SWALIS (referencias/swalis.csv): ordem = urgência, prazo em dias.
CLASSES = ["A1", "A2", "B", "C", "D"]
PRAZO_DIAS = {"A1": 15, "A2": 21, "B": 60, "C": 180, "D": 360}

# Limiar mínimo de pontos totais (gravidade + deterioração) para cada classe.
LIMIARES = [("A1", 9), ("A2", 6), ("B", 4), ("C", 2)]  # abaixo de 2 → D

# Pisos (regras que nenhum peso desfaz).
PISO_ONCOLOGICO = "A2"            # CID C* ou biópsia positiva
ONCOLOGICO_EM_PROGRESSAO = "A1"   # oncológico + progressão em imagem
PISO_CID_URGENTE = "A1"
JANELA_PROGRESSAO_DIAS = 180     # progressão "recente" para o piso A1

# Achados que descrevem o MESMO fato: na gravidade conta só o de maior pontuação.
# (spike: CID maligno + biópsia positiva somavam 2x e inflavam a A1 de 110 para 198)
GRUPOS_EXCLUSIVOS = [
    {C.CID_MALIGNO, C.BIOPSIA_POSITIVA, C.CID_SUSPEITO},
    {C.DOR_INTENSA, C.DOR_MODERADA},
    {C.LIMITACAO_GRAVE, C.LIMITACAO_MODERADA},
]

# --- Score clínico (0–100): estado do paciente --------------------------------------
# A fila NÃO agrupa por classe: a classe SWALIS entra como parâmetro do score clínico.
#   estado  = pontos (gravidade + deterioração) + chance de piora  → muda só com achado novo (aprovado)
#   classe  = urgência da classe SWALIS × MULT_CLASSE                → muda só com aprovação
#   espera  = dias na fila, ponderada pela urgência da classe        → anda sozinha todo dia
# (spikes/spike_parametro_classe.py: sem o multiplicador e sem a espera ponderada, 100 dos 177
#  oncológicos ficavam abaixo de pacientes sem urgência que só esperavam muito; com eles, 4.)
W_PONTOS = 0.35
W_PIORA = 0.20
W_CLASSE = 0.25
W_ESPERA = 0.20
MULT_CLASSE = 2.0
URGENCIA_CLASSE = {"A1": 1.0, "A2": 0.8, "B": 0.55, "C": 0.3, "D": 0.0}
ESPERA_PISO = 0.3        # espera vale de 30% (classe D) a 100% (classe A1) do seu peso
TETO_PONTOS = 15         # pontos clínicos >= teto contam como 100%
TETO_ESPERA_DIAS = 730   # 2 anos de espera = parte de espera em 100%

# P(evento de piora nos próximos 90 dias) | nº de pioras nos últimos 90 dias (0, 1, 2+).
# Gerado por spikes/calibrar_p_piora.py sobre o dataset (dado sintético; n=11 no "2+"; sem HbA1c).
P_PIORA = {0: 0.036, 1: 0.300, 2: 0.455}
JANELA_PIORA_DIAS = 90

# --- Score de risco (0–1): risco do paciente × risco do procedimento ---------------
# Matriz do médico da Fin-x. Quanto maior o risco, menos recomendada a cirurgia → desce na fila.
# Paciente = ASA direto (já considera comorbidades). Sem ASA: estimado pelo nº de comorbidades
# (moda no dataset) + alerta. Procedimento = risco_cirurgico de procedimentos.csv.
NIVEL_RISCO = {"baixo": 0.0, "medio": 0.5, "alto": 1.0}
ASA_NIVEL = {1: "baixo", 2: "baixo", 3: "medio", 4: "alto"}
PROCEDIMENTO_NIVEL = {1: "baixo", 2: "baixo", 3: "medio", 4: "alto", 5: "alto"}
ASA_ESTIMADO_POR_COMORBIDADES = {0: 1, 1: 2, 2: 2, 3: 3}  # 4+ → 3
# Ponderação: score final = score clínico × (1 − PESO_RISCO × risco)
# (spikes/spike_risco.py: multiplicar desloca menos que subtrair; 20% mantém o caso da demo no topo)
PESO_RISCO = 0.2

# --- Destaque "situação crítica" (só flag para o front; não mexe na ordem) ------
# Paciente grave, no topo, com prazo estourado há muito tempo: o regulador precisa olhar
# o caso (inclusive se a cirurgia ainda faz sentido). Critério a validar com a Fin-x.
CRITICO_CLASSES = {"A1", "A2"}
CRITICO_RAZAO_PRAZO = 3.0   # esperou 3x o prazo da classe ou mais
CRITICO_SCORE_MIN = 85      # score final
