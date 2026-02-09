import sqlite3
from pathlib import Path
import sys

DB_PATH = Path("openwebui_data/webui.db")
# твой файл-источник
SRC_PATH = Path("a3_assistant/pipe/a3_controller.py")

# id функции в Open WebUI (обычно совпадает с тем, что в pipes(): "a3_controller")
FUNCTION_ID = "a3_controller"

def main():
    if not DB_PATH.exists():
        print(f"❌ DB not found: {DB_PATH.resolve()}")
        sys.exit(1)

    if not SRC_PATH.exists():
        print(f"❌ Source not found: {SRC_PATH.resolve()}")
        sys.exit(1)

    code = SRC_PATH.read_text(encoding="utf-8")
    if "class Pipe" not in code:
        print("⚠️ В файле не найдено 'class Pipe' — ты точно туда вставил код функции?")
        sys.exit(1)

    con = sqlite3.connect(str(DB_PATH))
    cur = con.cursor()

    # проверим, что функция существует
    row = cur.execute(
        "SELECT id, name FROM function WHERE id = ? OR name = ? LIMIT 1",
        (FUNCTION_ID, FUNCTION_ID),
    ).fetchone()

    if not row:
        # покажем подсказку: что есть
        rows = cur.execute("SELECT id, name FROM function ORDER BY id LIMIT 30").fetchall()
        con.close()
        print("❌ Функция не найдена по id/name =", FUNCTION_ID)
        print("Вот первые 30 функций в БД (id, name):")
        for r in rows:
            print(" -", r)
        sys.exit(1)

    found_id, found_name = row

    # В OpenWebUI в разных версиях поле с кодом может называться по-разному.
    # Попробуем самые частые: content / code / data
    cols = [r[1] for r in cur.execute("PRAGMA table_info(function)").fetchall()]

    target_col = None
    for c in ("content", "code", "data"):
        if c in cols:
            target_col = c
            break

    if not target_col:
        con.close()
        print("❌ Не нашёл колонку для кода функции. Колонки:", cols)
        sys.exit(1)

    cur.execute(f"UPDATE function SET {target_col} = ? WHERE id = ?", (code, found_id))
    con.commit()
    con.close()

    print(f"✅ Updated function '{found_name}' (id={found_id}) via column '{target_col}'")

if __name__ == "__main__":
    main()
