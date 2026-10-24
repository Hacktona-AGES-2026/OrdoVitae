import sqlite3
import unittest
from datetime import date
from pathlib import Path

from extracao import extrair_evento, extrair_solicitacao
from motor.modelos import CodigoAchado as C, Dimensao as D, Origem


class TestExtracaoRegras(unittest.TestCase):
    def test_solicitacao_oncologica_cid(self):
        sol = {
            "solicitacao_id": "SOL-1",
            "data_entrada_fila": "2026-05-10",
            "cid_principal": "C50.4",
            "intensidade_dor_eva": 2,
            "limitacao_funcional": "nenhuma",
            "justificativa_clinica": "Nódulo mamário suspeito com biópsia prévia demonstrando neoplasia.",
        }
        achados = extrair_solicitacao(sol)
        codigos = [a.codigo for a in achados]
        self.assertIn(C.CID_MALIGNO, codigos)
        achado_onco = next(a for a in achados if a.codigo == C.CID_MALIGNO)
        self.assertEqual(achado_onco.dimensao, D.GRAVIDADE)
        self.assertEqual(achado_onco.data_fato, date(2026, 5, 10))
        self.assertEqual(achado_onco.evidencia.ref, "SOL-1:cid_principal")

    def test_solicitacao_dor_e_limitacao(self):
        sol = {
            "solicitacao_id": "SOL-2",
            "data_entrada_fila": "2026-06-01",
            "cid_principal": "K409",
            "intensidade_dor_eva": 8,
            "limitacao_funcional": "grave",
            "justificativa_clinica": "Paciente com dor limitante em região inguinal e limitação grave.",
        }
        achados = extrair_solicitacao(sol)
        codigos = [a.codigo for a in achados]
        self.assertIn(C.DOR_INTENSA, codigos)
        self.assertIn(C.LIMITACAO_GRAVE, codigos)

    def test_solicitacao_alarme_e_dados_insuficientes(self):
        sol = {
            "solicitacao_id": "SOL-3",
            "data_entrada_fila": "2026-07-01",
            "cid_principal": "K802",
            "justificativa_clinica": "ictericia e perda ponderal",
        }
        achados = extrair_solicitacao(sol)
        codigos = [a.codigo for a in achados]
        self.assertIn(C.DADOS_INSUFICIENTES, codigos)  # < 30 chars
        self.assertIn(C.SINAL_ALARME, codigos)

    def test_negacao_sem_sinais_de_encarceramento(self):
        # Os "sem sinais de encarceramento" não podem virar SINAL_ALARME
        sol = {
            "solicitacao_id": "SOL-TEST-NEG",
            "data_entrada_fila": "2026-07-01",
            "cid_principal": "K409",
            "justificativa_clinica": "Hernia inguinal bilateral redutivel, abaulamento aos esforcos. Sem sinais de encarceramento.",
        }
        achados = extrair_solicitacao(sol)
        codigos = [a.codigo for a in achados]
        self.assertNotIn(C.SINAL_ALARME, codigos)

    def test_angina_instavel_internacao_recente(self):
        # "Angina instável, internação recente" precisa gerar achado
        sol = {
            "solicitacao_id": "SOL-TEST-ANGINA",
            "data_entrada_fila": "2026-07-01",
            "cid_principal": "I200",
            "justificativa_clinica": "Angina instavel, internacao recente, lesao de tronco de coronaria esquerda. Cirurgia com prioridade.",
        }
        achados = extrair_solicitacao(sol)
        codigos = [a.codigo for a in achados]
        self.assertIn(C.CID_URGENTE, codigos)
        self.assertIn(C.SINAL_ALARME, codigos)
        self.assertIn(C.INTERNACAO, codigos)

    def test_evento_biopsia_positiva(self):
        ev = {
            "evento_id": "EVT-1",
            "solicitacao_id": "SOL-1",
            "data_evento": "2026-08-15",
            "tipo_evento": "biopsia",
            "resultado": "positivo",
            "descricao": "AP confirma carcinoma ductal invasivo.",
        }
        achados = extrair_evento(ev)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].codigo, C.BIOPSIA_POSITIVA)
        self.assertEqual(achados[0].dimensao, D.GRAVIDADE)
        self.assertEqual(achados[0].data_fato, date(2026, 8, 15))

    def test_evento_hba1c_descontrolada(self):
        ev = {
            "evento_id": "EVT-2",
            "solicitacao_id": "SOL-1",
            "data_evento": "2026-09-01",
            "tipo_evento": "hba1c",
            "valor_numerico": 9.2,
            "descricao": "HbA1c 9.2%",
        }
        achados = extrair_evento(ev)
        codigos = [a.codigo for a in achados]
        self.assertIn(C.HBA1C_DESCONTROLADA, codigos)
        self.assertIn(C.OTIMIZAR_CLINICAMENTE, codigos)

    def test_evento_saida_da_fila(self):
        ev = {
            "evento_id": "EVT-3",
            "solicitacao_id": "SOL-1",
            "data_evento": "2026-09-10",
            "tipo_evento": "contato_telefonico",
            "resultado": "desistiu",
            "descricao": "Paciente desistiu da fila.",
        }
        achados = extrair_evento(ev)
        self.assertEqual(len(achados), 1)
        self.assertEqual(achados[0].codigo, C.SAIU_DA_FILA)
        self.assertEqual(achados[0].dimensao, D.ALERTA)

    def test_validacao_llm_anti_alucinacao(self):
        sol = {
            "solicitacao_id": "SOL-4",
            "data_entrada_fila": "2026-01-01",
            "cid_principal": "K409",
            "justificativa_clinica": "Paciente relata piora da dor ha 2 meses com crises agudas.",
        }
        resposta_llm = [
            {"codigo": "PIORA_RELATADA", "data_fato": "2026-08-10", "trecho": "piora da dor ha 2 meses"},
            {"codigo": "PRONTO_SOCORRO", "data_fato": "2026-08-10", "trecho": "trecho que nao existe no texto"},
        ]
        achados = extrair_solicitacao(sol, resposta_llm=resposta_llm)
        codigos_llm = [a.codigo for a in achados if a.origem == Origem.LLM]
        self.assertIn(C.PIORA_RELATADA, codigos_llm)
        self.assertNotIn(C.PRONTO_SOCORRO, codigos_llm)  # Descartado porque trecho não existe


class TestContagensDataset(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        candidatos = [
            Path(__file__).resolve().parents[2] / "database" / "ordovitae.sqlite3",
            Path(__file__).resolve().parents[2] / "OrdoVitae" / "database" / "ordovitae.sqlite3",
            Path(__file__).resolve().parents[1] / "database" / "ordovitae.sqlite3",
        ]
        db_path = next((p for p in candidatos if p.exists()), candidatos[0])
        cls.conn = sqlite3.connect(db_path)
        cls.conn.row_factory = sqlite3.Row

    @classmethod
    def tearDownClass(cls):
        cls.conn.close()

    def test_contagens_referencia_spec(self):
        # 1. Solicitações
        sols = self.conn.execute("SELECT * FROM fila_cirurgica").fetchall()
        cid_maligno_count = 0
        for s in sols:
            achados = extrair_solicitacao(dict(s))
            if any(a.codigo == C.CID_MALIGNO for a in achados):
                cid_maligno_count += 1
        self.assertEqual(cid_maligno_count, 177)

        # 2. Eventos
        evs = self.conn.execute("SELECT * FROM eventos_clinicos").fetchall()
        biopsia_count = 0
        saiu_fila_count = 0
        ps_count = 0
        internacao_count = 0

        for e in evs:
            achados = extrair_evento(dict(e))
            for a in achados:
                if a.codigo == C.BIOPSIA_POSITIVA:
                    biopsia_count += 1
                elif a.codigo == C.SAIU_DA_FILA:
                    saiu_fila_count += 1
                elif a.codigo == C.PRONTO_SOCORRO:
                    ps_count += 1
                elif a.codigo == C.INTERNACAO:
                    internacao_count += 1

        # No dataset bruto existem 147 (sendo EVT-000323 e EVT-000324 duplicados idênticos).
        # No banco normalizado e deduplicado ficam 146.
        self.assertIn(biopsia_count, (146, 147))
        self.assertEqual(saiu_fila_count, 18)
        # No dataset bruto existem 203 (sendo EVT-001030 e EVT-001031 duplicados idênticos).
        # No banco normalizado e deduplicado ficam 202.
        self.assertIn(ps_count, (202, 203))
        self.assertEqual(internacao_count, 41)

    def test_validacao_39_observacoes_e_10_negacoes_dataset(self):
        # 1. Os 10 "sem sinais de encarceramento" no dataset não podem gerar SINAL_ALARME
        sols_encarcer = self.conn.execute("SELECT * FROM fila_cirurgica WHERE lower(justificativa_clinica) LIKE '%sem sinais de encarceramento%'").fetchall()
        self.assertEqual(len(sols_encarcer), 10)
        for s in sols_encarcer:
            achados = extrair_solicitacao(dict(s))
            self.assertNotIn(C.SINAL_ALARME, [a.codigo for a in achados])

        # 2. As 39 observações com piora, internação, emagrecimento ou PS
        sols_obs = self.conn.execute("SELECT * FROM fila_cirurgica WHERE length(observacoes) > 0").fetchall()
        count_alvo_39 = 0
        for s in sols_obs:
            achados = extrair_solicitacao(dict(s))
            cods = [a.codigo for a in achados if a.evidencia.fonte == "observacao"]
            if any(c in (C.INTERNACAO, C.PIORA_RELATADA, C.SINAL_ALARME, C.PRONTO_SOCORRO) for c in cods):
                count_alvo_39 += 1
        self.assertEqual(count_alvo_39, 39)


if __name__ == "__main__":
    unittest.main()
