from datetime import datetime
import time
import uuid

from src.models.logs import Logs
from src.utils.utils import logging
from src.db.clickhouse.services import ClickHouseServices
from src.db.redis.services import Services as RedisServices
from src.logging.batch_caching import BatchCaching


class LogIngestionService:
    def __init__(self, internal_batch_size: int = 1):
        self.internal_batch_size = internal_batch_size
        self.cache_batch = []

        self.batch_caching = BatchCaching(cache_batch=self.cache_batch)
        self.redis_services = RedisServices()
        self.click_house_services = ClickHouseServices()
        logging.info(f"LogIngestionService initialized | batch_size={self.internal_batch_size}")


    def ingest_log(self, log_object: Logs) -> Logs:
        # adding to mini batch in memory
        self.batch_caching.add_log_to_cache(log_object)
        current_batch_size = len(self.batch_caching.cache)
        logging.debug(f"Log added to local batch | current_batch_size={current_batch_size}")

        # push to redis after checking batch size if current batch reaches internal batch size
        if current_batch_size >= self.internal_batch_size:
            logging.info(f"Batch size reached {current_batch_size} | flushing_to_redis")
            self.flush_cache_to_redis()
        
        if not self.flush_cache_to_redis():
            logging.error("Failed to flush cache to Redis | log ingestion may be delayed")
                
        self.flush_redis_to_clickhouse()
        if not self.flush_redis_to_clickhouse():
            logging.error("Failed to flush Redis to ClickHouse | log ingestion may be delayed")

        return log_object


    def flush_cache_to_redis(self) -> bool:
        try:
            start = time.time()
            for log in self.batch_caching.cache:
                log_id = str(uuid.uuid4())
                try:
                    redis_resp = self.redis_services.insert_object(log_pair=(log_id, log))
                    logging.debug(f"Redis insert successful | log_id={log_id} | event={log.event_name} | resp={redis_resp}")
                except Exception as e:
                    logging.exception(f"Redis insert failed | log_id={log_id} | event={log.event_name} | error={e}")
                    return False

            self.batch_caching.flush_cache()
            duration = round(time.time() - start, 3)
            logging.info(f"Redis flush completed | duration={duration}s")
            return True
        except Exception as e:
            logging.exception(f"Failed to flush cache to Redis | error={e}")
            return False
    

    def flush_redis_to_clickhouse(self) -> bool:
        try:
            redis_log_cache = self.redis_services.get_object() or []
            redis_count = len(redis_log_cache)

            if redis_count == 0:
                logging.info("No logs found in Redis for ClickHouse flush")
                return True

            logging.info(f"Fetched logs from Redis | count={redis_count}")

            # pushing to clickhouse after checking redis cache length reached threshold 
            success_count = 0
            start = time.time()
            try:
                clickhouse_resp = self.click_house_services.insert_log(redis_log_cache)
                logging.debug(f"ClickHouse insert response: {clickhouse_resp}")
                success_count = len(clickhouse_resp) if clickhouse_resp else 0
            except Exception as e:
                logging.exception(f"ClickHouse insert failed | error={e}")
                return False
            duration = round(time.time() - start, 3)

            logging.info(f"ClickHouse flush completed | attempted={redis_count} | duration={duration}s")

            # deleting from redis after all logs were successfully inserted into clickhouse to prevent data loss
            if success_count == redis_count:
                try:
                    self.redis_services.delete_object()
                    logging.info(f"Redis cleared after successful ClickHouse flush | cleared_count={redis_count}")
                except Exception as e:
                    logging.exception(f"Failed to clear Redis after ClickHouse flush | error={e}")
                    return False
            else:
                logging.warning("Partial ClickHouse insert detected | Redis NOT cleared to prevent data loss")
                return False

            return True
        
        except Exception as e:
            logging.exception(f"Failed to flush Redis to ClickHouse | error={e}")
            return False


def main():
    service = LogIngestionService(internal_batch_size=1)

    for i in range(20):
        print("=" * 50)
        print(f"{i+1})")
        log_entry = Logs(
            timestamp=datetime.now(),
            event_name=f"Test Event {i}",
            message=f"This is a test log entry {i}.",
            description=f"This log entry {i} is created for testing purposes.",
            diagnostics="No diagnostics available.",
            source={"UnitTest": True},
        )
        time.sleep(1)
        service.ingest_log(log_entry)
        

if __name__ == "__main__":
    main()