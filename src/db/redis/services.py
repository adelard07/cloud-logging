from typing import Any
import json

from src.db.redis.initialise import Initialise
from src.models.logs import Logs
from src.utils.utils import logging


class Services:
    def __init__(self):
        self.redis_obj = Initialise()

    @staticmethod
    def _jsonable(value: Any) -> Any:
        """
        Convert nested model/dict-ish data into something JSON serializable.
        """
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
    def _normalize_payload_dict(cls, payload_dict: dict[str, Any]) -> dict[str, Any]:
        """
        Align payload with your latest Logs schema:
        - If nested objects exist, ensure they are stored as proper JSON objects (not random types).
        - Convert nested Pydantic models into dicts.
        """
        normalized: dict[str, Any] = {}

        for k, v in payload_dict.items():
            if v is None:
                continue

            if k in {"server_info", "request_info", "message_info", "source"}:
                normalized[k] = cls._jsonable(v)
            else:
                normalized[k] = v

        return normalized

    def insert_object(self, log_pair: tuple[str, Any | Logs]):
        try:
            log_key, log_payload = log_pair

            # bytes -> str
            if isinstance(log_payload, (bytes, bytearray)):
                log_payload = log_payload.decode()

            # str -> try json else treat as message text
            if isinstance(log_payload, str):
                try:
                    log_payload = json.loads(log_payload)
                except json.JSONDecodeError:
                    log_payload = {"message_info": {"message": log_payload}}

            if isinstance(log_payload, Logs):
                payload_dict = log_payload.model_dump(exclude_none=True)

            elif isinstance(log_payload, dict):
                payload_dict = {k: v for k, v in log_payload.items() if v is not None}
                payload_dict = self._normalize_payload_dict(payload_dict)

                # If someone still sends legacy flat keys, map them
                # (keeps backward compatibility with old callers)
                if "message" in payload_dict or "description" in payload_dict:
                    mi = payload_dict.get("message_info") or {}
                    if "message" in payload_dict and "message" not in mi:
                        mi["message"] = payload_dict.pop("message")
                    if "description" in payload_dict and "description" not in mi:
                        mi["description"] = payload_dict.pop("description")
                    payload_dict["message_info"] = mi

                if "diagnostics" in payload_dict or "source" in payload_dict:
                    # If "source" is already nested in your new model, leave it.
                    # If "diagnostics" is flat legacy, move into source.diagnostics
                    if isinstance(payload_dict.get("source"), dict):
                        src_obj = payload_dict["source"]
                        if "diagnostics" in payload_dict:
                            diag = payload_dict.pop("diagnostics")
                            if "diagnostics" not in src_obj:
                                src_obj["diagnostics"] = diag
                            payload_dict["source"] = src_obj
                    else:
                        # source isn't a dict; create one
                        diag = payload_dict.pop("diagnostics", None)
                        src = payload_dict.pop("source", None)
                        payload_dict["source"] = {
                            "diagnostics": diag if diag is not None else {},
                            "source": src if isinstance(src, dict) else ({} if src is None else {"value": src}),
                        }

            else:
                payload_dict = {"message_info": {"message": str(log_payload)}}

            payload_dict = self._normalize_payload_dict(payload_dict)

            payload = json.dumps(payload_dict, ensure_ascii=False, default=str)
            return self.redis_obj.redis_client.set(str(log_key), payload)

        except Exception as e:
            logging.exception(f"Error inserting object into Redis: {e}")
            return None

    def get_object(self, key: str | None = None):
        try:
            def decode_value(raw: Any):
                if raw is None:
                    return None

                if isinstance(raw, bytes):
                    raw = raw.decode()

                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return raw

            if key is not None:
                raw_value = self.redis_obj.redis_client.get(key)
                return [{key: decode_value(raw_value)}] if raw_value else []

            keys = self.redis_obj.redis_client.keys("*")
            response: list[dict[str, Any]] = []

            for raw_key in keys:
                decoded_key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
                raw_value = self.redis_obj.redis_client.get(decoded_key)
                response.append({decoded_key: decode_value(raw_value)})

            return response

        except Exception as e:
            logging.exception(f"Error retrieving object from Redis: {e}")
            return None

    def delete_object(self, key: str | None = None):
        try:
            if key is None:
                keys = self.redis_obj.redis_client.keys("*")
                if keys:
                    return self.redis_obj.redis_client.delete(*keys)
                return 0

            return self.redis_obj.redis_client.delete(key)

        except Exception as e:
            logging.exception(f"Error deleting object from Redis: {str(e)}")
            return None


if __name__ == "__main__":
    import uuid
    from datetime import datetime
    from src.models.logs import ServerInfo, RequestInfo, MessageInfo, Source

    services = Services()

    # Create test log aligned to the new schema
    log = Logs(
        timestamp=datetime.now(),
        event_type="redis_test",
        event_name="redis_test_event",
        event_category="unit_test",
        server_info=ServerInfo(hostname="localhost", portnumber=6379),
        request_info=RequestInfo(
            severity_level="INFO",
            status_code=200,
            session_id=str(uuid.uuid4()),
            request_type="redis_set",
            success_flag=True,
        ),
        message_info=MessageInfo(
            message="Testing redis insert",
            description="Simple redis write/read test",
        ),
        source=Source(
            diagnostics={"mode": "test"},
            source={"test": True},
        ),
    )

    test_key = str(uuid.uuid4())

    print(f"\nInserting log with key: {test_key}")
    insert_resp = services.insert_object((test_key, log))
    print(f"Insert response: {insert_resp}")

    raw_value = services.get_object(test_key)
    print(f"\nFetched from Redis:\n{raw_value}")

    delete_resp = services.delete_object(test_key)
    print(f"\nDelete response: {delete_resp}")

    verify = services.get_object(test_key)
    print(f"\nPost-delete fetch (should be []): {verify}")