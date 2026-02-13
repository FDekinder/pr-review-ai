"""
Sample code with INTENTIONAL security vulnerabilities.
Used to test the Security Agent's detection capabilities.

DO NOT use this code in production! Every function here contains
a security flaw that the agent should find.
"""

import os
import pickle
import subprocess


# Issue 1: SQL Injection (Critical)
# The user input is directly interpolated into the SQL query.
# An attacker could input: ' OR '1'='1' -- to bypass authentication.
def get_user(username: str):
    query = f"SELECT * FROM users WHERE username = '{username}'"
    return db.execute(query)


# Issue 2: Command Injection (Critical)
# User input is passed directly to the shell.
# An attacker could input: "; rm -rf /" to execute arbitrary commands.
def convert_file(filename: str):
    os.system(f"convert {filename} output.pdf")


# Issue 3: Hardcoded Secret (High)
# API keys should NEVER be in source code. They should be in
# environment variables or a secrets manager.
API_KEY = "sk-proj-abc123def456ghi789"
DATABASE_PASSWORD = "super_secret_password_123"


# Issue 4: Insecure Deserialization (High)
# pickle.loads can execute arbitrary code during deserialization.
# An attacker who controls the data can achieve remote code execution.
def load_user_data(data: bytes):
    return pickle.loads(data)


# Issue 5: Path Traversal (Medium)
# User controls the filename, so they could request "../../etc/passwd"
# to read sensitive files outside the intended directory.
def read_file(filename: str):
    with open(f"/uploads/{filename}", "r") as f:
        return f.read()


# Issue 6: Subprocess with shell=True (High)
# shell=True passes the command through the system shell,
# enabling shell injection attacks.
def run_lint(filepath: str):
    result = subprocess.run(
        f"pylint {filepath}",
        shell=True,
        capture_output=True
    )
    return result.stdout
