import sqlite3

con = sqlite3.connect("openwebui_data/webui.db")
cur = con.cursor()

rows = cur.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()

for r in rows:
    print(r[0])

con.close()
