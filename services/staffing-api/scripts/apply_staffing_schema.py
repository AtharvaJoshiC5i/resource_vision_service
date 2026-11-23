"""Apply sql/staffing_schema.sql to the configured Azure SQL database."""
from __future__ import annotations

from pathlib import Path

from app.database import connect

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = ROOT / "sql" / "staffing_schema.sql"


def main() -> None:
    sql = SCHEMA.read_text(encoding="utf-8")
    statements = []
    for chunk in sql.split(";"):
        text = chunk.strip()
        if not text:
            continue
        if all(not line.strip() or line.strip().startswith("--") for line in text.splitlines()):
            continue
        statements.append(text)
    with connect() as conn:
        cur = conn.cursor()
        for stmt in statements:
            cur.execute(stmt)
        conn.commit()
    print(f"Applied {len(statements)} statement(s) from {SCHEMA.name}")


if __name__ == "__main__":
    main()