"""API ponta a ponta (TestClient) sobre um serviço com SQLite em memória."""
import unittest

from fastapi.testclient import TestClient

from api.dependencias import criar_servico, obter_servico
from api.main import app

SOL = {"solicitacao_id": "SOL-1", "paciente_id": "PAC-1", "procedimento_id": "PROC002", "cid_principal": "K40.9",
       "data_entrada_fila": "2026-01-10", "intensidade_dor_eva": "2", "limitacao_funcional": "nenhuma", "asa": "2",
       "comorbidades": "nenhuma", "justificativa_clinica": "Hernia inguinal redutivel, sem complicacoes ha meses."}
ONCO = dict(SOL, solicitacao_id="SOL-2", paciente_id="PAC-2", procedimento_id="PROC014", cid_principal="C50.9")


class TestApi(unittest.TestCase):
    def setUp(self):
        svc = criar_servico("sqlite://", {"PROC002": 2, "PROC014": 4})
        self.addCleanup(svc.uow().fabrica.kw["bind"].dispose)
        app.dependency_overrides[obter_servico] = lambda: svc
        self.addCleanup(app.dependency_overrides.clear)
        self.api = TestClient(app)

    def test_fluxo_simulador_e_regulador(self):
        self.assertIsNone(self.api.get("/simulacao").json()["hoje"])
        r = self.api.post("/integracao/solicitacoes", json={"dados": SOL})
        self.assertEqual(r.status_code, 201)
        self.assertEqual(r.json()["sugestoes"][0]["tipo"], "classificacao_inicial")
        self.api.post("/integracao/solicitacoes", json={"dados": ONCO})

        pagina = self.api.get("/sugestoes", params={"status": "pendente"}).json()
        self.assertEqual((pagina["total"], pagina["limite"], pagina["offset"]), (2, 50, 0))
        pendentes = pagina["itens"]
        self.assertEqual(len(pendentes), 2)
        self.assertIn("posicaoPara", pendentes[0]["previa"])
        for s in pendentes:
            self.assertEqual(self.api.patch(f"/sugestoes/{s['id']}", json={"status": "aprovada"}).json()["status"], "aprovada")

        fila = self.api.get("/fila").json()
        self.assertEqual(fila["data"], "2026-01-10")
        self.assertEqual([i["solicitacaoId"] for i in fila["ordem"]], ["SOL-2", "SOL-1"])
        self.assertEqual({"posicaoAnterior", "diasEmFila", "alemDoPrazo", "provisorio"} - fila["ordem"][0].keys(), set())

        self.assertEqual(self.api.patch("/simulacao", json={"hoje": "2026-01-12"}).json()["hoje"], "2026-01-12")
        self.assertEqual(len(self.api.get("/fila", params={"data": "2026-01-11"}).json()["ordem"]), 2)

        ev = {"evento_id": "EVT-1", "solicitacao_id": "SOL-1", "data_evento": "2026-01-12",
              "tipo_evento": "biopsia", "resultado": "positivo", "descricao": "AP: adenocarcinoma."}
        [subir] = self.api.post("/integracao/eventos", json={"dados": ev}).json()["sugestoes"]
        self.assertEqual((subir["tipo"], subir["classePara"]), ("subir", "A2"))
        rejeitada = self.api.patch(f"/sugestoes/{subir['id']}", json={"status": "rejeitada", "comentario": "AP em revisão"}).json()
        self.assertEqual((rejeitada["status"], rejeitada["comentario"]), ("rejeitada", "AP em revisão"))

        ficha = self.api.get("/solicitacoes/SOL-1").json()
        self.assertEqual([h["data"] for h in ficha["historico"]], ["2026-01-11", "2026-01-12"])
        self.assertTrue(any(a["codigo"] == "BIOPSIA_POSITIVA" for a in ficha["achados"]))

        csv = self.api.get("/fila.csv")
        self.assertEqual(csv.headers["content-type"].split(";")[0], "text/csv")
        self.assertTrue(csv.text.startswith("solicitacao_id,posicao,justificativa\nSOL-2,1,"))
        self.assertIsInstance(self.api.get("/alertas").json()["itens"], list)

    def test_datas_com_foto(self):
        self.assertEqual(self.api.get("/simulacao/datas").json(), [])
        self.api.post("/integracao/solicitacoes", json={"dados": SOL})
        self.api.post("/simulacao/avancar-dia", json={"dias": 2})
        self.assertEqual(self.api.get("/simulacao/datas").json(), ["2026-01-11", "2026-01-12"])

    def test_decisao_compartilhada(self):
        self.api.post("/integracao/solicitacoes", json={"dados": SOL})
        r = self.api.get("/solicitacoes/SOL-1/decisao-compartilhada")
        self.assertEqual(r.status_code, 200)
        self.assertEqual({"resumoMedico", "statusAdesao", "usouLlm", "dataReferencia", "itens"} - r.json().keys(), set())
        self.assertEqual(self.api.get("/solicitacoes/SOL-X/decisao-compartilhada").status_code, 404)

    def test_erros_viram_status_http(self):
        [s] = self.api.post("/integracao/solicitacoes", json={"dados": SOL}).json()["sugestoes"]
        self.assertEqual(self.api.get("/solicitacoes/SOL-X").status_code, 404)
        self.assertEqual(self.api.patch("/sugestoes/999", json={"status": "aprovada"}).status_code, 404)
        r = self.api.patch(f"/sugestoes/{s['id']}", json={"status": "rejeitada", "comentario": " "})
        self.assertEqual((r.status_code, r.json()["erro"]), (422, "ComentarioObrigatorio"))
        self.api.patch(f"/sugestoes/{s['id']}", json={"status": "aprovada"})
        self.assertEqual(self.api.patch(f"/sugestoes/{s['id']}", json={"status": "aprovada"}).status_code, 409)
        self.assertEqual(self.api.get("/fila", params={"data": "2020-01-01"}).status_code, 404)
        self.assertEqual(self.api.patch("/simulacao", json={"hoje": "2026-01-01"}).status_code, 409)
        self.assertEqual(self.api.get("/sugestoes", params={"limite": 500}).status_code, 422)

    def test_colecoes_paginadas(self):
        for i in range(5):
            self.api.post("/integracao/solicitacoes", json={"dados": dict(SOL, solicitacao_id=f"SOL-{i}", paciente_id=f"PAC-{i}")})
        p = self.api.get("/sugestoes", params={"limite": 2, "offset": 2}).json()
        self.assertEqual((len(p["itens"]), p["total"]), (2, 5))
        f = self.api.get("/fila", params={"limite": 2, "offset": 3}).json()
        self.assertEqual(([i["posicao"] for i in f["ordem"]], f["total"]), ([4, 5], 5))
        self.assertEqual(self.api.get(f"/sugestoes/{p['itens'][0]['id']}").status_code, 200)

    def test_auto_aprovar(self):
        self.assertTrue(self.api.patch("/simulacao", json={"autoAprovar": True}).json()["autoAprovar"])
        [s] = self.api.post("/integracao/solicitacoes", json={"dados": SOL}).json()["sugestoes"]
        self.assertEqual((s["status"], s["decididaPor"]), ("aprovada", "simulacao"))


if __name__ == "__main__":
    unittest.main()
