"""
Simple helper to connect to Postgres (Docker locally, or any Postgres via DATABASE_URL).
We import this in every tool that needs the database.
"""
import os
import psycopg2
from dotenv import load_dotenv

load_dotenv()


def get_db_connection():
    """
    Returns a Postgres connection.
    Reads DATABASE_URL from .env — works with Docker locally
    or any Postgres (Supabase, Neon, RDS) by just changing that one variable.
    """
    return psycopg2.connect(os.environ["DATABASE_URL"])
