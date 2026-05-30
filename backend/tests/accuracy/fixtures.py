"""
20 accuracy test fixtures for the business assistant.

Each fixture has:
  id          — short identifier
  question    — natural language question (sent to generate_sql)
  description — what correct answer looks like
  check       — callable(rows: list[dict]) -> bool
  expected    — human-readable expected answer string (for reporting)
"""
from __future__ import annotations


def _first_int(rows: list[dict], expected: int) -> bool:
    if not rows:
        return False
    val = list(rows[0].values())[0]
    try:
        return int(val) == expected
    except (TypeError, ValueError):
        return False


def _first_approx(rows: list[dict], expected: float, tol: float = 1.0) -> bool:
    if not rows:
        return False
    val = list(rows[0].values())[0]
    try:
        return abs(float(val) - expected) <= tol
    except (TypeError, ValueError):
        return False


def _any_cell_contains(rows: list[dict], substring: str) -> bool:
    if not rows:
        return False
    for cell in rows[0].values():
        if isinstance(cell, str) and substring.lower() in cell.lower():
            return True
    return False


def _date_contains(rows: list[dict], date_str: str) -> bool:
    if not rows:
        return False
    val = str(list(rows[0].values())[0])
    return date_str in val


QUESTIONS: list[dict] = [
    {
        "id": "Q01",
        "question": "How many customers are there?",
        "description": "Count all rows in customers table",
        "check": lambda rows: _first_int(rows, 10),
        "expected": "10",
    },
    {
        "id": "Q02",
        "question": "How many products do we sell?",
        "description": "Count all rows in products table",
        "check": lambda rows: _first_int(rows, 12),
        "expected": "12",
    },
    {
        "id": "Q03",
        "question": "How many orders are in the database?",
        "description": "Count all rows in orders table",
        "check": lambda rows: _first_int(rows, 15),
        "expected": "15",
    },
    {
        "id": "Q04",
        "question": "How many order items are there in total?",
        "description": "Count all rows in order_items table",
        "check": lambda rows: _first_int(rows, 23),
        "expected": "23",
    },
    {
        "id": "Q05",
        "question": "What is the most expensive product by unit price?",
        "description": "product with highest unit_price = Mishi Kobe Niku (97.00)",
        "check": lambda rows: _any_cell_contains(rows, "Mishi"),
        "expected": "Mishi Kobe Niku",
    },
    {
        "id": "Q06",
        "question": "How many products are currently out of stock?",
        "description": "Products where units_in_stock = 0; answer = 1",
        "check": lambda rows: _first_int(rows, 1),
        "expected": "1",
    },
    {
        "id": "Q07",
        "question": "How many distinct product categories are there?",
        "description": "COUNT(DISTINCT category) from products = 6",
        "check": lambda rows: _first_int(rows, 6),
        "expected": "6",
    },
    {
        "id": "Q08",
        "question": "What is the total revenue from all order items?",
        "description": "SUM(quantity * unit_price) from order_items = 12785.00",
        "check": lambda rows: _first_approx(rows, 12785.0, tol=1.0),
        "expected": "12785.00",
    },
    {
        "id": "Q09",
        "question": "How many orders were shipped to Germany?",
        "description": "COUNT orders WHERE ship_country = 'Germany' = 3",
        "check": lambda rows: _first_int(rows, 3),
        "expected": "3",
    },
    {
        "id": "Q10",
        "question": "How many unique countries received orders?",
        "description": "COUNT(DISTINCT ship_country) from orders = 9",
        "check": lambda rows: _first_int(rows, 9),
        "expected": "9",
    },
    {
        "id": "Q11",
        "question": "What is the cheapest product by unit price?",
        "description": "product with lowest unit_price = Aniseed Syrup (10.00)",
        "check": lambda rows: _any_cell_contains(rows, "Aniseed"),
        "expected": "Aniseed Syrup",
    },
    {
        "id": "Q12",
        "question": "How many products are in the Condiments category?",
        "description": "COUNT products WHERE category = 'Condiments' = 5",
        "check": lambda rows: _first_int(rows, 5),
        "expected": "5",
    },
    {
        "id": "Q13",
        "question": "What is the total freight cost across all orders?",
        "description": "SUM(freight) from orders = 778.01",
        "check": lambda rows: _first_approx(rows, 778.01, tol=0.5),
        "expected": "778.01",
    },
    {
        "id": "Q14",
        "question": "How many orders has the customer ALFKI placed?",
        "description": "COUNT orders WHERE customer_id = 'ALFKI' = 3",
        "check": lambda rows: _first_int(rows, 3),
        "expected": "3",
    },
    {
        "id": "Q15",
        "question": "How many products are in the Beverages category?",
        "description": "COUNT products WHERE category = 'Beverages' = 2",
        "check": lambda rows: _first_int(rows, 2),
        "expected": "2",
    },
    {
        "id": "Q16",
        "question": "What is the total quantity of items sold across all order lines?",
        "description": "SUM(quantity) from order_items = 496",
        "check": lambda rows: _first_approx(rows, 496.0, tol=0.5),
        "expected": "496",
    },
    {
        "id": "Q17",
        "question": "How many products have more than 20 units in stock?",
        "description": "COUNT products WHERE units_in_stock > 20 = 7",
        "check": lambda rows: _first_int(rows, 7),
        "expected": "7",
    },
    {
        "id": "Q18",
        "question": "What is the most recent order date?",
        "description": "MAX(order_date) from orders = 2024-07-22",
        "check": lambda rows: _date_contains(rows, "2024-07-22"),
        "expected": "2024-07-22",
    },
    {
        "id": "Q19",
        "question": "Which product generated the highest total revenue (sum of quantity times unit price)?",
        "description": "Chai with 3180.00 (40*42.40 + 35*42.40)",
        "check": lambda rows: _any_cell_contains(rows, "Chai"),
        "expected": "Chai",
    },
    {
        "id": "Q20",
        "question": "How many orders were shipped to Mexico?",
        "description": "COUNT orders WHERE ship_country = 'Mexico' = 3",
        "check": lambda rows: _first_int(rows, 3),
        "expected": "3",
    },
]
