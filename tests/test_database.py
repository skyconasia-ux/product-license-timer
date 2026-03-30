from models.database import initialize_db, get_connection


def test_initialize_creates_products_table(tmp_path):
    db = tmp_path / "licenses.db"
    initialize_db(db)
    with get_connection(db) as conn:
        rows = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        names = {r[0] for r in rows}
    assert "products" in names
    assert "notifications_log" in names


def test_foreign_keys_enabled(tmp_path):
    db = tmp_path / "licenses.db"
    initialize_db(db)
    with get_connection(db) as conn:
        result = conn.execute("PRAGMA foreign_keys").fetchone()
    assert result[0] == 1


def test_initialize_is_idempotent(tmp_path):
    db = tmp_path / "licenses.db"
    initialize_db(db)
    initialize_db(db)  # second call must not raise
