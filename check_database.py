import sqlite3

connection = sqlite3.connect("data/signals.db")

cursor = connection.cursor()

cursor.execute("SELECT * FROM website_analyses")

records = cursor.fetchall()

for record in records:
    print("\nRecord:", record[0])
    print("Website:", record[1])
    print("URL:", record[2])
    print("Signals:", record[5])

connection.close()