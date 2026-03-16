import mysql.connector

def run_migration():
    print("Connecting to local database...")
    local_db = mysql.connector.connect(
        host='localhost',
        user='root',
        password='123456', # Example local password
        database='visitor_db'
    )
    
    print("Connecting to remote database...")
    remote_db = mysql.connector.connect(
        host='YOUR_AIVEN_HOST',
        user='YOUR_AIVEN_USER',
        password='YOUR_AIVEN_PASSWORD',
        database='defaultdb',
        port=17551,
        ssl_disabled=False,
        ssl_verify_cert=False,
        ssl_verify_identity=False
    )
    
    local_cursor = local_db.cursor(dictionary=True)
    remote_cursor = remote_db.cursor()
    
    # Disable foreign key checks on remote
    remote_cursor.execute("SET FOREIGN_KEY_CHECKS=0;")
    
    # Drop all existing tables on remote
    remote_cursor.execute("SHOW TABLES")
    remote_tables = [row[0] for row in remote_cursor.fetchall()]
    for table in remote_tables:
        remote_cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
        remote_db.commit()
    
    local_cursor.execute("SHOW TABLES")
    tables_to_migrate = [row[f'Tables_in_visitor_db'] for row in local_cursor.fetchall()]
    
    for table in tables_to_migrate:
        print(f"Migrating table schema and data: {table} ...")
        
        # 1. Migrate Schema
        local_cursor.execute(f"SHOW CREATE TABLE `{table}`")
        create_stmt = local_cursor.fetchone()['Create Table']
        remote_cursor.execute(create_stmt)
        remote_db.commit()
        
        # 2. Migrate Data
        local_cursor.execute(f"SELECT * FROM `{table}`")
        rows = local_cursor.fetchall()
        
        if not rows:
            continue
            
        columns = rows[0].keys()
        
        # Prepare insert query
        cols_str = ", ".join([f"`{c}`" for c in columns])
        val_placeholders = ", ".join(["%s"] * len(columns))
        insert_query = f"INSERT IGNORE INTO `{table}` ({cols_str}) VALUES ({val_placeholders})"
        
        # Insert rows
        insert_data = []
        for row in rows:
            insert_data.append(tuple(row[c] for c in columns))
        
        try:
            remote_cursor.executemany(insert_query, insert_data)
            remote_db.commit()
            print(f"  -> Migrated {len(rows)} rows.")
        except Exception as e:
            print(f"  -> Error migrating {table}: {e}")
            
    # Re-enable foreign key checks on remote
    remote_cursor.execute("SET FOREIGN_KEY_CHECKS=1;")
    
    print("Migration complete!")
    local_cursor.close()
    local_db.close()
    remote_cursor.close()
    remote_db.close()

if __name__ == '__main__':
    run_migration()
