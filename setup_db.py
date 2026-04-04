"""Print the SQL schema required by the chatbot demo.

Run this script to display the CREATE TABLE statements needed for Supabase.
Optionally pass --output <path> to save the SQL to a file.
"""

from __future__ import annotations

import argparse
from pathlib import Path

SCHEMA_SQL = """-- Conversation metadata
create table if not exists conversation (
    id uuid primary key,
    created_at timestamp with time zone not null default now(),
    title text
);

-- Message history
create table if not exists messages (
    id uuid primary key,
    conversation_id uuid not null references conversation(id) on delete cascade,
    role text not null check (role in ('user', 'bot')),
    content text not null,
    created_at timestamp with time zone not null default now()
);

-- Laptop catalog
create table if not exists laptop (
    id bigserial primary key,
    name text not null,
    price integer,
    tags text
);

-- Printer catalog
create table if not exists printer (
    id bigserial primary key,
    name text not null,
    price integer,
    tags text
);

-- Troubleshooting knowledge base
create table if not exists troubleshooting (
    device text not null,
    issue text not null,
    steps text not null
);
"""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Print the Supabase schema SQL for the chatbot demo."
    )
    parser.add_argument(
        "--output",
        type=Path,
        help="Optional path to save the SQL instead of printing it only.",
    )
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    if args.output:
        args.output.write_text(SCHEMA_SQL, encoding="utf-8")
        print(f"Schema SQL written to {args.output}")

    print(SCHEMA_SQL)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
