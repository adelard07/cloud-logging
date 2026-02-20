from typing import Any
import os
import json

from src.db.redis.initialise import Initialise
from src.models.logs import Logs
from src.utils.utils import logging, to_sql_literal

class Services:
    def __init__(self):
        self.redis_obj = Initialise()
            

    def insert_object(self, log_pair: tuple[str, Any | Logs]):
        try:
            log_key, log_dict = log_pair

            payload = json.dumps(log_dict.model_dump(), default=str)

            result = self.redis_obj.redis_client.set(str(log_key), payload)

            return result

        except Exception as e:
            logging.exception(f"Error inserting object into Redis: {e}")
            return None

        
    def get_object(self, key: str = None):
        try:
            def decode_value(raw):
                if raw is None:
                    return None

                # Redis returns bytes
                if isinstance(raw, bytes):
                    raw = raw.decode()

                # Try JSON decode first
                try:
                    return json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    return raw

            if key is not None:
                raw_value = self.redis_obj.redis_client.get(key)
                return [{key: decode_value(raw_value)}] if raw_value else []

            # Fetch all keys
            keys = self.redis_obj.redis_client.keys('*')
            response = []

            for raw_key in keys:
                decoded_key = raw_key.decode() if isinstance(raw_key, bytes) else raw_key
                raw_value = self.redis_obj.redis_client.get(decoded_key)
                response.append({decoded_key: decode_value(raw_value)})

            return response

        except Exception as e:
            logging.exception(f"Error retrieving object from Redis: {e}")
            return None


    def delete_object(self, key: str = None):
        try:
            if key is None:
                keys = self.redis_obj.redis_client.keys('*')
                if keys:
                    return self.redis_obj.redis_client.delete(*keys)
                
            return self.redis_obj.redis_client.delete(key)
            
        except Exception as e:
            print(f"Error deleting object from Redis: {str(e)}")
            return None
        
        
if __name__ == "__main__":
    from datetime import datetime
    import uuid
    import json

    services = Services()

    # Create test log
    # log = Logs(
    #     timestamp=datetime.now(),
    #     event_name="redis_test_event",
    #     message="Testing redis insert",
    #     description="Simple redis write/read test",
    #     diagnostics="none",
    #     source={"test": True},
    # )

    # test_key = str(uuid.uuid4())

    # print(f"\nInserting log with key: {test_key}")

    # # Insert
    # insert_resp = services.insert_object((test_key, log))
    # print(f"Insert response: {insert_resp}")

    # Fetch
    raw_value = services.get_object()
    print(f"\nValues from Redis:\n{raw_value}")
    print(f"\nCache lenth from Redis:\n{len(raw_value)}")

    # if raw_value:
    #     decoded = json.loads(raw_value)
    #     print("\nDecoded JSON:")
    #     print(decoded)

    # # # Delete
    # # delete_resp = services.delete_object(test_key)
    # # print(f"\nDelete response: {delete_resp}")

    # # Verify deletion
    # verify = services.get_object(test_key)
    # print(f"\nPost-delete fetch (should be None): {verify}")
