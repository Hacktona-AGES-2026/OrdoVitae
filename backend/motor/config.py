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
