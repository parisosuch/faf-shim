from collections.abc import Generator
from sqlmodel import SQLModel, Session, create_engine, text

DATABASE_URL = "sqlite:///faf-shim.db"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def init_db():
    # Enable WAL mode for better concurrent read performance
    with engine.connect() as conn:
        conn.execute(text("PRAGMA journal_mode=WAL"))

    SQLModel.metadata.create_all(engine)


def get_session() -> Generator[Session, None, None]:
    with Session(engine) as session:
        yield session
