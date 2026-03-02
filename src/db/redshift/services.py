from typing import Any
import json
import uuid
import psycopg2
from psycopg2 import OperationalError, ProgrammingError
from psycopg2.extras import execute_values

from src.utils.utils import logging, to_sql_literal
from src.db.redshift.initialise import Initialise
from src.models.logs import Logs, ServerInfo, RequestInfo, MessageInfo, SourceInfo


class RedshiftServices:
    def __init__(self):
        self.init = Initialise()

    def run_query(self, query: str, params=None, fetch: bool = True):
        try:
            with self.init.connection.cursor() as cursor:
                cursor.execute(query, params)
                if fetch and cursor.description:
                    result = cursor.fetchall()
                    logging.info(f"Query executed successfully.")
                    return result
                logging.info(f"Query executed successfully (no result set).")
                return None
        except Exception as e:
            logging.error(f"Error executing query. Error: {str(e)}")
            return None


    @staticmethod
    def _jsonable(value: Any) -> Any:
        """Convert nested model/dict-ish data into something JSON serializable."""
        if value is None:
            return None
        if hasattr(value, "model_dump"):
            return value.model_dump(exclude_none=True)
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode()
            except Exception:
                return str(value)
        return value


    @classmethod
    def _normalize_row(cls, row: dict[str, Any]) -> dict[str, Any]:
        normalized: dict[str, Any] = {}
        for k, v in row.items():
            if v is None:
                continue
            if k in {"server_info", "request_info", "message_info", "source_info"}:
                json_obj = cls._jsonable(v)
                try:
                    normalized[k] = json.dumps(json_obj, ensure_ascii=False, default=str)
                except TypeError:
                    normalized[k] = json.dumps(str(json_obj), ensure_ascii=False)
            else:
                normalized[k] = v
        return normalized
  

    def insert_log(self, log_entry: dict[str, Any] | list[dict[str, Any]]):
        try:
            entries = log_entry if isinstance(log_entry, list) else [log_entry]
            if not entries:
                return None

            def payload_to_row(payload: Any) -> dict[str, Any]:
                if payload is None:
                    return {}
                if isinstance(payload, (bytes, bytearray)):
                    payload = payload.decode()
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        return self._normalize_row({"message_info": {"message": payload}})
                if isinstance(payload, Logs):
                    row = payload.model_dump(exclude_none=True)
                    return self._normalize_row(row)
                if isinstance(payload, dict):
                    row = {k: v for k, v in payload.items() if v is not None}
                    return self._normalize_row(row)
                return self._normalize_row({"message_info": {"message": str(payload)}})

            row_dicts: list[dict[str, Any]] = []
            for item in entries:
                if not isinstance(item, dict) or len(item) != 1:
                    raise ValueError(
                        "Each entry must be a dict with exactly one key-value pair: {redis_key: payload}"
                    )
                _, payload = next(iter(item.items()))
                row = payload_to_row(payload)
                row_dicts.append(row)

            if not any(row_dicts):
                return None

            # Inject a Python-generated UUID for each row (Redshift has no generateUUIDv4())
            for row in row_dicts:
                row.setdefault("log_id", str(uuid.uuid4()))

            columns_list = sorted({k for d in row_dicts for k in d.keys()})
            json_columns = {"server_info", "request_info", "message_info", "source_info"}

            # Build column clause; wrap SUPER columns with JSON_PARSE()
            col_clause = ", ".join(
                f"JSON_PARSE(%({col})s)" if col in json_columns else col
                for col in columns_list
            )

            # psycopg2 named-param style for clarity
            placeholders = ", ".join(
                f"JSON_PARSE(%({col})s)" if col in json_columns else f"%({col})s"
                for col in columns_list
            )

            query = f"INSERT INTO logs ({', '.join(columns_list)}) VALUES ({placeholders})"

            with self.init.connection.cursor() as cursor:
                for row in row_dicts:
                    # Fill missing columns with None
                    params = {col: row.get(col, None) for col in columns_list}
                    cursor.execute(query, params)

            logging.info(f"Inserted {len(row_dicts)} log(s) successfully.")
            return len(row_dicts)

        except ProgrammingError as pe:
            logging.error(f"SQL error inserting log entry: {pe}")
            return None
        except Exception as e:
            logging.error(f"Error inserting log entry: {log_entry}. Error: {str(e)}")
            return None


    def delete_logs(self, log_id: list[str] | str | None = None):
        try:
            if log_id is None:
                self.run_query("TRUNCATE TABLE logs", fetch=False)
                logging.info("All logs deleted successfully (TRUNCATE TABLE logs).")
                return True

            if isinstance(log_id, str):
                log_ids = [log_id.strip()]
            elif isinstance(log_id, list):
                log_ids = [str(x).strip() for x in log_id if str(x).strip()]
                if not log_ids:
                    raise ValueError("log_id list is empty after cleaning.")
            else:
                raise TypeError("log_id must be None, a string UUID, or a list of string UUIDs.")

            # Use %s placeholders; psycopg2 handles safe quoting
            placeholders = ", ".join(["%s"] * len(log_ids))
            query = f"DELETE FROM logs WHERE log_id IN ({placeholders})"

            with self.init.connection.cursor() as cursor:
                cursor.execute(query, log_ids)

            logging.info(f"Deleted {len(log_ids)} log(s) for id(s): {log_ids}")
            return True

        except ValueError as ve:
            logging.error(f"Validation error in delete_logs: {ve}")
        except TypeError as te:
            logging.error(f"Type error in delete_logs: {te}")
        except (OperationalError, ProgrammingError) as pe:
            logging.error(f"Redshift error while deleting logs: {pe}")
        except Exception as e:
            logging.error(f"Unexpected error while deleting logs: {e}")

        return None
    

    def fetch_logs(self, log_id: list[str] | str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
        try:
            def _parse_json_maybe(v: Any) -> Any:
                if v is None:
                    return None
                if isinstance(v, (bytes, bytearray)):
                    try:
                        v = v.decode()
                    except Exception:
                        return str(v)
                if isinstance(v, str):
                    s = v.strip()
                    if (s.startswith("{") and s.endswith("}")) or (s.startswith("[") and s.endswith("]")):
                        try:
                            return json.loads(s)
                        except Exception:
                            return v
                return v

            where_clause = ""
            params = []

            if log_id is not None:
                if isinstance(log_id, str):
                    ids = [log_id.strip()]
                elif isinstance(log_id, list):
                    ids = [str(x).strip() for x in log_id if str(x).strip()]
                    if not ids:
                        raise ValueError("log_id list is empty after cleaning.")
                else:
                    raise TypeError("log_id must be None, a string UUID, or a list of string UUIDs.")

                placeholders = ", ".join(["%s"] * len(ids))
                where_clause = f"WHERE log_id IN ({placeholders})"
                params = ids

            query = f"SELECT * FROM logs {where_clause} ORDER BY timestamp DESC"

            with self.init.connection.cursor() as cursor:
                cursor.execute(query, params or None)
                col_names = [desc[0] for desc in cursor.description]
                rows = cursor.fetchall()

            out: list[dict[str, Any]] = []
            for r in rows:
                d = {col_names[i]: (r[i] if i < len(r) else None) for i in range(len(col_names))}
                for k in ("server_info", "request_info", "message_info", "source_info"):
                    if k in d:
                        d[k] = _parse_json_maybe(d[k])
                out.append(d)

            if isinstance(log_id, str):
                return out[0] if out else {}

            return out

        except ValueError as ve:
            logging.error(f"Validation error in fetch_logs: {ve}")
        except TypeError as te:
            logging.error(f"Type error in fetch_logs: {te}")
        except (OperationalError, ProgrammingError) as pe:
            logging.error(f"Redshift error while fetching logs: {pe}")
        except Exception as e:
            logging.error(f"Unexpected error while fetching logs: {e}")

        return {} if isinstance(log_id, str) else []


if __name__ == "__main__":
    service = RedshiftServices()
    logs = service.fetch_logs()
    print(logs)