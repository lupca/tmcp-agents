import sqlite3

db_path = "/Users/bodoi17/projects/tmcp/tmcp-dashboard/pb_data/data.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id, name, workspace_id FROM marketing_campaigns WHERE id='9b7fcx0b4qtlc7t'")
c = cur.fetchone()
if c:
    print(f"Campaign 'First campain' Workspace: {c['workspace_id']}")

cur.execute("SELECT id, name, workspace_id FROM marketing_campaigns WHERE id='ss486yvk0xyt5rs'")
c2 = cur.fetchone()
if c2:
    print(f"Campaign 'Chuẩn Bị Trong Mạch' Workspace: {c2['workspace_id']}")

cur.execute("SELECT id, email FROM users")
print("USERS:", [dict(u) for u in cur.fetchall()])

cur.execute("SELECT id, name, members FROM workspaces")
print("WORKSPACES:", [dict(w) for w in cur.fetchall()])

conn.close()
