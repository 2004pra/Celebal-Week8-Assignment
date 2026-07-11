import random
from datetime import datetime

import pandas as pd
from faker import Faker

fake = Faker()
Faker.seed(42)
random.seed(42)

N_CUSTOMERS = 800
N_PRODUCTS = 150
N_ORDERS = 4000
CATEGORIES = ["Electronics", "Apparel", "Home & Kitchen", "Books",
              "Beauty", "Sports", "Toys", "Groceries"]
OUT_DIR = "data/raw"


def generate_customers(n=N_CUSTOMERS):
    rows = []
    start_date = datetime(2023, 1, 1)
    end_date = datetime(2026, 6, 30)

    for i in range(1, n + 1):
        name = fake.name()
        email = fake.email()
        phone = fake.phone_number()
        signup_date = fake.date_between(start_date=start_date, end_date=end_date)
        city = fake.city()
        segment = random.choice(["Regular", "Premium", "VIP"])

        # dirty data injection
        if random.random() < 0.05:
            email = None
        if random.random() < 0.04:
            phone = None
        if random.random() < 0.03:
            name = f"  {name.upper()}  "
        if random.random() < 0.02 and email:
            email = email.upper()

        rows.append({
            "customer_id": i, "name": name, "email": email, "phone": phone,
            "city": city, "signup_date": signup_date, "segment": segment,
        })

    df = pd.DataFrame(rows)
    dupes = df.sample(n=15, random_state=1)
    df = pd.concat([df, dupes], ignore_index=True)
    return df


def generate_products(n=N_PRODUCTS):
    rows = []
    for i in range(1, n + 1):
        category = random.choice(CATEGORIES)
        price = round(random.uniform(5, 500), 2)

        if random.random() < 0.04:
            category = None
        if random.random() < 0.02:
            price = round(random.uniform(-50, -1), 2)
        if random.random() < 0.02:
            price = 0.0

        rows.append({
            "product_id": i, "product_name": fake.catch_phrase(),
            "category": category, "price": price,
        })
    return pd.DataFrame(rows)


def generate_orders(customers_df, n=N_ORDERS):
    valid_customer_ids = customers_df["customer_id"].unique().tolist()
    rows = []
    start_date = datetime(2024, 1, 1)
    end_date = datetime(2026, 6, 30)

    for i in range(1, n + 1):
        customer_id = random.choice(valid_customer_ids)
        if random.random() < 0.02:
            customer_id = max(valid_customer_ids) + random.randint(1000, 9999)

        order_date = fake.date_time_between(start_date=start_date, end_date=end_date)

        r = random.random()
        if r < 0.015:
            order_date = "not_a_date"
        elif r < 0.03:
            order_date = datetime(2027, random.randint(1, 12), random.randint(1, 28))
        elif r < 0.04:
            order_date = ""

        status = random.choice(["Completed", "Completed", "Completed",
                                 "Cancelled", "Pending", "Refunded"])

        rows.append({
            "order_id": i, "customer_id": customer_id,
            "order_date": order_date, "status": status,
        })

    df = pd.DataFrame(rows)
    dupes = df.sample(n=20, random_state=2)
    df = pd.concat([df, dupes], ignore_index=True)
    return df


def generate_order_items(orders_df, products_df):
    valid_order_ids = orders_df["order_id"].unique().tolist()
    valid_product_ids = products_df["product_id"].unique().tolist()
    price_lookup = products_df.set_index("product_id")["price"].to_dict()

    rows = []
    item_id = 1
    for order_id in valid_order_ids:
        n_items = random.randint(1, 5)
        for _ in range(n_items):
            product_id = random.choice(valid_product_ids)
            if random.random() < 0.015:
                product_id = max(valid_product_ids) + random.randint(1000, 9999)

            oid = order_id
            if random.random() < 0.01:
                oid = max(valid_order_ids) + random.randint(1000, 9999)

            quantity = random.randint(1, 5)
            unit_price = price_lookup.get(product_id, round(random.uniform(5, 500), 2))

            if random.random() < 0.015:
                quantity = -quantity
            if random.random() < 0.01:
                unit_price = None

            rows.append({
                "order_item_id": item_id, "order_id": oid, "product_id": product_id,
                "quantity": quantity, "unit_price": unit_price,
            })
            item_id += 1

    df = pd.DataFrame(rows)
    dupes = df.sample(n=25, random_state=3)
    df = pd.concat([df, dupes], ignore_index=True)
    return df


def main():
    print("generating customers...")
    customers_df = generate_customers()
    print("generating products...")
    products_df = generate_products()
    print("generating orders...")
    orders_df = generate_orders(customers_df)
    print("generating order_items...")
    order_items_df = generate_order_items(orders_df, products_df)

    customers_df.to_csv(f"{OUT_DIR}/customers.csv", index=False)
    products_df.to_csv(f"{OUT_DIR}/products.csv", index=False)
    orders_df.to_csv(f"{OUT_DIR}/orders.csv", index=False)
    order_items_df.to_csv(f"{OUT_DIR}/order_items.csv", index=False)

    print(f"\ndone. raw files written to {OUT_DIR}/")
    print(f"  customers.csv    : {len(customers_df)} rows")
    print(f"  products.csv     : {len(products_df)} rows")
    print(f"  orders.csv       : {len(orders_df)} rows")
    print(f"  order_items.csv  : {len(order_items_df)} rows")


if __name__ == "__main__":
    main()
