import pytest
from pathlib import Path
from models.database import initialize_db, get_connection


@pytest.fixture
def tmp_db(tmp_path):
    """Temporary SQLite DB initialized with schema."""
    db_path = tmp_path / "test_licenses.db"
    initialize_db(db_path)
    return db_path
