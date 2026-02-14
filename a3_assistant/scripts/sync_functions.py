from __future__ import annotations

import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, Optional, Set


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


def _function_columns(cur: sqlite3.Cursor) -> Set[str]:
    rows = cur.execute("PRAGMA table_info('function')").fetchall()
    return {str(r[1]) for r in rows if len(r) > 1 and r[1]}


def _wait_for_function_table(timeout_sec: int = 60) -> None:
    deadline = time.time() + timeout_sec
    last_err = "function table not ready"
    while time.time() < deadline:
        try:
            if DB_PATH.exists():
                con = sqlite3.connect(DB_PATH)
                cur = con.cursor()
                cols = _function_columns(cur)
                con.close()
                if {"id", "type", "content"}.issubset(cols):
                    return
                last_err = f"columns not ready: {sorted(cols)}"
            else:
                last_err = f"db missing: {DB_PATH}"
        except Exception as e:
            last_err = str(e)
        time.sleep(1)
    raise RuntimeError(f"Timeout waiting for function table. Last error: {last_err}")


def _upsert_function(
    cur: sqlite3.Cursor,
    columns: Set[str],
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
        set_parts = []
        values = []
        update_map = {
            "name": name,
            "type": ftype,
            "content": content,
            "meta": meta_json,
            "valves": valves_json,
            "updated_at": now,
            "is_active": 1,
            "is_global": is_global,
        }
        for key, value in update_map.items():
            if key in columns:
                set_parts.append(f"{key}=?")
                values.append(value)
        if not set_parts:
            raise RuntimeError("No updatable columns in function table")
        values.append(function_id)
        cur.execute(f"UPDATE function SET {', '.join(set_parts)} WHERE id=?", values)
    else:
        insert_map = {
            "id": function_id,
            "user_id": user_id,
            "name": name,
            "type": ftype,
            "content": content,
            "meta": meta_json,
            "created_at": now,
            "updated_at": now,
            "valves": valves_json,
            "is_active": 1,
            "is_global": is_global,
        }
        keys = [k for k in insert_map.keys() if k in columns]
        if not {"id", "type", "content"}.issubset(set(keys)):
            raise RuntimeError(f"Function table missing required columns: {sorted(columns)}")
        placeholders = ", ".join(["?"] * len(keys))
        cur.execute(
            f"INSERT INTO function ({', '.join(keys)}) VALUES ({placeholders})",
            [insert_map[k] for k in keys],
        )


def main() -> None:
    if not A3_SOURCE.exists():
        raise FileNotFoundError(f"A3 source not found: {A3_SOURCE}")

    # Function is the single source of truth for A3 in production.
    # Remove old pipeline file to avoid duplicate "A3" pipe profiles in UI.
    if PIPELINE_TARGET.exists():
        PIPELINE_TARGET.unlink()
        print(f"[sync] removed legacy pipeline file: {PIPELINE_TARGET}")

    _wait_for_function_table(timeout_sec=90)

    now = int(time.time())
    con = sqlite3.connect(DB_PATH)
    cur = con.cursor()
    columns = _function_columns(cur)

    user_id = _resolve_user_id(cur)
    a3_content = _read_text(A3_SOURCE)

    _upsert_function(
        cur,
        columns,
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

    # Disable legacy duplicate pipe if it exists.
    if "is_active" in columns:
        cur.execute("UPDATE function SET is_active=0 WHERE id='a3'")

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
            columns,
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
