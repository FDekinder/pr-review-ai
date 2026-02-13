"""
Sample code with INTENTIONAL performance problems.
Used to test the Performance Agent's detection capabilities.

Each function demonstrates a common performance anti-pattern
that the agent should identify and suggest improvements for.
"""

import time


# Issue 1: O(n^2) nested loop (High)
# This checks every pair of items. For 10,000 items, that's 100,000,000 comparisons.
# A set-based approach would be O(n).
def find_duplicates(items: list) -> list:
    duplicates = []
    for i in range(len(items)):
        for j in range(i + 1, len(items)):
            if items[i] == items[j]:
                duplicates.append(items[i])
    return duplicates


# Issue 2: N+1 Query Problem (Critical for web apps)
# For each user, we make a separate database call to get their orders.
# With 1000 users, that's 1001 queries. Should use a JOIN or eager loading.
def get_users_with_orders():
    users = db.query("SELECT * FROM users")  # 1 query
    for user in users:
        user.orders = db.query(
            f"SELECT * FROM orders WHERE user_id = {user.id}"  # N queries
        )
    return users


# Issue 3: String concatenation in loop (Medium)
# Strings are immutable in Python. Each += creates a new string object
# and copies all previous content. Use ''.join() instead.
def build_report(items: list) -> str:
    report = ""
    for item in items:
        report += f"Item: {item.name}, Price: {item.price}\n"
    return report


# Issue 4: Repeated computation (Medium)
# fibonacci(n-1) and fibonacci(n-2) recalculate the same values many times.
# fibonacci(30) makes ~2.7 million function calls. Use memoization.
def fibonacci(n: int) -> int:
    if n <= 1:
        return n
    return fibonacci(n - 1) + fibonacci(n - 2)


# Issue 5: Loading entire file into memory (High)
# For a 10GB file, this would try to load everything into RAM at once.
# Should read line by line or in chunks.
def count_lines(filepath: str) -> int:
    content = open(filepath).read()
    return content.count("\n")


# Issue 6: Synchronous blocking in async context (Critical)
# time.sleep() blocks the entire event loop, preventing other async
# tasks from running. Should use asyncio.sleep() instead.
async def process_items(items: list):
    for item in items:
        time.sleep(1)  # Blocks the event loop!
        await save_to_db(item)
