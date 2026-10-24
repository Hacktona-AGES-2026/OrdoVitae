import unittest
from datetime import date

from motor import ItemFila, avaliar, decidir, ordenar
from motor.modelos import Achado, CodigoAchado as C, Dimensao as D, Evidencia, Origem, TipoSugestao

REF = date(2026, 10, 23)
ENTRADA = date(2025, 5, 30)


def achado(codigo, dim, data=None, sol="SOL-1", ref="EVT-1", origem=Origem.REGRA):
    return Achado(codigo, dim, sol, data, Evidencia("evento", ref), origem)


class TestAvaliacao(unittest.TestCase):
    def test_hernia_sem_sintomas_e_D(self):
        av = avaliar("SOL-1", [], REF, ENTRADA)
        self.assertEqual(av.classe, "D")

    def test_oncologico_tem_piso_A2(self):
        av = avaliar("SOL-1", [achado(C.CID_MALIGNO, D.GRAVIDADE)], REF, ENTRADA)
        self.assertEqual(av.classe, "A2")

    def test_oncologico_em_progressao_vira_A1(self):
        av = avaliar("SOL-1", [
            achado(C.CID_MALIGNO, D.GRAVIDADE),
            achado(C.PROGRESSAO_IMAGEM, D.DETERIORACAO, date(2026, 10, 10)),
        ], REF, ENTRADA)
        self.assertEqual(av.classe, "A1")
        self.assertIn("progressão", av.motivo_classe)

    def test_deterioracao_decai_com_o_tempo(self):
        recente = avaliar("SOL-1", [achado(C.INTERNACAO, D.DETERIORACAO, date(2026, 10, 16))], REF, ENTRADA)
        antiga = avaliar("SOL-1", [achado(C.INTERNACAO, D.DETERIORACAO, date(2025, 10, 16))], REF, ENTRADA)
        self.assertGreater(recente.deterioracao, antiga.deterioracao)

    def test_evento_futuro_ignorado(self):
        av = avaliar("SOL-1", [achado(C.INTERNACAO, D.DETERIORACAO, date(2027, 1, 1))], REF, ENTRADA)
        self.assertEqual(av.deterioracao, 0)

    def test_llm_sem_data_nao_duplica_regra(self):
        av = avaliar("SOL-1", [
            achado(C.PRONTO_SOCORRO, D.DETERIORACAO, date(2026, 10, 1)),
            achado(C.PRONTO_SOCORRO, D.DETERIORACAO, None, ref="SOL-1:justificativa_clinica", origem=Origem.LLM),
        ], REF, ENTRADA)
        self.assertEqual(len(av.contribuicoes), 1)


class TestDecisor(unittest.TestCase):
    def test_sugere_subir_com_justificativa(self):
        av = avaliar("SOL-1", [achado(C.CID_MALIGNO, D.GRAVIDADE)], REF, ENTRADA)
        [s] = decidir(av, classe_aprovada="D")
        self.assertEqual(s.tipo, TipoSugestao.SUBIR)
        self.assertEqual((s.classe_de, s.classe_para), ("D", "A2"))
        self.assertTrue(s.urgente)
        self.assertIn("CID_MALIGNO", s.justificativa)

    def test_sem_mudanca_sem_sugestao(self):
        av = avaliar("SOL-1", [], REF, ENTRADA)
        self.assertEqual(decidir(av, classe_aprovada="D"), [])

    def test_saida_da_fila_sugere_remover(self):
        av = avaliar("SOL-1", [achado(C.SAIU_DA_FILA, D.ALERTA, date(2026, 9, 9))], REF, ENTRADA)
        tipos = [s.tipo for s in decidir(av, classe_aprovada="C")]
        self.assertIn(TipoSugestao.REMOVER, tipos)


class TestFila(unittest.TestCase):
    def test_classe_antes_do_tempo(self):
        fila = ordenar([
            ItemFila("ANTIGO", "D", date(2022, 1, 1), False, True),
            ItemFila("ONCO", "A2", date(2026, 10, 1), True, False),
        ], REF)
        self.assertEqual([i.solicitacao_id for i in fila], ["ONCO", "ANTIGO"])

    def test_regra_de_ouro_trava_mesmo_com_classe_errada(self):
        fila = ordenar([
            ItemFila("CALMO", "C", date(2024, 1, 1), False, True),
            ItemFila("ONCO_ERRADO", "D", date(2026, 1, 1), True, False),
        ], REF)
        self.assertEqual(fila[0].solicitacao_id, "ONCO_ERRADO")


if __name__ == "__main__":
    unittest.main()
