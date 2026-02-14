from __future__ import annotations

import json
import shutil
import sqlite3
import time
from pathlib import Path
from typing import Dict, Optional


DB_PATH = Path("/app/backend/data/webui.db")
PIPELINE_TARGET = Path("/app/backend/data/pipelines/a3_controller.py")
A3_SOURCE = Path("/a3_assistant/pipe/a3_controller.py")
ACTION_DIR = Path("/a3_assistant/actions")


def _read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore")


def _resolve_user_id(cur: sqlite3.Cursor) -> str:
    row = cur.execute(
        "SELECT user_id FROM function WHERE id='a3_pm_methodologist'"
    ).fetchone()
    if row and row[0]:
        return str(row[0])

    row = cur.execute("SELECT user_id FROM function LIMIT 1").fetchone()
    if row and row[0]:
        return str(row[0])

    for table in ("user", "users"):
        try:
            row = cur.execute(f"SELECT id FROM {table} LIMIT 1").fetchone()
            if row and row[0]:
                return str(row[0])
        except sqlite3.Error:
            continue

    # Fallback for empty installs where no function/user rows exist yet.
    return "00000000-0000-0000-0000-000000000000"


def _upsert_function(
    cur: sqlite3.Cursor,
    *,
    function_id: str,
    user_id: str,
    name: str,
    ftype: str,
    content: str,
    meta: Dict[str, object],
    now: int,
    is_global: int,
    valves: Optional[Dict[str, object]] = None,
) -> None:
    meta_json = json.dumps(meta, ensure_ascii=False)
    valves_json = json.dumps(valves, ensure_ascii=False) if valves else None
    exists = cur.execute("SELECT 1 FROM function WHERE id=?", (function_id,)).fetchone()
    if exists:
        cur.execute(
            """
            UPDATE function
            SET name=?, type=?, content=?, meta=?, valves=?, updated_at=?, is_active=1, is_global=?
            WHERE id=?
            """,
            (name, ftype, content, meta_json, valves_json, now, is_global, function_id),
        )
    else:
        cur.execute(
            """
            INSERT INTO function
            (id, user_id, name, type, content, meta, created_at, updated_at, valves, is_active, is_global)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 1, ?)
            """,
            (
                function_id,
                user_id,
                name,
                ftype,
                content,
                meta_json,
                now,
                now,
                valves_json,
                is_global,
            ),
        )


def main() -> None:
    if not DB_PATH.exists():
        raise FileNotFoundError(f"webui.db not found: {DB_PATH}")
    if not A3_SOURCE.exists():
        raise FileNotFoundError(f"A3 source not found: {A3_SOURCE}")

    # Keep pipeline file synchronized too (fallback runtime mode).
    PIPELINE_TARGET.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(A3_SOURCE, PIPELINE_TARGET)

    now = int(time.time())
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()

    user_id = _resolve_user_id(cur)
    a3_content = _read_text(A3_SOURCE)

    _upsert_function(
        cur,
        function_id="a3_pm_methodologist",
        user_id=user_id,
        name="A3 PM Methodologist",
        ftype="pipe",
        content=a3_content,
        meta={
            "description": "A3 project controller and methodologist",
            "manifest": {"title": "A3 PM Methodologist", "version": "local-sync-1"},
        },
        now=now,
        is_global=0,
    )

    actions = [
        (
            "smart_infographic",
            "Smart Infographic",
            ACTION_DIR / "smart_infographic.py",
            {
                "description": "AI-powered infographic generator based on AntV Infographic.",
                "manifest": {"title": "Smart Infographic", "author": "Fu-Jie"},
            },
            {"MODEL_ID": "chatgpt-4o-latest", "OUTPUT_MODE": "image"},
        ),
        (
            "export_to_word_enhanced_formatting",
            "Export to Word Enhanced",
            ACTION_DIR / "export_to_word_enhanced_formatting.py",
            {
                "description": "Export current conversation to Word (.docx) with enhanced formatting.",
                "manifest": {"title": "Export to Word Enhanced", "author": "Fu-Jie"},
            },
            None,
        ),
    ]

    for function_id, name, path, meta, valves in actions:
        if not path.exists():
            raise FileNotFoundError(f"action source not found: {path}")
        content = _read_text(path)
        _upsert_function(
            cur,
            function_id=function_id,
            user_id=user_id,
            name=name,
            ftype="action",
            content=content,
            meta=meta,
            now=now,
            is_global=1,
            valves=valves,
        )

    con.commit()

    rows = cur.execute(
        """
        SELECT id, type, is_active, is_global, length(content)
        FROM function
        WHERE id IN ('a3_pm_methodologist', 'smart_infographic', 'export_to_word_enhanced_formatting')
        ORDER BY id
        """
    ).fetchall()
    con.close()

    print("[sync] webui.db function sync complete")
    for row in rows:
        print(f"[sync] {row}")


if __name__ == "__main__":
    main()
