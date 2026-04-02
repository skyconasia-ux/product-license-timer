import pytest
from unittest.mock import patch
from services.db_session import get_session, get_engine


def test_get_session_returns_session():
    with patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"}):
        from importlib import reload
        import services.db_session as dbs
        reload(dbs)
        session = dbs.get_session()
        assert session is not None
        session.close()


def test_get_engine_uses_env():
    with patch.dict("os.environ", {"DATABASE_URL": "sqlite:///:memory:"}):
        from importlib import reload
        import services.db_session as dbs
        reload(dbs)
        engine = dbs.get_engine()
        assert "sqlite" in str(engine.url)
