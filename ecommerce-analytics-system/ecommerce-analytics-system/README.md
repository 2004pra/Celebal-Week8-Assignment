# E-Commerce Order Analytics System

An end-to-end data analytics pipeline for e-commerce order data — from
synthetic (intentionally messy) data generation, through Pandas cleaning
and validation, into a SQLite database, with SQL analytics (joins,
aggregations, window functions, CTEs, cohort/retention analysis) surfaced
through a command-line reporting tool.

## 1. Architecture

```
generate_data.py            clean_data.py              load_to_sql.py           report_cli.py
      │                            │                          │                        │
      ▼                            ▼                          ▼                        ▼
data/raw/*.csv  ───────►  data/cleaned/*.csv  ───────►  ecommerce.db  ───────►  formatted tables
(dirty, realistic)        (validated, consistent)       (SQLite, FK enforced)   (via SQL + tabulate)
```

- **Data generation** (`scripts/generate_data.py`): builds `customers`,
  `products`, `orders`, `order_items` with Faker, and deliberately injects
  nulls, duplicates, orphaned foreign keys, invalid/future dates, and bad
  numeric values (negative quantity, zero/negative price) — the same kinds
  of problems real-world exports have.
- **Cleaning** (`scripts/clean_data.py`): loads the raw CSVs into Pandas,
  fixes/removes the issues above, and re-validates referential integrity
  *across* tables (not just within one file) before writing to
  `data/cleaned/`. Every fix is logged to the console and to
  `output/sample_reports/cleaning_log.txt`.
- **Loading** (`scripts/load_to_sql.py`): creates the schema from
  `sql/schema.sql` (PK/FK/NOT NULL/CHECK constraints) in a SQLite database
  and loads the cleaned CSVs into it, then re-verifies row counts and that
  there are zero orphaned foreign keys.
- **Analytics** (`sql/*.sql`): standalone, reviewable SQL files covering
  joins & aggregations, window functions & CTEs, and cohort/retention/
  segmentation analysis.
- **Reporting** (`scripts/report_cli.py`): a CLI tool that runs any of the
  analytics queries against the database and prints/saves a formatted
  table, with input validation and graceful error handling.

## 2. Setup

```bash
pip install pandas faker tabulate
```

Python 3.9+ recommended. Uses the standard library `sqlite3` module, so no
separate database server is required.

## 3. How to Run (in order)

```bash
# 1. Generate raw, intentionally-dirty datasets
python scripts/generate_data.py

# 2. Clean & validate them with Pandas
python scripts/clean_data.py

# 3. Load the cleaned data into a SQLite database (ecommerce.db)
python scripts/load_to_sql.py

# 4. Run reports
python scripts/report_cli.py --report list                      # see all reports
python scripts/report_cli.py --report revenue_by_customer
python scripts/report_cli.py --report top_customers_ltv --limit 10
python scripts/report_cli.py --report retention --save output/sample_reports/retention.txt
```

### Available reports

| Report name            | What it shows                                             |
|-------------------------|-------------------------------------------------------------|
| `revenue_by_customer`   | Total revenue & order count per customer                    |
| `revenue_by_category`   | Total revenue & units sold per product category             |
| `revenue_by_month`      | Total revenue & order count per month                       |
| `top_products_qty`      | Top products by units sold                                  |
| `top_products_revenue`  | Top products by revenue                                     |
| `aov_by_segment`        | Average order value by customer segment                     |
| `top_customers_ltv`     | Customers ranked by lifetime value (`RANK`/`DENSE_RANK`)     |
| `running_revenue`       | Month-over-month running total of revenue (`SUM() OVER`)     |
| `moving_avg_revenue`    | 3-month moving average of revenue (`AVG() OVER`)             |
| `growth_rate`           | Month-over-month revenue growth rate (CTE + `LAG()`)         |
| `cohort_sizes`          | Customer count per first-purchase-month cohort               |
| `retention`             | Monthly retention rate per cohort                            |
| `churn_status`          | Repeat vs. churned vs. active customers                      |
| `segmentation`          | RFM-style segmentation: frequency tier + spend tier          |

### CLI options

```
--report NAME     required. Report to run, or 'list' to see all options.
--db PATH         path to the SQLite database (default: ecommerce.db)
--limit N         max rows to display, 0 = no limit (default: 20)
--save PATH       also write the output to a text file
```

## 4. Data Model

```
customers (customer_id PK)
    │ 1
    │
    │ N
orders (order_id PK, customer_id FK → customers)
    │ 1
    │
    │ N
order_items (order_item_id PK, order_id FK → orders, product_id FK → products)
    │ N
    │
    │ 1
products (product_id PK)
```

Constraints enforced in `sql/schema.sql`: all primary keys, all foreign
keys, `NOT NULL` on required fields, and `CHECK` constraints on `price`,
`quantity`, and `unit_price` to keep negative/zero values out of the
database (they're already filtered out in the cleaning step, but the
schema also refuses them as a second line of defense).

## 5. Data Quality: What Was Injected vs. What Was Cleaned

| Issue                                     | Injected in raw data | Handled in `clean_data.py`            |
|--------------------------------------------|----------------------|-----------------------------------------|
| Missing emails / phone numbers            | Yes                  | Filled with `'unknown'`                |
| Inconsistent name/email casing & whitespace| Yes                 | Normalized (`.strip()`, `.title()`/`.lower()`) |
| Exact duplicate rows (all 4 tables)       | Yes                  | Dropped via `drop_duplicates()`        |
| Missing product category                  | Yes                  | Filled with `'Uncategorized'`          |
| Zero / negative product price             | Yes                  | Rows dropped                           |
| Orders referencing a non-existent customer| Yes                  | Rows dropped (orphan FK)               |
| Unparseable / malformed order dates       | Yes                  | Rows dropped                           |
| Future-dated orders                       | Yes                  | Rows dropped                           |
| order_items referencing a non-existent order or product | Yes    | Rows dropped (orphan FK)               |
| Negative quantity                         | Yes                  | Rows dropped                           |
| Missing unit_price                        | Yes                  | Rows dropped                           |

Exact counts from the last run are in `output/sample_reports/cleaning_log.txt`.

## 6. Edge Cases Handled by the CLI Tool

- Unknown/misspelled `--report` name → prints an error and the full list of
  valid report names instead of crashing.
- `--report` omitted entirely → `argparse` prints usage and exits cleanly.
- Database file missing → friendly error message telling you to run
  `load_to_sql.py` first, instead of a raw `sqlite3` traceback.
- Query returns zero rows (e.g. an empty or freshly-created database) →
  prints "No data found for this report." instead of an empty/broken table.
- Negative `--limit` → rejected with a clear error before any query runs.

## 7. Known Simplifications

- Uses SQLite for portability (no server setup needed to run/grade this).
  The SQL in `sql/*.sql` is close to standard ANSI SQL; the only
  SQLite-specific pieces are `strftime()` for date formatting and
  `julianday()` for date arithmetic — the equivalent in Postgres would be
  `to_char()`/date subtraction, and in MySQL `DATE_FORMAT()`/`DATEDIFF()`.
- "Churned" is defined as a single completed order more than 90 days ago —
  a reasonable default threshold, not a business-validated one.
- Revenue figures only count orders with `status = 'Completed'` (cancelled,
  pending, and refunded orders are excluded from all revenue reports).

## 8. Project Structure

```
ecommerce-analytics-system/
│── data/
│   ├── raw/                 # output of generate_data.py (dirty data)
│   └── cleaned/              # output of clean_data.py (validated data)
│── scripts/
│   ├── generate_data.py      # Step 1
│   ├── clean_data.py         # Step 2
│   ├── load_to_sql.py        # Step 3
│   └── report_cli.py         # Steps 8-9
│── sql/
│   ├── schema.sql            # Step 3
│   ├── aggregations.sql      # Step 4
│   ├── window_functions.sql  # Step 5
│   └── cohort_analysis.sql   # Steps 6-7
│── output/
│   └── sample_reports/       # saved output of every report + cleaning log
│── ecommerce.db               # generated by load_to_sql.py (not committed if .gitignore'd)
│── README.md
```

## 9. Sample Output

`output/sample_reports/revenue_by_month.txt`:

```
Report: revenue_by_month  (15 rows shown)

+---------------+-----------------+----------------+
| order_month   |   total_revenue |   total_orders |
+===============+=================+================+
| 2024-01       |          189872 |             83 |
| 2024-02       |          126712 |             57 |
| 2024-03       |          161556 |             75 |
| 2024-04       |          143875 |             58 |
| 2024-05       |          158409 |             71 |
...
```

See `output/sample_reports/` for the full output of every report.
