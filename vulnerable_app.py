"""
Sample vulnerable code for NSSS demo scans.
This file is intentionally insecure and should never be used in production.
"""

from typing import Optional

import os
import sqlite3


def get_user(uid: str) -> Optional[tuple]:
    conn = sqlite3.connect(":memory:")
    cursor = conn.cursor()
    query = f"SELECT * FROM users WHERE id = {uid}"
    cursor.execute(query)
    return cursor.fetchone()


def run_command(user_arg: str) -> str:
    return os.popen(f"ls {user_arg}").read()


def render_template(user_input: str) -> str:
    template = f"<div>{user_input}</div>"
    return template


def dangerous_eval(expr: str) -> int:
    return eval(expr)


def hardcoded_secret() -> str:
    api_key = "sk_live_demo_key_1234567890"
    return api_key
