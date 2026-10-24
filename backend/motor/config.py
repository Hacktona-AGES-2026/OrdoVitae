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
    C.HBA1C_DESCONTROLADA: 1,
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

# --- OrdoScore (0–100): ordena DENTRO da classe ---------------------------------
# OrdoScore = (1 - PESO_PRAZO) * parte clínica  +  PESO_PRAZO * parte de prazo
#   parte clínica: pontos + chance de piora — muda só com achado novo, precisa de aprovação
#   parte de espera: dias na fila / TETO_ESPERA_DIAS — anda sozinha todo dia
# (replay: sem isso, quem esperava 475 dias em A1 escorregou da posição 5 p/ 50
#  porque recém-chegados passavam na frente. Usar "% do prazo da classe" não serve:
#  73% da fila já estourou o prazo, então saturava e virava constante.)
PESO_PRAZO = 0.3
TETO_ESPERA_DIAS = 730  # 2 anos de espera = parte de espera em 100%

# --- Destaque "situação crítica" (só flag para o front; não mexe na ordem) ------
# Paciente grave, no topo, com prazo estourado há muito tempo: o regulador precisa olhar
# o caso (inclusive se a cirurgia ainda faz sentido). Critério a validar com a Fin-x.
CRITICO_CLASSES = {"A1", "A2"}
CRITICO_RAZAO_PRAZO = 3.0   # esperou 3x o prazo da classe ou mais
CRITICO_ORDO_MIN = 85       # OrdoScore final
# P(evento de piora nos próximos 90 dias) | nº de pioras nos últimos 90 dias (0, 1, 2+).
# Gerado por spikes/calibrar_p_piora.py sobre o dataset (dado sintético; n=13 no "2+").
P_PIORA = {0: 0.047, 1: 0.263, 2: 0.385}
JANELA_PIORA_DIAS = 90
TETO_PONTOS = 15        # pontos clínicos >= teto contam como 100%
PESO_CLINICO = 0.6
PESO_PIORA = 0.4
