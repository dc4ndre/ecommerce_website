import sqlite3
import os
from datetime import datetime

# Always use the same DB file as Flask (inside /instance folder)
DB_PATH = os.path.join(os.path.dirname(__file__), "instance", "ecommerce.db")

def check_database():
    print(f"📂 Using database: {os.path.abspath(DB_PATH)}")

    if not os.path.exists(DB_PATH):
        print(f"❌ Database file '{DB_PATH}' not found!")
        print("Run your Flask app first to create the database.")
        return
    
    print(f"✅ Database file found: {DB_PATH}")
    print(f"File size: {os.path.getsize(DB_PATH)} bytes")
    print(f"Last modified: {datetime.fromtimestamp(os.path.getmtime(DB_PATH))}")
    print("="*50)
    
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table';")
        tables = cursor.fetchall()
        
        print(f"📊 Found {len(tables)} tables:")
        for table in tables:
            print(f"  - {table[0]}")
        print("="*50)
        
        # Include cart_items table
        for table_name in ['users', 'products', 'categories', 'orders', 'order_items', 'cart_items']:
            print(f"\n🔍 TABLE: {table_name.upper()}")
            try:
                cursor.execute(f"PRAGMA table_info({table_name})")
                columns = cursor.fetchall()
                print(f"Columns ({len(columns)}):")
                for col in columns:
                    print(f"  - {col[1]} ({col[2]})")
                
                cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
                count = cursor.fetchone()[0]
                print(f"Records: {count}")
                
                if count > 0:
                    if table_name == "cart_items":
                        cursor.execute('''
                            SELECT ci.id, ci.user_id, ci.product_id, p.name, p.price, ci.quantity, ci.created_at
                            FROM cart_items ci
                            JOIN products p ON ci.product_id = p.id
                            LIMIT 5
                        ''')
                        rows = cursor.fetchall()
                        print("Sample data (with product details):")
                        for row in rows:
                            print(f"  CartID={row[0]}, User={row[1]}, ProductID={row[2]}, "
                                  f"Name={row[3]}, Price={row[4]}, Qty={row[5]}, Added={row[6]}")
                    else:
                        cursor.execute(f"SELECT * FROM {table_name} LIMIT 3")
                        rows = cursor.fetchall()
                        print("Sample data:")
                        for i, row in enumerate(rows, 1):
                            print(f"  {i}: {row}")
                
            except sqlite3.Error as e:
                print(f"❌ Error accessing {table_name}: {e}")
            
            print("-" * 30)
        
        conn.close()
        
    except sqlite3.Error as e:
        print(f"❌ Database error: {e}")


def show_all_data():
    print(f"📂 Using database: {os.path.abspath(DB_PATH)}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    tables = ['users', 'products', 'categories', 'orders', 'order_items', 'cart_items']
    
    for table_name in tables:
        print(f"\n{'='*20} {table_name.upper()} {'='*20}")
        try:
            if table_name == "cart_items":
                cursor.execute('''
                    SELECT ci.id, ci.user_id, ci.product_id, p.name, p.price, ci.quantity, ci.created_at
                    FROM cart_items ci
                    JOIN products p ON ci.product_id = p.id
                ''')
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        print(f"CartID={row[0]}, User={row[1]}, ProductID={row[2]}, "
                              f"Name={row[3]}, Price={row[4]}, Qty={row[5]}, Added={row[6]}")
                else:
                    print("No data")
            else:
                cursor.execute(f"SELECT * FROM {table_name}")
                rows = cursor.fetchall()
                if rows:
                    for i, row in enumerate(rows, 1):
                        print(f"{i}: {row}")
                else:
                    print("No data")
                
        except sqlite3.Error as e:
            print(f"Error: {e}")
    
    conn.close()


def run_custom_query():
    print(f"📂 Using database: {os.path.abspath(DB_PATH)}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    print("\n🔧 Custom Query Mode")
    print("Enter SQL queries (type 'exit' to quit):")
    
    while True:
        query = input("\nSQL> ").strip()
        
        if query.lower() == 'exit':
            break
            
        if not query:
            continue
            
        try:
            cursor.execute(query)
            
            if query.lower().startswith('select'):
                rows = cursor.fetchall()
                if rows:
                    for row in rows:
                        print(row)
                else:
                    print("No results")
            else:
                conn.commit()
                print("Query executed successfully")
                
        except sqlite3.Error as e:
            print(f"❌ Error: {e}")
    
    conn.close()


def clear_table(table_name):
    print(f"📂 Using database: {os.path.abspath(DB_PATH)}")
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    confirm = input(f"⚠️ Are you sure you want to delete ALL records from '{table_name}'? (y/n): ").strip().lower()
    if confirm != 'y':
        print("❌ Cancelled. No data was deleted.")
        return
    
    try:
        cursor.execute(f"DELETE FROM {table_name};")
        cursor.execute("DELETE FROM sqlite_sequence WHERE name=?;", (table_name,))
        
        conn.commit()
        print(f"✅ All records from '{table_name}' have been deleted successfully.")
    except sqlite3.Error as e:
        print(f"❌ Error clearing table {table_name}: {e}")
    finally:
        conn.close()


if __name__ == "__main__":
    print("🗄️  E-COMMERCE DATABASE CHECKER")
    print("="*50)
    
    while True:
        print("\nOptions:")
        print("1. Check database overview")
        print("2. Show all data")
        print("3. Run custom SQL query")
        print("4. Clear a table")
        print("5. Exit")
        
        choice = input("\nChoose an option (1-5): ").strip()
        
        if choice == '1':
            check_database()
        elif choice == '2':
            show_all_data()
        elif choice == '3':
            run_custom_query()
        elif choice == '4':
            print("\nAvailable tables: users, products, categories, orders, order_items, cart_items")
            table = input("Enter table name to clear: ").strip()
            clear_table(table)
        elif choice == '5':
            print("👋 Goodbye!")
            break
        else:
            print("❌ Invalid choice. Please enter 1-5.")
