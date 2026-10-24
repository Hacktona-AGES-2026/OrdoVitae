import unittest
from datetime import date

from motor import EstadoAprovado, ItemFila, avaliar, critico, decidir, ordenar, prazos_estourados, prever_posicoes
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

    def test_cid_maligno_e_biopsia_nao_somam_duas_vezes(self):
        so_cid = avaliar("SOL-1", [achado(C.CID_MALIGNO, D.GRAVIDADE)], REF, ENTRADA)
        os_dois = avaliar("SOL-1", [achado(C.CID_MALIGNO, D.GRAVIDADE),
                                    achado(C.BIOPSIA_POSITIVA, D.GRAVIDADE, date(2025, 5, 1), ref="EVT-2")], REF, ENTRADA)
        self.assertEqual(so_cid.gravidade, os_dois.gravidade)
        self.assertEqual(os_dois.classe, "A2")

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

    def test_piora_recente_aumenta_p_piora_e_ordo_clinico(self):
        sem = avaliar("SOL-1", [], REF, ENTRADA)
        com = avaliar("SOL-1", [achado(C.PRONTO_SOCORRO, D.DETERIORACAO, date(2026, 10, 1))], REF, ENTRADA)
        self.assertGreater(com.p_piora, sem.p_piora)
        self.assertGreater(com.ordo_clinico, sem.ordo_clinico)
        self.assertTrue(0 <= sem.ordo_clinico <= 100 and 0 <= com.ordo_clinico <= 100)

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
    def test_achado_novo_que_muda_classe_sugere_subir(self):
        novo = achado(C.CID_MALIGNO, D.GRAVIDADE)
        av = avaliar("SOL-1", [novo], REF, ENTRADA)
        [s] = decidir(av, EstadoAprovado("D", 10.0), [novo])
        self.assertEqual(s.tipo, TipoSugestao.SUBIR)
        self.assertEqual((s.classe_de, s.classe_para), ("D", "A2"))
        self.assertEqual(s.ordo_clinico_de, 10.0)
        self.assertTrue(s.urgente)
        self.assertIn("CID_MALIGNO", s.justificativa)

    def test_achado_novo_mesma_classe_muda_ordo_clinico(self):
        novo = achado(C.PIORA_RELATADA, D.DETERIORACAO, date(2026, 10, 20))
        av = avaliar("SOL-1", [novo], REF, ENTRADA)
        [s] = decidir(av, EstadoAprovado(av.classe, 0.0), [novo])
        self.assertEqual(s.tipo, TipoSugestao.SUBIR)
        self.assertEqual(s.classe_de, s.classe_para)

    def test_sem_achado_novo_sem_sugestao(self):
        """O tempo passando não gera sugestão sozinho."""
        av = avaliar("SOL-1", [achado(C.INTERNACAO, D.DETERIORACAO, date(2026, 1, 1))], REF, ENTRADA)
        self.assertEqual(decidir(av, EstadoAprovado("A1", 99.0), []), [])

    def test_saida_da_fila_sugere_remover(self):
        novo = achado(C.SAIU_DA_FILA, D.ALERTA, date(2026, 9, 9))
        av = avaliar("SOL-1", [novo], REF, ENTRADA)
        tipos = [s.tipo for s in decidir(av, EstadoAprovado("C", 20.0), [novo])]
        self.assertIn(TipoSugestao.REMOVER, tipos)


class TestFila(unittest.TestCase):
    def test_classe_antes_do_tempo(self):
        fila = ordenar([
            ItemFila("ANTIGO", "D", 0, date(2022, 1, 1), False, True),
            ItemFila("ONCO", "A2", 40, date(2026, 10, 1), True, False),
        ], REF)
        self.assertEqual([i.solicitacao_id for i in fila], ["ONCO", "ANTIGO"])

    def test_ordo_score_ordena_dentro_da_classe(self):
        fila = ordenar([
            ItemFila("ANTIGO", "B", 30, date(2022, 1, 1), False, False),
            ItemFila("PIORANDO", "B", 90, date(2026, 10, 1), False, False),
        ], REF)
        self.assertEqual(fila[0].solicitacao_id, "PIORANDO")

    def test_regra_de_ouro_trava_mesmo_com_classe_errada(self):
        fila = ordenar([
            ItemFila("CALMO", "C", 10, date(2024, 1, 1), False, True),
            ItemFila("ONCO_ERRADO", "D", 0, date(2026, 1, 1), True, False),
        ], REF)
        self.assertEqual(fila[0].solicitacao_id, "ONCO_ERRADO")

    def test_previa_de_posicao(self):
        fila = ordenar([
            ItemFila("X", "B", 50, date(2024, 1, 1), False, False),
            ItemFila("Y", "C", 20, date(2024, 1, 1), False, False),
            ItemFila("JOAO", "D", 5, date(2024, 1, 1), False, True),
        ], REF)
        novo = achado(C.CID_MALIGNO, D.GRAVIDADE, sol="JOAO")
        av = avaliar("JOAO", [novo], REF, ENTRADA)
        [s] = decidir(av, EstadoAprovado("D", 5), [novo])
        prever_posicoes(fila, [s], REF)
        self.assertEqual((s.posicao_de, s.posicao_para), (3, 1))
        self.assertEqual([i.posicao for i in fila], [1, 2, 3])  # fila oficial intacta
        self.assertGreater(s.ordo_para, s.ordo_de)

    def test_quem_espera_ganha_de_recem_chegado_com_score_parecido(self):
        fila = ordenar([
            ItemFila("NOVO", "A1", 50, date(2026, 10, 20), False, False),
            ItemFila("ESPERANDO_HA_1_ANO", "A1", 45, date(2025, 10, 1), False, False),
        ], REF)
        self.assertEqual(fila[0].solicitacao_id, "ESPERANDO_HA_1_ANO")

    def test_critico_so_para_grave_estourado_e_score_alto(self):
        grave_antigo = ItemFila("G", "A1", 100, date(2025, 1, 1), True, False)
        grave_recente = ItemFila("R", "A1", 100, date(2026, 10, 20), True, False)
        leve_antigo = ItemFila("L", "D", 0, date(2022, 1, 1), False, True)
        self.assertEqual([critico(i, REF) for i in (grave_antigo, grave_recente, leve_antigo)], [True, False, False])

    def test_prazo_estourado(self):
        itens = [ItemFila("A", "A1", 50, date(2025, 10, 1), False, False),
                 ItemFila("B", "D", 0, date(2026, 10, 1), False, True)]
        self.assertEqual([i.solicitacao_id for i in prazos_estourados(itens, REF)], ["A"])


if __name__ == "__main__":
    unittest.main()
