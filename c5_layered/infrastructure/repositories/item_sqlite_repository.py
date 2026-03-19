from __future__ import annotations

import sqlite3
from pathlib import Path

from c5_layered.domain.models import ItemSnapshot


class SqliteItemRepository:
    def __init__(self, db_file: Path) -> None:
        self._db_file = db_file

    def get_item_snapshot(self, item_id: str) -> ItemSnapshot | None:
        if not self._db_file.exists():
            return None

        sql = (
            "SELECT itemId, itemName, minwear, maxwear, minPrice, grade, lastModified "
            "FROM items WHERE itemId = ?"
        )
        try:
            with sqlite3.connect(self._db_file) as conn:
                cur = conn.execute(sql, (item_id,))
                row = cur.fetchone()
            if not row:
                return None
            return ItemSnapshot(
                item_id=str(row[0]),
                item_name=row[1],
                minwear=row[2],
                maxwear=row[3],
                min_price=row[4],
                grade=row[5],
                last_modified=row[6],
            )
        except sqlite3.Error:
            return None

