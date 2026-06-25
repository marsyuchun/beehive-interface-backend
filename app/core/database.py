from collections.abc import Iterator

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.core.config import Settings


class Base(DeclarativeBase):
    pass


def create_engine_from_settings(settings: Settings | None = None) -> Engine:
    resolved_settings = settings or Settings()
    connect_args = (
        {"check_same_thread": False}
        if resolved_settings.database_url.startswith("sqlite")
        else {}
    )
    return create_engine(resolved_settings.database_url, connect_args=connect_args)


engine = create_engine_from_settings()
SessionFactory = sessionmaker(
    bind=engine,
    autoflush=False,
    expire_on_commit=False,
)


def get_session() -> Iterator[Session]:
    with SessionFactory() as session:
        yield session


def init_database(database_engine: Engine | None = None) -> None:
    import app.models  # noqa: F401

    Base.metadata.create_all(database_engine or engine)
