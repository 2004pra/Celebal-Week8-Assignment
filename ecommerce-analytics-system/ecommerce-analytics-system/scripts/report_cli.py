import argparse
import os
import sqlite3
import sys

from tabulate import tabulate

REPORTS = {
    "revenue_by_customer": """
        SELECT c.customer_id, c.name, c.segment,
               ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue,
               COUNT(DISTINCT o.order_id) AS total_orders
        FROM customers c
        JOIN orders o ON c.customer_id = o.customer_id
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.status = 'Completed'
        GROUP BY c.customer_id, c.name, c.segment
        ORDER BY total_revenue DESC
    """,
    "revenue_by_category": """
        SELECT p.category,
               ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue,
               SUM(oi.quantity) AS total_units_sold
        FROM order_items oi
        JOIN orders o ON oi.order_id = o.order_id
        JOIN products p ON oi.product_id = p.product_id
        WHERE o.status = 'Completed'
        GROUP BY p.category
        ORDER BY total_revenue DESC
    """,
    "revenue_by_month": """
        SELECT strftime('%Y-%m', o.order_date) AS order_month,
               ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue,
               COUNT(DISTINCT o.order_id) AS total_orders
        FROM orders o
        JOIN order_items oi ON o.order_id = oi.order_id
        WHERE o.status = 'Completed'
        GROUP BY order_month
        ORDER BY order_month
    """,
    "top_products_qty": """
        SELECT p.product_id, p.product_name, p.category,
               SUM(oi.quantity) AS total_units_sold
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY p.product_id, p.product_name, p.category
        ORDER BY total_units_sold DESC
    """,
    "top_products_revenue": """
        SELECT p.product_id, p.product_name, p.category,
               ROUND(SUM(oi.quantity * oi.unit_price), 2) AS total_revenue
        FROM order_items oi
        JOIN products p ON oi.product_id = p.product_id
        JOIN orders o ON oi.order_id = o.order_id
        WHERE o.status = 'Completed'
        GROUP BY p.product_id, p.product_name, p.category
        ORDER BY total_revenue DESC
    """,
    "aov_by_segment": """
        WITH order_totals AS (
            SELECT o.order_id, c.segment,
                   SUM(oi.quantity * oi.unit_price) AS order_total
            FROM orders o
            JOIN customers c ON o.customer_id = c.customer_id
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'
            GROUP BY o.order_id, c.segment
        )
        SELECT segment, ROUND(AVG(order_total), 2) AS avg_order_value,
               COUNT(*) AS num_orders
        FROM order_totals
        GROUP BY segment
        ORDER BY avg_order_value DESC
    """,
    "top_customers_ltv": """
        WITH customer_ltv AS (
            SELECT c.customer_id, c.name,
                   ROUND(SUM(oi.quantity * oi.unit_price), 2) AS lifetime_value
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'
            GROUP BY c.customer_id, c.name
        )
        SELECT customer_id, name, lifetime_value,
               RANK() OVER (ORDER BY lifetime_value DESC) AS ltv_rank,
               DENSE_RANK() OVER (ORDER BY lifetime_value DESC) AS ltv_dense_rank
        FROM customer_ltv
        ORDER BY lifetime_value DESC
    """,
    "running_revenue": """
        WITH monthly_revenue AS (
            SELECT strftime('%Y-%m', o.order_date) AS order_month,
                   SUM(oi.quantity * oi.unit_price) AS monthly_total
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'
            GROUP BY order_month
        )
        SELECT order_month, ROUND(monthly_total, 2) AS monthly_total,
               ROUND(SUM(monthly_total) OVER (ORDER BY order_month), 2) AS running_total
        FROM monthly_revenue
        ORDER BY order_month
    """,
    "moving_avg_revenue": """
        WITH monthly_revenue AS (
            SELECT strftime('%Y-%m', o.order_date) AS order_month,
                   SUM(oi.quantity * oi.unit_price) AS monthly_total
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'
            GROUP BY order_month
        )
        SELECT order_month, ROUND(monthly_total, 2) AS monthly_total,
               ROUND(AVG(monthly_total) OVER (
                   ORDER BY order_month ROWS BETWEEN 2 PRECEDING AND CURRENT ROW
               ), 2) AS moving_avg_3month
        FROM monthly_revenue
        ORDER BY order_month
    """,
    "growth_rate": """
        WITH monthly_revenue AS (
            SELECT strftime('%Y-%m', o.order_date) AS order_month,
                   SUM(oi.quantity * oi.unit_price) AS monthly_total
            FROM orders o
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'
            GROUP BY order_month
        ),
        with_previous AS (
            SELECT order_month, monthly_total,
                   LAG(monthly_total) OVER (ORDER BY order_month) AS prev_month_total
            FROM monthly_revenue
        )
        SELECT order_month, ROUND(monthly_total, 2) AS monthly_total,
               ROUND(prev_month_total, 2) AS prev_month_total,
               CASE WHEN prev_month_total IS NULL OR prev_month_total = 0 THEN NULL
                    ELSE ROUND(100.0 * (monthly_total - prev_month_total) / prev_month_total, 2)
               END AS growth_rate_pct
        FROM with_previous
        ORDER BY order_month
    """,
    "cohort_sizes": """
        WITH first_purchase AS (
            SELECT customer_id, MIN(strftime('%Y-%m', order_date)) AS cohort_month
            FROM orders WHERE status = 'Completed'
            GROUP BY customer_id
        )
        SELECT cohort_month, COUNT(*) AS customers_in_cohort
        FROM first_purchase
        GROUP BY cohort_month
        ORDER BY cohort_month
    """,
    "retention": """
        WITH first_purchase AS (
            SELECT customer_id, MIN(strftime('%Y-%m', order_date)) AS cohort_month
            FROM orders WHERE status = 'Completed'
            GROUP BY customer_id
        ),
        activity AS (
            SELECT DISTINCT o.customer_id, strftime('%Y-%m', o.order_date) AS activity_month
            FROM orders o WHERE o.status = 'Completed'
        ),
        cohort_activity AS (
            SELECT fp.cohort_month, a.activity_month,
                   (CAST(strftime('%Y', a.activity_month || '-01') AS INTEGER) * 12 +
                    CAST(strftime('%m', a.activity_month || '-01') AS INTEGER)) -
                   (CAST(strftime('%Y', fp.cohort_month || '-01') AS INTEGER) * 12 +
                    CAST(strftime('%m', fp.cohort_month || '-01') AS INTEGER)) AS month_index,
                   a.customer_id
            FROM first_purchase fp
            JOIN activity a ON fp.customer_id = a.customer_id
        ),
        cohort_sizes AS (
            SELECT cohort_month, COUNT(*) AS cohort_size
            FROM first_purchase GROUP BY cohort_month
        )
        SELECT ca.cohort_month, ca.month_index,
               COUNT(DISTINCT ca.customer_id) AS active_customers,
               cs.cohort_size,
               ROUND(100.0 * COUNT(DISTINCT ca.customer_id) / cs.cohort_size, 1) AS retention_pct
        FROM cohort_activity ca
        JOIN cohort_sizes cs ON ca.cohort_month = cs.cohort_month
        GROUP BY ca.cohort_month, ca.month_index, cs.cohort_size
        ORDER BY ca.cohort_month, ca.month_index
    """,
    "churn_status": """
        WITH order_counts AS (
            SELECT customer_id, COUNT(*) AS num_orders, MAX(order_date) AS last_order_date
            FROM orders WHERE status = 'Completed'
            GROUP BY customer_id
        )
        SELECT
            CASE
                WHEN num_orders >= 2 THEN 'Repeat'
                WHEN num_orders = 1 AND
                     julianday('now') - julianday(last_order_date) > 90 THEN 'Churned'
                ELSE 'New / Active (single order, recent)'
            END AS customer_status,
            COUNT(*) AS num_customers
        FROM order_counts
        GROUP BY customer_status
    """,
    "segmentation": """
        WITH customer_stats AS (
            SELECT c.customer_id, c.name,
                   COUNT(DISTINCT o.order_id) AS frequency,
                   ROUND(SUM(oi.quantity * oi.unit_price), 2) AS monetary,
                   julianday('now') - julianday(MAX(o.order_date)) AS recency_days
            FROM customers c
            JOIN orders o ON c.customer_id = o.customer_id
            JOIN order_items oi ON o.order_id = oi.order_id
            WHERE o.status = 'Completed'
            GROUP BY c.customer_id, c.name
        )
        SELECT customer_id, name, frequency, monetary,
               ROUND(recency_days, 0) AS recency_days,
               CASE WHEN frequency = 1 THEN 'One-time'
                    WHEN frequency BETWEEN 2 AND 4 THEN 'Occasional'
                    ELSE 'Loyal' END AS frequency_segment,
               CASE WHEN monetary < 100 THEN 'Low'
                    WHEN monetary BETWEEN 100 AND 500 THEN 'Medium'
                    ELSE 'High' END AS spend_segment
        FROM customer_stats
        ORDER BY monetary DESC
    """,
}


def connect_db(db_path):
    if not os.path.exists(db_path):
        print(f"error: database file not found at '{db_path}'.")
        print("run 'python scripts/load_to_sql.py' first to create it.")
        sys.exit(1)
    try:
        conn = sqlite3.connect(db_path)
        conn.execute("SELECT 1")
        return conn
    except sqlite3.Error as e:
        print(f"error: could not connect to database '{db_path}': {e}")
        sys.exit(1)


def run_report(conn, report_name, limit):
    query = REPORTS[report_name]
    try:
        cur = conn.execute(query)
        rows = cur.fetchall()
        columns = [d[0] for d in cur.description]
    except sqlite3.Error as e:
        print(f"error: query for report '{report_name}' failed: {e}")
        sys.exit(1)

    if limit and limit > 0:
        rows = rows[:limit]
    return columns, rows


def format_output(report_name, columns, rows):
    if not rows:
        return f"\nreport: {report_name}\nno data found for this report.\n"
    table_str = tabulate(rows, headers=columns, tablefmt="grid")
    return f"\nreport: {report_name}  ({len(rows)} rows shown)\n\n{table_str}\n"


def main():
    parser = argparse.ArgumentParser(description="e-commerce order analytics cli reporting tool")
    parser.add_argument("--report", required=True, help="report to run, or 'list' to see all options")
    parser.add_argument("--db", default="ecommerce.db", help="path to sqlite database")
    parser.add_argument("--limit", type=int, default=20, help="max rows to display, 0 = no limit")
    parser.add_argument("--save", default=None, help="optional path to also save output as text")

    args = parser.parse_args()

    if args.report == "list":
        print("available reports:")
        for name in REPORTS:
            print(f"  - {name}")
        return

    if args.report not in REPORTS:
        print(f"error: unknown report '{args.report}'.")
        print("available reports:")
        for name in REPORTS:
            print(f"  - {name}")
        sys.exit(1)

    if args.limit < 0:
        print("error: --limit cannot be negative.")
        sys.exit(1)

    conn = connect_db(args.db)
    columns, rows = run_report(conn, args.report, args.limit)
    conn.close()

    output = format_output(args.report, columns, rows)
    print(output)

    if args.save:
        with open(args.save, "w") as f:
            f.write(output)
        print(f"saved to {args.save}")


if __name__ == "__main__":
    main()
