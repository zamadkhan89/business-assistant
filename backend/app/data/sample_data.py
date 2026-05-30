from app.data.duckdb_connector import get_conn


def load_sample_data() -> None:
    """Load Northwind-inspired e-commerce dataset into DuckDB (idempotent)."""
    conn = get_conn()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS customers (
            customer_id VARCHAR PRIMARY KEY,
            name        VARCHAR NOT NULL,
            email       VARCHAR,
            city        VARCHAR,
            country     VARCHAR
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS products (
            product_id     INTEGER PRIMARY KEY,
            name           VARCHAR NOT NULL,
            category       VARCHAR,
            unit_price     DECIMAL(10,2),
            units_in_stock INTEGER
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            order_id     INTEGER PRIMARY KEY,
            customer_id  VARCHAR,
            order_date   DATE,
            ship_country VARCHAR,
            freight      DECIMAL(10,2)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            order_item_id INTEGER PRIMARY KEY,
            order_id      INTEGER,
            product_id    INTEGER,
            quantity      INTEGER,
            unit_price    DECIMAL(10,2)
        )
    """)

    if conn.execute("SELECT COUNT(*) FROM customers").fetchone()[0] > 0:
        conn.close()
        return  # already loaded

    conn.execute("""
        INSERT INTO customers VALUES
            ('ALFKI', 'Alfreds Futterkiste',         'alfreds@example.com', 'Berlin',      'Germany'),
            ('ANATR', 'Ana Trujillo',                 'ana@example.com',     'Mexico City', 'Mexico'),
            ('BERGS', 'Berglunds snabbköp',           'bergs@example.com',   'Luleå',       'Sweden'),
            ('BOLID', 'Bólido Comidas preparadas',    'bolid@example.com',   'Madrid',      'Spain'),
            ('BONAP', 'Bon app',                      'bonap@example.com',   'Marseille',   'France'),
            ('BOTTM', 'Bottom-Dollar Markets',        'bottm@example.com',   'Tsawassen',   'Canada'),
            ('BSBEV', 'Bs Beverages',                 'bsbev@example.com',   'London',      'UK'),
            ('CACTU', 'Cactus Comidas para llevar',   'cactu@example.com',   'Buenos Aires','Argentina'),
            ('CENTC', 'Centro comercial Moctezuma',   'centc@example.com',   'Mexico City', 'Mexico'),
            ('CHOPS', 'Chop-suey Chinese',            'chops@example.com',   'Bern',        'Switzerland')
    """)

    conn.execute("""
        INSERT INTO products VALUES
            (1,  'Chai',                           'Beverages',     18.00, 39),
            (2,  'Chang',                          'Beverages',     19.00, 17),
            (3,  'Aniseed Syrup',                  'Condiments',    10.00, 13),
            (4,  'Chef Anton Cajun Seasoning',     'Condiments',    22.00, 53),
            (5,  'Chef Anton Gumbo Mix',           'Condiments',    21.35,  0),
            (6,  'Grandma Boysenberry Spread',     'Condiments',    25.00,120),
            (7,  'Uncle Bob Organic Dried Pears',  'Produce',       30.00, 15),
            (8,  'Northwoods Cranberry Sauce',     'Condiments',    40.00,  6),
            (9,  'Mishi Kobe Niku',                'Meat/Poultry',  97.00, 29),
            (10, 'Ikura',                          'Seafood',       31.00, 31),
            (11, 'Queso Cabrales',                 'Dairy Products',21.00, 22),
            (12, 'Queso Manchego La Pastora',      'Dairy Products',38.00, 86)
    """)

    conn.execute("""
        INSERT INTO orders VALUES
            (10248,'ALFKI','2024-07-04','Germany',    32.38),
            (10249,'ANATR','2024-07-05','Mexico',     11.61),
            (10250,'BERGS','2024-07-08','Sweden',     65.83),
            (10251,'ALFKI','2024-07-08','Germany',    41.34),
            (10252,'BOLID','2024-07-09','Spain',      51.30),
            (10253,'BONAP','2024-07-10','France',     58.17),
            (10254,'BOTTM','2024-07-11','Canada',     22.98),
            (10255,'BSBEV','2024-07-12','UK',        148.33),
            (10256,'CACTU','2024-07-15','Argentina',  13.97),
            (10257,'CENTC','2024-07-16','Mexico',     81.91),
            (10258,'CHOPS','2024-07-17','Switzerland',140.51),
            (10259,'ALFKI','2024-07-18','Germany',     3.25),
            (10260,'ANATR','2024-07-19','Mexico',     55.09),
            (10261,'BERGS','2024-07-19','Sweden',      3.05),
            (10262,'BOLID','2024-07-22','Spain',      48.29)
    """)

    conn.execute("""
        INSERT INTO order_items VALUES
            (1, 10248, 11, 12, 14.00),(2, 10248,  2, 10,  9.80),(3, 10248,  9,  5, 34.80),
            (4, 10249,  3,  9, 18.60),(5, 10249,  1, 40, 42.40),
            (6, 10250,  4, 10,  7.70),(7, 10250,  1, 35, 42.40),(8, 10250,  5, 15, 16.80),
            (9, 10251,  6,  6, 16.80),(10,10251,  7, 15, 15.60),
            (11,10252, 11, 40, 64.80),(12,10252,  3, 25,  2.00),
            (13,10253, 12, 20, 10.00),(14,10253,  8, 42, 14.40),
            (15,10254,  2, 15,  3.60),(16,10255, 10, 20, 15.20),(17,10255,  9, 35, 13.90),
            (18,10256,  3, 15, 26.20),(19,10257,  4, 25, 35.10),
            (20,10258,  2, 50, 15.20),(21,10259,  4, 16, 16.80),
            (22,10260,  4, 16,  7.70),(23,10261,  9, 20, 81.00)
    """)

    conn.close()
    print("[data] Sample dataset loaded into DuckDB")  # noqa: T201
