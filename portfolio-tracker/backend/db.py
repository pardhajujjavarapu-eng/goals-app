from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase
from pathlib import Path

DB_PATH = Path(__file__).parent.parent / "data" / "portfolio.db"
DB_PATH.parent.mkdir(parents=True, exist_ok=True)

engine = create_engine(
    f"sqlite:///{DB_PATH}",
    echo=False,
    connect_args={"check_same_thread": False},
)


class Base(DeclarativeBase):
    pass
