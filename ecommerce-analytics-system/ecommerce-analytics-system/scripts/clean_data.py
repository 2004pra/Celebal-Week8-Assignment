import pandas as pd

RAW_DIR = "data/raw"
CLEAN_DIR = "data/cleaned"
log = []


def note(msg):
    log.append(msg)
    print(msg)


def clean_customers():
    df = pd.read_csv(f"{RAW_DIR}/customers.csv")
    before = len(df)

    df["name"] = df["name"].fillna("Unknown").astype(str).str.strip().str.title()
    df["email"] = df["email"].fillna("unknown").astype(str).str.strip().str.lower()
    df["phone"] = df["phone"].fillna("unknown")

    n_dupes = df.duplicated().sum()
    df = df.drop_duplicates()

    n_missing_email = (df["email"] == "unknown").sum()
    n_missing_phone = (df["phone"] == "unknown").sum()

    note(f"[customers] {before} raw rows -> {len(df)} cleaned rows ({n_dupes} duplicates removed)")
    note(f"[customers] {n_missing_email} missing emails filled, {n_missing_phone} missing phones filled")
    return df


def clean_products():
    df = pd.read_csv(f"{RAW_DIR}/products.csv")
    before = len(df)

    n_missing_cat = df["category"].isna().sum()
    df["category"] = df["category"].fillna("Uncategorized")

    n_bad_price = (df["price"] <= 0).sum()
    df = df[df["price"] > 0].copy()

    note(f"[products] {before} raw rows -> {len(df)} cleaned rows")
    note(f"[products] {n_missing_cat} missing categories filled, {n_bad_price} bad prices removed")
    return df


def clean_orders(customers_df):
    df = pd.read_csv(f"{RAW_DIR}/orders.csv")
    before = len(df)

    n_dupes = df.duplicated().sum()
    df = df.drop_duplicates()

    # format='mixed' avoids pandas silently marking valid dates as NaT
    # when the column has inconsistent formats
    df["order_date_parsed"] = pd.to_datetime(df["order_date"], errors="coerce", format="mixed")
    n_unparseable = df["order_date_parsed"].isna().sum()
    df = df[df["order_date_parsed"].notna()].copy()

    today = pd.Timestamp.now()
    n_future = (df["order_date_parsed"] > today).sum()
    df = df[df["order_date_parsed"] <= today].copy()

    valid_customers = set(customers_df["customer_id"])
    n_orphan = (~df["customer_id"].isin(valid_customers)).sum()
    df = df[df["customer_id"].isin(valid_customers)].copy()

    df["order_date"] = df["order_date_parsed"].dt.strftime("%Y-%m-%d %H:%M:%S")
    df = df.drop(columns=["order_date_parsed"])

    note(f"[orders] {before} raw rows -> {len(df)} cleaned rows ({n_dupes} duplicates removed)")
    note(f"[orders] {n_unparseable} unparseable dates removed, {n_future} future dates removed")
    note(f"[orders] {n_orphan} rows with unknown customer_id removed")
    return df


def clean_order_items(orders_df, products_df):
    df = pd.read_csv(f"{RAW_DIR}/order_items.csv")
    before = len(df)

    n_dupes = df.duplicated().sum()
    df = df.drop_duplicates()

    valid_orders = set(orders_df["order_id"])
    valid_products = set(products_df["product_id"])

    n_orphan_order = (~df["order_id"].isin(valid_orders)).sum()
    df = df[df["order_id"].isin(valid_orders)].copy()

    n_orphan_product = (~df["product_id"].isin(valid_products)).sum()
    df = df[df["product_id"].isin(valid_products)].copy()

    n_bad_qty = (df["quantity"] <= 0).sum()
    df = df[df["quantity"] > 0].copy()

    n_missing_price = df["unit_price"].isna().sum()
    df = df[df["unit_price"].notna()].copy()

    note(f"[order_items] {before} raw rows -> {len(df)} cleaned rows ({n_dupes} duplicates removed)")
    note(f"[order_items] {n_orphan_order} unknown order_id, {n_orphan_product} unknown product_id removed")
    note(f"[order_items] {n_bad_qty} bad quantities, {n_missing_price} missing prices removed")
    return df


def main():
    note("=== starting data cleaning ===\n")

    customers_df = clean_customers()
    print()
    products_df = clean_products()
    print()
    orders_df = clean_orders(customers_df)
    print()
    order_items_df = clean_order_items(orders_df, products_df)
    print()

    customers_df.to_csv(f"{CLEAN_DIR}/customers_clean.csv", index=False)
    products_df.to_csv(f"{CLEAN_DIR}/products_clean.csv", index=False)
    orders_df.to_csv(f"{CLEAN_DIR}/orders_clean.csv", index=False)
    order_items_df.to_csv(f"{CLEAN_DIR}/order_items_clean.csv", index=False)

    note("=== cleaning complete. files written to data/cleaned/ ===")

    with open("output/sample_reports/cleaning_log.txt", "w") as f:
        f.write("\n".join(log))


if __name__ == "__main__":
    main()
