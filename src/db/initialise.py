import clickhouse_connect
import os
import dotenv

from clickhouse_connect.driver.exceptions import ClickHouseError
from src.utils.utils import logging

dotenv.load_dotenv()


class Initialise:
    def __init__(self):
        try:
            self.host = os.getenv("CLICKHOUSE_HOST")
            self.username = os.getenv("CLICKHOUSE_USERNAME")
            self.password = os.getenv("CLICKHOUSE_PASSWORD")
            self.secure = os.getenv("CLICKHOUSE_SECURE", "false").lower() == "true"

            if not all([self.host, self.username, self.password]):
                raise ValueError("Missing required environment variables for ClickHouse connection.")

            self.client = clickhouse_connect.get_client(
                host=self.host,
                username=self.username,
                password=self.password,
                secure=self.secure,
            )

            logging.info("ClickHouse client initialised successfully.")

        except ValueError as ve:
            logging.error(f"Environment configuration error: {ve}")
            raise

        except ConnectionError as ce:
            logging.error(f"ClickHouse connection failed: {ce}")
            raise

        except Exception as e:
            logging.error(f"Unexpected error during ClickHouse initialisation: {e}")
            raise


    def create_logs_table(self):
        try:
            create_table_query = """
            CREATE TABLE IF NOT EXISTS logs (
                id UUID DEFAULT generateUUIDv4(),
                timestamp DateTime DEFAULT now(),
                event_name String,
                message String,
                description String,
                diagnostics String,
                source JSON
            ) ENGINE = MergeTree()
            ORDER BY (timestamp)
            """

            result = self.client.query(create_table_query)
            logging.info("Logs table created or already exists.")
            return result

        except SyntaxError as se:
            logging.error(f"SQL syntax error while creating logs table: {se}")

        except ClickHouseError as che:
            logging.error(f"ClickHouse error while creating logs table: {che}")

        except Exception as e:
            logging.error(f"Unexpected error while creating logs table: {e}")

        return None


    def delete_table(self, table_name: str):
        try:
            if not table_name:
                raise ValueError("Table name cannot be empty.")

            delete_table_query = f"DROP TABLE IF EXISTS {table_name}"

            result = self.client.query(delete_table_query)
            logging.info(f"Table '{table_name}' deleted successfully.")
            return result

        except ValueError as ve:
            logging.error(f"Validation error: {ve}")

        except SyntaxError as se:
            logging.error(f"SQL syntax error while deleting table '{table_name}': {se}")

        except ClickHouseError as che:
            logging.error(f"ClickHouse error while deleting table '{table_name}': {che}")

        except Exception as e:
            logging.error(f"Unexpected error while deleting table '{table_name}': {e}")

        return None


if __name__ == "__main__":
    try:
        initialise = Initialise()
        initialise.create_logs_table()
        logging.info("Initialisation flow completed.")

    except Exception as e:
        logging.critical(f"Fatal startup error: {e}")
