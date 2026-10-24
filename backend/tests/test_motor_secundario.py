"""Testes unitários do Motor Secundário de Decisão Compartilhada e Adesão."""
import unittest

from motor_secundario import (
    CodigoDecisao,
    NivelAtencaoMedica,
    StatusAdesao,
    avaliar_decisao_compartilhada,
)


class TestMotorSecundarioDecisaoCompartilhada(unittest.TestCase):
    def test_interrupcao_insulina_quebra_adesao(self):
        sol = {
            "solicitacao_id": "SOL-2026-00352",
            "paciente_id": "PAC-00037",
            "cid_principal": "M17.9",
            "justificativa_clinica": "Gonartrose bilateral, dor moderada.",
            "observacoes": "Pct relata que ficou sem insulina na UBS por 1 mes.",
            "comorbidades": "DM2; depressao",
        }
        av = avaliar_decisao_compartilhada(sol)
        self.assertTrue(av.elegivel_decisao_compartilhada)
        self.assertEqual(av.status_adesao, StatusAdesao.QUEBRA_ADESAO)
        self.assertEqual(av.nivel_atencao_maximo, NivelAtencaoMedica.CRITICO)
        codigos = {i.codigo for i in av.itens}
        self.assertIn(CodigoDecisao.INTERRUPCAO_MEDICACAO, codigos)

    def test_tabagismo_mantido_apos_orientacao_medica(self):
        sol = {
            "solicitacao_id": "SOL-2026-00987",
            "paciente_id": "PAC-00505",
            "cid_principal": "M87.0",
            "justificativa_clinica": "Coxartrose direita grau IV. Tabagista ativo, orientado a cessar.",
            "observacoes": "",
            "comorbidades": "tabagismo",
        }
        av = avaliar_decisao_compartilhada(sol)
        self.assertTrue(av.elegivel_decisao_compartilhada)
        codigos = {i.codigo for i in av.itens}
        self.assertIn(CodigoDecisao.TABAGISMO_ATIVO_ORIENTADO, codigos)

    def test_melhora_com_remedio_caso_eletivo_valido(self):
        sol = {
            "solicitacao_id": "SOL-2024-00179",
            "paciente_id": "PAC-00887",
            "cid_principal": "K57.3",
            "justificativa_clinica": "Doenca diverticular sem perfuracao.",
            "observacoes": 'Paciente refere que nao deseja mais operar no momento, "melhorou com remedio".',
            "comorbidades": "DPOC",
        }
        av = avaliar_decisao_compartilhada(sol)
        self.assertTrue(av.elegivel_decisao_compartilhada)
        self.assertFalse(av.tem_conflito_clinico)
        self.assertEqual(av.status_adesao, StatusAdesao.REAVALIAR_INDICACAO)
        item = next(i for i in av.itens if i.codigo == CodigoDecisao.MELHORA_COM_REMEDIO)
        self.assertTrue(item.valido_para_decisao)

    def test_melhora_com_remedio_em_oncologico_gera_conflito_critico(self):
        sol = {
            "solicitacao_id": "SOL-ONCO-001",
            "paciente_id": "PAC-99999",
            "cid_principal": "C18.7",
            "justificativa_clinica": "Adenocarcinoma de sigmoide confirmado.",
            "observacoes": "",
            "comorbidades": "HAS",
        }
        achados_llm = [{"codigo": "MELHORA", "trecho_literal": "Pct refere melhora dos sintomas com tratamento clinico."}]
        av = avaliar_decisao_compartilhada(sol, achados_llm=achados_llm)
        self.assertTrue(av.elegivel_decisao_compartilhada)
        self.assertTrue(av.tem_conflito_clinico)
        self.assertEqual(av.status_adesao, StatusAdesao.CONFLITO_DECISAO)
        item = next(i for i in av.itens if i.codigo == CodigoDecisao.MELHORA_COM_REMEDIO)
        self.assertFalse(item.valido_para_decisao)
        self.assertEqual(item.nivel_atencao, NivelAtencaoMedica.CRITICO)

    def test_pedido_ferias_em_lesao_suspeita_gera_conflito(self):
        sol = {
            "solicitacao_id": "SOL-2025-00006",
            "paciente_id": "PAC-00739",
            "cid_principal": "D44.0",
            "justificativa_clinica": "Nodulo tireoidiano Bethesda III, crescimento no ultimo US.",
            "observacoes": "Paciente pede cirurgia no periodo de ferias.",
            "comorbidades": "depressao",
        }
        av = avaliar_decisao_compartilhada(sol)
        self.assertTrue(av.tem_conflito_clinico)
        item = next(i for i in av.itens if i.codigo == CodigoDecisao.PEDIDO_JANELA_FERIAS)
        self.assertFalse(item.valido_para_decisao)

    def test_adesao_positiva_comprovada(self):
        sol = {
            "solicitacao_id": "SOL-2025-00130",
            "paciente_id": "PAC-00262",
            "cid_principal": "K81.1",
            "justificativa_clinica": "Colelitiase.",
            "observacoes": "HbA1c em queda apos ajuste de medicacao. Endocrino liberou para cirurgia.",
            "comorbidades": "DM2",
        }
        av = avaliar_decisao_compartilhada(sol)
        self.assertTrue(av.elegivel_decisao_compartilhada)
        self.assertEqual(av.status_adesao, StatusAdesao.ADESAO_POSITIVA)
        codigos = {i.codigo for i in av.itens}
        self.assertIn(CodigoDecisao.ADESAO_COMPROVADA, codigos)


if __name__ == "__main__":
    unittest.main()
