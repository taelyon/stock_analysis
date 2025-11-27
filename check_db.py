import sqlite3
import pandas as pd

conn = sqlite3.connect('investar.db')
cursor = conn.cursor()

try:
    cursor.execute("SELECT * FROM comp_info WHERE code='IONQ' OR company LIKE '%IONQ%'")
    rows = cursor.fetchall()
    print("IONQ Info:", rows)
    
    cursor.execute("SELECT * FROM comp_info LIMIT 5")
    print("Sample Info:", cursor.fetchall())
except Exception as e:
    print(e)
finally:
    conn.close()
