#!/usr/bin/env python3
"""Создать переносимый SQL-дамп БД в migrations/gira_full_clean.sql (из переменных .env)."""
from __future__ import annotations

import os
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OUT = ROOT / "migrations" / "gira_full_clean.sql"


def load_env(path: Path) -> dict[str, str]:
    d: dict[str, str] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip().strip("'\"")
    return d


def main() -> int:
    env_path = ROOT / ".env"
    if not env_path.is_file():
        print("Нет файла .env в корне проекта.", file=sys.stderr)
        return 1
    e = load_env(env_path)
    required = ("DB_HOST", "DB_PORT", "DB_NAME", "DB_USER", "DB_PASSWORD")
    missing = [k for k in required if k not in e]
    if missing:
        print(f"В .env не хватает: {', '.join(missing)}", file=sys.stderr)
        return 1

    env = os.environ.copy()
    env["PGPASSWORD"] = e["DB_PASSWORD"]
    cmd = [
        "pg_dump",
        "-h",
        e["DB_HOST"],
        "-p",
        str(e["DB_PORT"]),
        "-U",
        e["DB_USER"],
        "-d",
        e["DB_NAME"],
        "--clean",
        "--if-exists",
        "--no-owner",
        "--no-acl",
        "--encoding=UTF8",
        "-f",
        "-",
    ]
    r = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr or "pg_dump failed", file=sys.stderr)
        return r.returncode
    text = r.stdout
    # Пара \restrict / \unrestrict привязана к ключу pg_dump; без начальной \restrict
    # psql падает на \unrestrict — убираем обе строки для переносимого дампа.
    text = re.sub(r"^\\restrict .*\n", "", text, flags=re.MULTILINE)
    text = re.sub(r"^\\unrestrict .*\n", "", text, flags=re.MULTILINE)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(text, encoding="utf-8")
    print(f"OK: {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
