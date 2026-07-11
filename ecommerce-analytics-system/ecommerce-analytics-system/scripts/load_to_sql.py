import sqlite3
import pandas as pd

DB_PATH = "ecommerce.db"
SCHEMA_PATH = "sql/schema.sql"
CLEAN_DIR = "data/cleaned"


def create_schema(conn):
    with open(SCHEMA_PATH, "r") as f:
        conn.executescript(f.read())
    print("schema created from sql/schema.sql")


def load_table(conn, csv_path, table_name):
    df = pd.read_csv(csv_path)
    df.to_sql(table_name, conn, if_exists="append", index=False)
    print(f"loaded {len(df)} rows into '{table_name}'")


def verify(conn):
    print("\n--- verification ---")
    cur = conn.cursor()

    for table in ["customers", "products", "orders", "order_items"]:
        cur.execute(f"SELECT COUNT(*) FROM {table}")
        print(f"  {table}: {cur.fetchone()[0]} rows")

    cur.execute("""
        SELECT COUNT(*) FROM orders o
        LEFT JOIN customers c ON o.customer_id = c.customer_id
        WHERE c.customer_id IS NULL
    """)
    orphan_orders = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM order_items oi
        LEFT JOIN orders o ON oi.order_id = o.order_id
        WHERE o.order_id IS NULL
    """)
    orphan_items_order = cur.fetchone()[0]

    cur.execute("""
        SELECT COUNT(*) FROM order_items oi
        LEFT JOIN products p ON oi.product_id = p.product_id
        WHERE p.product_id IS NULL
    """)
    orphan_items_product = cur.fetchone()[0]

    print(f"  orphan orders: {orphan_orders}")
    print(f"  orphan order_items (order): {orphan_items_order}")
    print(f"  orphan order_items (product): {orphan_items_product}")

    if orphan_orders == 0 and orphan_items_order == 0 and orphan_items_product == 0:
        print("  referential integrity ok")
    else:
        print("  WARNING: referential integrity issues remain")


def main():
    conn = sqlite3.connect(DB_PATH)
    conn.execute("PRAGMA foreign_keys = ON")

    create_schema(conn)
    load_table(conn, f"{CLEAN_DIR}/customers_clean.csv", "customers")
    load_table(conn, f"{CLEAN_DIR}/products_clean.csv", "products")
    load_table(conn, f"{CLEAN_DIR}/orders_clean.csv", "orders")
    load_table(conn, f"{CLEAN_DIR}/order_items_clean.csv", "order_items")

    conn.commit()
    verify(conn)
    conn.close()
    print(f"\ndatabase ready at ./{DB_PATH}")


if __name__ == "__main__":
    main()
