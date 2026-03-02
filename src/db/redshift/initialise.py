import os
import dotenv
import psycopg2
from psycopg2 import OperationalError, ProgrammingError
from src.utils.utils import logging

dotenv.load_dotenv()


class Initialise:
    def __init__(self):
        try:
            self.host = os.getenv("REDSHIFT_HOST")
            self.port = int(os.getenv("REDSHIFT_PORT", "5439"))
            self.database = os.getenv("REDSHIFT_DATABASE")
            self.username = os.getenv("REDSHIFT_USERNAME")
            self.password = os.getenv("REDSHIFT_PASSWORD")

            if not all([self.host, self.database, self.username, self.password]):
                raise ValueError("Missing required environment variables for Redshift connection.")

            self.connection = psycopg2.connect(
                host=self.host,
                port=self.port,
                dbname=self.database,
                user=self.username,
                password=self.password,
                connect_timeout=5,
                sslmode="require",
            )
            self.connection.autocommit = True

            logging.info("Redshift client initialised successfully.")

        except ValueError as ve:
            logging.error(f"Environment configuration error: {ve}")
            raise

        except OperationalError as oe:
            logging.error(f"Redshift connection failed: {oe}")
            raise

        except Exception as e:
            logging.error(f"Unexpected error during Redshift initialisation: {e}")
            raise


    def _execute(self, query: str):
        """Helper to execute a query using a cursor."""
        with self.connection.cursor() as cursor:
            cursor.execute(query)


    def create_logs_table(self):
        try:
            create_table_query = """
                CREATE TABLE IF NOT EXISTS logs
                (
                    log_id      VARCHAR(36)         DEFAULT REPLACE(CAST(GETDATE() AS VARCHAR), ' ', '-'),

                    timestamp   TIMESTAMP           DEFAULT GETDATE(),
                    event_type  VARCHAR(255),
                    event_name  VARCHAR(255),
                    event_category VARCHAR(255),

                    -- Semi-structured columns using Redshift SUPER type (replaces ClickHouse JSON)
                    server_info  SUPER,
                    request_info SUPER,
                    message_info SUPER,
                    source_info  SUPER
                )
                DISTSTYLE AUTO
                SORTKEY (timestamp);
            """

            self._execute(create_table_query)
            logging.info("Logs table created or already exists.")

        except ProgrammingError as pe:
            logging.error(f"SQL error while creating logs table: {pe}")

        except OperationalError as oe:
            logging.error(f"Redshift error while creating logs table: {oe}")

        except Exception as e:
            logging.error(f"Unexpected error while creating logs table: {e}")


    def delete_table(self, table_name: str):
        try:
            if not table_name:
                raise ValueError("Table name cannot be empty.")

            delete_table_query = f"DROP TABLE IF EXISTS {table_name}"

            self._execute(delete_table_query)
            logging.info(f"Table '{table_name}' deleted successfully.")

        except ValueError as ve:
            logging.error(f"Validation error: {ve}")

        except ProgrammingError as pe:
            logging.error(f"SQL error while deleting table '{table_name}': {pe}")

        except OperationalError as oe:
            logging.error(f"Redshift error while deleting table '{table_name}': {oe}")

        except Exception as e:
            logging.error(f"Unexpected error while deleting table '{table_name}': {e}")


    def close(self):
        """Always close the connection when done."""
        if self.connection and not self.connection.closed:
            self.connection.close()
            logging.info("Redshift connection closed.")


if __name__ == "__main__":
    initialise = None
    try:
        initialise = Initialise()
        initialise.create_logs_table()
        logging.info("Initialisation flow completed.")

    except Exception as e:
        logging.critical(f"Fatal startup error: {e}")

    finally:
        if initialise:
            initialise.close()