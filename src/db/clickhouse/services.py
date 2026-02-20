import json
from datetime import datetime
from clickhouse_connect.driver.exceptions import ClickHouseError

from src.utils.utils import logging, to_sql_literal
from src.db.clickhouse.initialise import Initialise
from src.models.logs import Logs

class ClickHouseServices:
    def __init__(self,):
        self.init = Initialise()
    
    
    def run_query(self, query: str):
        try:
            result = self.init.client.query(query).result_set
            logging.info(f"Query executed successfully: {query}")
            return result
        except Exception as e:
            logging.error(f"Error executing query: {query}. Error: {str(e)}")
            return None
            
            
    def insert_log(self, log_entry: dict[Logs] | list[dict[str, Logs]]):
        try:
            entries = log_entry if isinstance(log_entry, list) else [log_entry]
            if not entries:
                return None

            dicts = [e.values().model_dump(exclude_none=True) for e in entries]
            columns_list = sorted({k for d in dicts for k in d.keys()})
            columns = ", ".join(columns_list)

            values_rows = []
            for d in dicts:
                row_vals = [to_sql_literal(d.get(col, None)) for col in columns_list]
                values_rows.append(f"({', '.join(row_vals)})")

            query = f"""
                INSERT INTO logs ({columns}) VALUES {', '.join(values_rows)}; 
                SELECT id FROM logs;
            """
            return self.run_query(query)

        except ClickHouseError as che:
            logging.error(f"ClickHouse error inserting log entry: {che}")
            return None
        except Exception as e:
            logging.error(f"Error inserting log entry: {log_entry}. Error: {str(e)}")
            return None



    def drop_logs(self, log_id: list[str] | str | None = None):
        try:
            if log_id is None:
                query = "TRUNCATE TABLE logs"
                result = self.client.query(query)
                logging.info("All logs deleted successfully (TRUNCATE TABLE logs).")
                return result

            if isinstance(log_id, str):
                log_ids = [log_id.strip()]

            elif isinstance(log_id, list):
                log_ids = [str(x).strip() for x in log_id if str(x).strip()]

                if not log_ids:
                    raise ValueError("log_id list is empty after cleaning.")

            else:
                raise TypeError("log_id must be None, a string UUID, or a list of string UUIDs.")

            ids_csv = ", ".join([f"'{x}'" for x in log_ids])
            query = f"ALTER TABLE logs DELETE WHERE id IN ({ids_csv})"

            result = self.client.query(query)
            logging.info(f"Deleted {len(log_ids)} log(s) for id(s): {log_ids}")
            return result

        except ValueError as ve:
            logging.error(f"Validation error in drop_logs_table: {ve}")

        except TypeError as te:
            logging.error(f"Type error in drop_logs_table: {te}")

        except ClickHouseError as che:
            logging.error(f"ClickHouse error while deleting logs: {che}")

        except Exception as e:
            logging.error(f"Unexpected error while deleting logs: {e}")

        return None

    
if __name__ == "__main__":
    service = ClickHouseServices()
    log_entry = Logs(
        event_name="Test Event",
        message="This is a test log entry.",
        description="This log entry is created for testing purposes.",
        diagnostics="No diagnostics available.",
        source={"UnitTest": True},
    )

    service.insert_log(log_entry)