from typing import Any
import json
from clickhouse_connect.driver.exceptions import ClickHouseError

from src.utils.utils import logging, to_sql_literal
from src.db.clickhouse.initialise import Initialise
from src.models.logs import Logs, ServerInfo, RequestInfo, MessageInfo, SourceInfo


class ClickHouseServices:
    def __init__(self):
        self.init = Initialise()

    def run_query(self, query: str):
        try:
            result = self.init.client.query(query).result_set
            logging.info(f"Query executed successfully: {query}")
            return result
        except Exception as e:
            logging.error(f"Error executing query: {query}. Error: {str(e)}")
            return None

    @staticmethod
    def _jsonable(value: Any) -> Any:
        """
        Convert nested model/dict-ish data into something JSON serializable.
        """
        if value is None:
            return None

        # Pydantic models
        if hasattr(value, "model_dump"):
            return value.model_dump(exclude_none=True)

        # bytes
        if isinstance(value, (bytes, bytearray)):
            try:
                return value.decode()
            except Exception:
                return str(value)

        # dict/list/primitive already JSONable (mostly)
        return value

    @classmethod
    def _normalize_row(self, row: dict[str, Any]) -> dict[str, Any]:
        """
        Ensures Logs nested fields are stored in ClickHouse as JSON strings
        for columns: server_info, request_info, message_info, source.
        """
        normalized: dict[str, Any] = {}

        for k, v in row.items():
            if v is None:
                continue

            if k in {"server_info", "request_info", "message_info", "source"}:
                # Store nested structures as JSON text in ClickHouse
                json_obj = self._jsonable(v)
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

                # bytes/bytearray -> str
                if isinstance(payload, (bytes, bytearray)):
                    payload = payload.decode()

                # string -> try JSON else treat as message text
                if isinstance(payload, str):
                    try:
                        payload = json.loads(payload)
                    except json.JSONDecodeError:
                        # minimal compatible row
                        return self._normalize_row({"message_info": {"message": payload}})

                # Logs model -> dump and normalize nested fields
                if isinstance(payload, Logs):
                    row = payload.model_dump(exclude_none=True)
                    return self._normalize_row(row)

                # Dict payload -> keep non-null keys; normalize nested fields if present
                if isinstance(payload, dict):
                    row = {k: v for k, v in payload.items() if v is not None}
                    return self._normalize_row(row)

                # Fallback -> treat as message
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

            # Build INSERT with union of keys across rows
            columns_list = sorted({k for d in row_dicts for k in d.keys()})
            columns = ", ".join(columns_list)

            values_rows: list[str] = []
            for d in row_dicts:
                row_vals = [to_sql_literal(d.get(col, None)) for col in columns_list]
                values_rows.append(f"({', '.join(row_vals)})")

            query = f"INSERT INTO logs ({columns}) VALUES {', '.join(values_rows)}"
            self.run_query(query)
            return len(row_dicts)

        except ClickHouseError as che:
            logging.error(f"ClickHouse error inserting log entry: {che}")
            return None
        except Exception as e:
            logging.error(f"Error inserting log entry: {log_entry}. Error: {str(e)}")
            return None


    def delete_logs(self, log_id: list[str] | str | None = None):
        try:
            if log_id is None:
                query = "TRUNCATE TABLE logs"
                result = self.init.client.query(query)
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

            result = self.init.client.query(query)
            logging.info(f"Deleted {len(log_ids)} log(s) for id(s): {log_ids}")
            return result

        except ValueError as ve:
            logging.error(f"Validation error in delete_logs: {ve}")
        except TypeError as te:
            logging.error(f"Type error in delete_logs: {te}")
        except ClickHouseError as che:
            logging.error(f"ClickHouse error while deleting logs: {che}")
        except Exception as e:
            logging.error(f"Unexpected error while deleting logs: {e}")

        return None


    def fetch_logs(self, log_id: list[str] | str | None = None) -> list[dict[str, Any]] | dict[str, Any]:
        try:
            columns = self.init.client.query("DESCRIBE TABLE logs").result_set
            col_names = [c[0] for c in columns if c and c[0]]

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
            if log_id is not None:
                if isinstance(log_id, str):
                    ids = [log_id.strip()]
                elif isinstance(log_id, list):
                    ids = [str(x).strip() for x in log_id if str(x).strip()]
                    if not ids:
                        raise ValueError("log_id list is empty after cleaning.")
                else:
                    raise TypeError("log_id must be None, a string UUID, or a list of string UUIDs.")

                ids_csv = ", ".join([to_sql_literal(x) for x in ids])
                where_clause = f"WHERE log_id IN ({ids_csv})"

            query = f"SELECT * FROM logs {where_clause} ORDER BY timestamp DESC"
            rows = self.run_query(query) or []

            out: list[dict[str, Any]] = []
            for r in rows:
                d = {col_names[i]: (r[i] if i < len(r) else None) for i in range(len(col_names))}
                for k in ("server_info", "request_info", "message_info", "source"):
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
        except ClickHouseError as che:
            logging.error(f"ClickHouse error while fetching logs: {che}")
        except Exception as e:
            logging.error(f"Unexpected error while fetching logs: {e}")

        return {} if isinstance(log_id, str) else []


if __name__ == "__main__":
    from datetime import datetime
    import uuid

    service = ClickHouseServices()
    logs = service.fetch_logs()
    print(logs)

#     # ---------- Single log test ----------
#     log = Logs(
#         timestamp=datetime.now(),
#         event_type="test",
#         event_name="Test Event",
#         event_category="unit_test",
#         server_info=ServerInfo(hostname="localhost", portnumber=8000),
#         request_info=RequestInfo(
#             severity_level="INFO",
#             status_code=200,
#             session_id=str(uuid.uuid4()),
#             request_type="insert_log",
#             success_flag=True,
#         ),
#         message_info=MessageInfo(
#             message="This is a test log entry.",
#             description="This log entry is created for testing purposes.",
#         ),
#         source=SourceInfo(
#             diagnostics={"note": "No diagnostics available."},
#             source={"origin": "UnitTest"},
#         ),
#     )

#     redis_key = str(uuid.uuid4())
#     single_payload = {redis_key: log}

#     print("\n--- Inserting single log ---")
#     resp = service.insert_log(single_payload)
#     print("Insert response:", resp)

#     # ---------- Batch test ----------
#     batch_payload: list[dict[str, Any]] = []
#     for i in range(3):
#         batch_log = log_entry = Logs(
#         timestamp=datetime.now(),
#         event_name="Test Event",
#         message_info=MessageInfo(
#             message="Log testing",
#             description="This is a log testing description."
#         ),
#         source=SourceInfo(
#             diagnostics={"note": "No diagnostics available."},
#             source={"origin": "UnitTest"}
#         ),
# )
#         batch_payload.append({str(uuid.uuid4()): batch_log})

#     print("\n--- Inserting batch logs ---")
#     batch_resp = service.insert_log(batch_payload)
#     print("Batch insert response:", batch_resp)