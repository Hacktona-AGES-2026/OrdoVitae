"""Simulador (SIMULADOR=1): fonte do dataset, injeção dia a dia e rotas que só existem com a variável."""
import importlib
import os
import unittest
from datetime import date

from fastapi.testclient import TestClient

from api.dependencias import criar_servico, obter_servico
from infra.fonte_dataset import FonteDataset
from servico.simulador import Simulador

FONTE = FonteDataset()


class TestFonteDataset(unittest.TestCase):
    def test_solicitacao_chega_sem_observacoes_e_observacao_vira_evento(self):
        todas = [c for d in FONTE.dias_com_chegada() for c in FONTE.chegadas(d)]
        self.assertTrue(all(c.dados["observacoes"] == "" for c in todas if c.tipo == "solicitacao"))
        obs = [c for c in todas if c.dados.get("tipo_evento") == "observacao"]
        self.assertGreater(len(obs), 500)

    def test_evento_nunca_chega_antes_de_acontecer(self):
        for d in FONTE.dias_com_chegada():
            for c in FONTE.chegadas(d):
                if c.tipo == "evento":
                    self.assertGreaterEqual(d, date.fromisoformat(c.dados["data_evento"][:10]))

    def test_solicitacoes_antes_dos_eventos_no_mesmo_dia(self):
        for d in FONTE.dias_com_chegada():
            tipos = [c.tipo for c in FONTE.chegadas(d)]
            self.assertEqual(tipos, sorted(tipos, key=lambda t: t != "solicitacao"))

    def test_resposta_llm_anexada_quando_existe(self):
        com_llm = [c for d in FONTE.dias_com_chegada() for c in FONTE.chegadas(d) if c.resposta_llm]
        self.assertGreater(len(com_llm), 0)


class TestSimulador(unittest.TestCase):
    def setUp(self):
        self.svc = criar_servico("sqlite://")
        self.addCleanup(self.svc.uow().fabrica.kw["bind"].dispose)
        self.sim = Simulador(self.svc, FONTE)

    def test_primeiro_passo_e_o_dia_zero(self):
        self.assertEqual(self.sim.avancar(1), FONTE.primeira_data())
        self.assertGreater(len(self.svc.listar_sugestoes("pendente")), 0)
        self.assertTrue(self.svc.consultar_fila(FONTE.primeira_data()) is not None)

    def test_pular_ate_restaura_auto_aprovar_e_fotografa_o_ultimo_dia(self):
        alvo = date(2022, 12, 31)
        self.assertEqual(self.sim.pular_ate(alvo), alvo)
        self.assertFalse(self.svc.relogio.auto_aprovar)
        self.assertEqual(self.svc.listar_sugestoes("pendente"), [])
        self.assertGreater(len(self.svc.consultar_fila(alvo)), 0)


class TestRotasSimulador(unittest.TestCase):
    def _app(self, ligado: bool):
        if ligado:
            os.environ["SIMULADOR"] = "1"
        else:
            os.environ.pop("SIMULADOR", None)
        import api.main
        main = importlib.reload(api.main)
        svc = criar_servico("sqlite://")
        self.addCleanup(svc.uow().fabrica.kw["bind"].dispose)
        main.app.dependency_overrides[obter_servico] = lambda: svc
        self.addCleanup(lambda: (os.environ.pop("SIMULADOR", None), importlib.reload(api.main)))
        return TestClient(main.app)

    def test_sem_variavel_rotas_nao_existem(self):
        api = self._app(False)
        self.assertEqual(api.post("/simulacao/reiniciar").status_code, 404)

    def test_com_variavel_avancar_injeta_e_frames_devolve_a_fila(self):
        api = self._app(True)
        self.assertEqual(api.post("/simulacao/pular-ate", json={"data": "2022-12-31"}).status_code, 200)
        self.assertEqual(api.post("/simulacao/avancar-dia", json={"dias": 2}).json()["hoje"], "2023-01-02")
        frames = api.get("/simulacao/frames", params={"de": "2022-12-30"}).json()
        self.assertEqual([f["data"] for f in frames], ["2022-12-31", "2023-01-01", "2023-01-02"])
        self.assertEqual(api.post("/simulacao/reiniciar").json()["hoje"], None)


if __name__ == "__main__":
    unittest.main()
