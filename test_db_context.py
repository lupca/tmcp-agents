import sqlite3

db_path = "/Users/bodoi17/projects/tmcp/tmcp-dashboard/pb_data/data.db"
conn = sqlite3.connect(db_path)
conn.row_factory = sqlite3.Row
cur = conn.cursor()

cur.execute("SELECT id, name, worksheet_id, product_id FROM marketing_campaigns")
campaigns = cur.fetchall()

for c in campaigns:
    print(f"Campaign: '{c['name']}' (ID: {c['id']})")
    print(f"  - Worksheet ID: '{c['worksheet_id']}'")
    print(f"  - Product ID: '{c['product_id']}'")
    
    if c['worksheet_id']:
        cur.execute("SELECT title, brandRefs, customerRefs FROM worksheets WHERE id=?", (c['worksheet_id'],))
        ws = cur.fetchone()
        if ws:
            print(f"    -> Worksheet Title: '{ws['title']}'")
            print(f"    -> Brand Refs: {ws['brandRefs']}")
            print(f"    -> Customer Refs: {ws['customerRefs']}")
        else:
            print("    -> Worksheet NOT FOUND in DB")
    
    print("-" * 40)

conn.close()
