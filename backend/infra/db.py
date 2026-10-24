"""Engine, criação das tabelas e fábrica de sessões. `python -m infra.db` cria database/sistema.sqlite3 vazio."""
from pathlib import Path

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from .orm import Base

CAMINHO_SISTEMA = Path(__file__).resolve().parents[2] / "database" / "sistema.sqlite3"
URL_SISTEMA = f"sqlite:///{CAMINHO_SISTEMA.as_posix()}"


def criar_engine(url: str = URL_SISTEMA) -> Engine:
    if url in ("sqlite://", "sqlite:///:memory:"):
        # em memória: uma conexão só, senão cada sessão enxergaria um banco vazio diferente
        return create_engine(url, connect_args={"check_same_thread": False}, poolclass=StaticPool)
    return create_engine(url, connect_args={"check_same_thread": False})


def criar_tabelas(engine: Engine) -> None:
    Base.metadata.create_all(engine)


def SessionFactory(engine: Engine) -> sessionmaker:
    return sessionmaker(engine, expire_on_commit=False)


def fabrica_para(url: str) -> sessionmaker:
    """Engine + tabelas + fábrica, num passo (usado pelos testes e pela API)."""
    engine = criar_engine(url)
    criar_tabelas(engine)
    return SessionFactory(engine)


if __name__ == "__main__":
    CAMINHO_SISTEMA.parent.mkdir(parents=True, exist_ok=True)
    criar_tabelas(criar_engine())
    print(f"schema criado em {CAMINHO_SISTEMA}")
