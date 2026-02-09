import sqlite3
conn = sqlite3.connect('/app/backend/data/webui.db')
cur = conn.cursor()
row = cur.execute("SELECT id, name, LENGTH(content) FROM function WHERE id='a3'").fetchone()
print(row)
if row:
    head = cur.execute("SELECT content FROM function WHERE id='a3'").fetchone()[0][:40]
    print(repr(head))
conn.close()
