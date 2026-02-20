import os
import logging
from contextlib import contextmanager
from functools import wraps
from psycopg2.extensions import connection as PGConnection, cursor as PGCursor
import psycopg2

from src.utils.utils import logging

from dotenv import load_dotenv

load_dotenv()

class QueryMode:
    NONE = "none"
    ALL = "all"
    ONE = "one"


class InitialiseDB:
    def __init__(self) -> None:
        self.connection: PGConnection = psycopg2.connect(
            host=os.getenv("DB_HOST"),
            port=os.getenv("DB_PORT"),
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASSWORD"),
        )
        self.connection.autocommit = False
        self.cursor: PGCursor = self.connection.cursor()
        
        
    def execute_query(self, query: str, params: tuple = None, fetch: QueryMode = None):
        try:
            self.cursor.execute(query, params)
            logging.info(f"Query executed successfully: {query} | params: {params}")

            if fetch == QueryMode.ALL:
                return self.cursor.fetchall()
            elif fetch == QueryMode.ONE:
                return self.cursor.fetchone()

            self.connection.commit()
            return None

        except Exception as e:
            self.connection.rollback()
            logging.error(f"Error executing query: {query}. Error: {str(e)}")
            return None

    def init_servers_table(self):
        try:
            create_table_query = """
            CREATE TABLE IF NOT EXISTS servers (
                server_id VARCHAR(255) PRIMARY KEY,
                server_name VARCHAR(255) UNIQUE NOT NULL,
                server_description TEXT,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            self.execute_query(create_table_query)
            return 
        except Exception as e:
            logging.error(f"Error initializing servers table: {str(e)}")
            return None

        
    def init_apps_table(self):
        try:
            create_table_query = """
            CREATE TABLE IF NOT EXISTS apps (
                app_id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
                app_serial SERIAL UNIQUE NOT NULL,
                app_name VARCHAR(255) UNIQUE NOT NULL,
                app_description TEXT,
                server_id VARCHAR(255) FOREIGN KEY REFERENCES servers(server_id),
                api_key ARRAY(TEXT),
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            );
            """
            self.execute_query(create_table_query)
            return 
        except Exception as e:
            logging.error(f"Error initializing apps table: {str(e)}")
            return None
        

    def close(self) -> None:
        try:
            if getattr(self, "cursor", None):
                self.cursor.close()
        finally:
            if getattr(self, "connection", None):
                self.connection.close()


@contextmanager
def db_session():
    db = InitialiseDB()
    try:
        yield db.connection, db.cursor
        db.connection.commit()
    except Exception:
        db.connection.rollback()
        logging.exception("Database operation failed. Rolled back for safety.")
        raise
    finally:
        db.close()


def database_init(func):
    """
    Decorator variant of db_session for standalone functions.
    Injects `connection` and `cursor` keyword args into the wrapped function.

    Usage:
        @database_init
        def do_something(*, connection, cursor):
            cursor.execute("SELECT 1")
            return cursor.fetchone()
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with db_session() as (connection, cursor):
            kwargs.setdefault("connection", connection)
            kwargs.setdefault("cursor", cursor)
            return func(*args, **kwargs)

    return wrapper


def main():
    dbi = InitialiseDB()
    dbi.init_servers_table()
    dbi.init_apps_table()
    dbi.close()

if __name__ == "__main__":
    main()