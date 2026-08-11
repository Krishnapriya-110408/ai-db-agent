"""
Run this once to create a sample e-commerce SQLite database.
Usage: python create_sample_db.py
"""
import sqlite3
import random
from datetime import datetime, timedelta

conn = sqlite3.connect("ecommerce.db")
cur = conn.cursor()

cur.executescript("""
DROP TABLE IF EXISTS customers;
DROP TABLE IF EXISTS products;
DROP TABLE IF EXISTS orders;
DROP TABLE IF EXISTS order_items;

CREATE TABLE customers (
    customer_id INTEGER PRIMARY KEY,
    name TEXT,
    city TEXT,
    signup_date TEXT
);

CREATE TABLE products (
    product_id INTEGER PRIMARY KEY,
    product_name TEXT,
    category TEXT,
    price REAL,
    stock INTEGER
);

CREATE TABLE orders (
    order_id INTEGER PRIMARY KEY,
    customer_id INTEGER,
    order_date TEXT,
    status TEXT,
    FOREIGN KEY(customer_id) REFERENCES customers(customer_id)
);

CREATE TABLE order_items (
    item_id INTEGER PRIMARY KEY,
    order_id INTEGER,
    product_id INTEGER,
    quantity INTEGER,
    FOREIGN KEY(order_id) REFERENCES orders(order_id),
    FOREIGN KEY(product_id) REFERENCES products(product_id)
);
""")

cities = ["Chennai", "Bangalore", "Mumbai", "Delhi", "Hyderabad"]
categories = ["Electronics", "Clothing", "Groceries", "Books", "Home"]
products = [
    ("Wireless Mouse", "Electronics", 499),
    ("Bluetooth Speaker", "Electronics", 1299),
    ("Cotton T-Shirt", "Clothing", 399),
    ("Jeans", "Clothing", 1499),
    ("Rice Bag 5kg", "Groceries", 350),
    ("Cooking Oil 1L", "Groceries", 180),
    ("Novel - Fiction", "Books", 250),
    ("Notebook Set", "Books", 120),
    ("Table Lamp", "Home", 799),
    ("Bedsheet Set", "Home", 899),
]

for i, (name, cat, price) in enumerate(products, start=1):
    cur.execute("INSERT INTO products VALUES (?,?,?,?,?)",
                (i, name, cat, price, random.randint(20, 200)))

for i in range(1, 51):
    cur.execute("INSERT INTO customers VALUES (?,?,?,?)",
                (i, f"Customer {i}", random.choice(cities),
                 (datetime(2025, 1, 1) + timedelta(days=random.randint(0, 500))).strftime("%Y-%m-%d")))

order_id = 1
item_id = 1
for _ in range(200):
    cust = random.randint(1, 50)
    odate = (datetime(2025, 6, 1) + timedelta(days=random.randint(0, 400))).strftime("%Y-%m-%d")
    status = random.choice(["Delivered", "Pending", "Cancelled"])
    cur.execute("INSERT INTO orders VALUES (?,?,?,?)", (order_id, cust, odate, status))
    for _ in range(random.randint(1, 3)):
        prod = random.randint(1, 10)
        qty = random.randint(1, 5)
        cur.execute("INSERT INTO order_items VALUES (?,?,?,?)", (item_id, order_id, prod, qty))
        item_id += 1
    order_id += 1

conn.commit()
conn.close()
print("ecommerce.db created successfully with sample data.")
