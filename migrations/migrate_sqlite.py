"""
Migrate existing SQLite data to SQL Server.
Usage: python -m migrations.migrate_sqlite --sqlite path/to/licenses.db
"""
from __future__ import annotations
import argparse
import sqlite3
from datetime import date
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
import sys

load_dotenv()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--sqlite", required=True, help="Path to SQLite licenses.db")
    args = parser.parse_args()

    url = os.getenv("DATABASE_URL")
    if not url:
        print("ERROR: DATABASE_URL not set in .env")
        sys.exit(1)

    from models.orm import Base, User, UserRole, Product, NotificationLog, NotificationType
    engine = create_engine(url)
    Base.metadata.create_all(engine)
    Session = sessionmaker(engine)
    session = Session()

    superadmin = session.query(User).filter_by(role=UserRole.superadmin).first()
    if not superadmin:
        print("ERROR: Run init_schema.py first to create superadmin.")
        sys.exit(1)

    src = sqlite3.connect(args.sqlite)
    src.row_factory = sqlite3.Row

    products = src.execute("SELECT * FROM products").fetchall()
    id_map: dict[int, int] = {}
    product_count = 0

    for row in products:
        existing = session.query(Product).filter_by(product_name=row["name"]).first()
        if existing:
            id_map[row["id"]] = existing.id
            continue
        p = Product(
            product_name=row["name"],
            customer_name=row["customer_name"] or "",
            order_number=row["order_number"] or "",
            start_date=date.fromisoformat(row["start_date"]),
            duration_days=row["duration_days"],
            expiry_date=date.fromisoformat(row["expiry_date"]),
            notes=row["notes"] or "",
            created_by=superadmin.id,
        )
        session.add(p)
        session.flush()
        id_map[row["id"]] = p.id
        product_count += 1

    ntype_map = {"15_days": NotificationType.days_15,
                 "10_days": NotificationType.days_10,
                 "5_days":  NotificationType.days_5}
    logs = src.execute("SELECT * FROM notifications_log").fetchall()
    log_count = 0
    for row in logs:
        new_pid = id_map.get(row["product_id"])
        if not new_pid:
            continue
        ntype = ntype_map.get(row["notification_type"])
        if not ntype:
            continue
        from datetime import datetime
        existing_log = session.query(NotificationLog).filter_by(
            product_id=new_pid, notification_type=ntype).first()
        if existing_log:
            continue
        session.add(NotificationLog(
            product_id=new_pid,
            notification_type=ntype,
            sent_at=datetime.fromisoformat(row["sent_at"]),
        ))
        log_count += 1

    session.commit()
    src.close()
    session.close()
    print(f"Migration complete: {product_count} products, {log_count} notification logs.")


if __name__ == "__main__":
    main()
