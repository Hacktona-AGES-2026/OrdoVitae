"""Ponta a ponta: replay do dataset inteiro pelo serviço (SQLite) → CSV → verificador oficial.

Demora ~1 min; roda só com ORDO_E2E=1:
  ORDO_E2E=1 python -m unittest tests.test_ponta_a_ponta
"""
import importlib.util
import os
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

from api.dependencias import criar_servico
from scripts.replay_servico import RAIZ, REF, replay


@unittest.skipUnless(os.environ.get("ORDO_E2E") == "1", "defina ORDO_E2E=1 (leva ~1 min)")
@unittest.skipUnless(importlib.util.find_spec("pandas"), "o verificador oficial precisa de pandas")
class TestPontaAPonta(unittest.TestCase):
    def test_replay_pelo_servico_passa_no_verificador(self):
        with tempfile.TemporaryDirectory() as tmp:
            svc = criar_servico(f"sqlite:///{Path(tmp, 'e2e.sqlite3').as_posix()}")
            resumo = replay(svc)
            self.assertEqual(resumo["hoje"], REF)
            csv = Path(tmp, "fila_priorizada.csv")
            csv.write_text(svc.exportar_fila_priorizada(), encoding="utf-8")
            r = subprocess.run([sys.executable, str(RAIZ / "verificar_fila_priorizada.py"), str(csv),
                                "--dataset", str(RAIZ)], capture_output=True, text=True, encoding="utf-8")
            svc.uow().fabrica.kw["bind"].dispose()
        self.assertIn("RESULTADO: OK", r.stdout, r.stdout + r.stderr)
        saidas = 941 - resumo["fila"]
        self.assertEqual(saidas, resumo["sugestoes"]["remover"], "toda saída veio de um REMOVER aprovado")


if __name__ == "__main__":
    unittest.main()
