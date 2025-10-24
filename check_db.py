import sqlite3

# Check database structure
conn = sqlite3.connect('instance/recordings.db')
cursor = conn.cursor()

# Get all tables
cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
tables = cursor.fetchall()
print("Tables:", tables)

# Get user table structure (try both 'user' and 'users')
for table_name in ['user', 'users']:
    try:
        cursor.execute(f"PRAGMA table_info({table_name})")
        columns = cursor.fetchall()
        if columns:
            print(f"\n{table_name} table columns:")
            for col in columns:
                print(f"  {col[1]} ({col[2]})")
    except:
        print(f"{table_name} table not found")

# Get recording table structure  
cursor.execute("PRAGMA table_info(recording)")
recording_columns = cursor.fetchall()
print(f"\nrecording table columns:")
for col in recording_columns:
    print(f"  {col[1]} ({col[2]})")

conn.close()