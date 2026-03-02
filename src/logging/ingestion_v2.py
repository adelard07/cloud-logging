from datetime import datetime
import os
import time
import uuid

from src.models.logs import Logs, ServerInfo, RequestInfo, MessageInfo, SourceInfo
from src.utils.utils import logging
from src.db.redshift.services import RedshiftServices
from src.db.redis.services import RedisServices
from src.logging.batch_caching import BatchCaching


class LogIngestionService:
    def __init__(self, internal_batch_size: int = 1, redis_flush_count: int = 10):
        self.internal_batch_size = internal_batch_size
        self.redis_flush_count = redis_flush_count
        self.cache_batch = []

        self.batch_caching = BatchCaching(cache_batch=self.cache_batch)
        self.redis_services = RedisServices()
        self.redshift_services = RedshiftServices()
        logging.info(f"LogIngestionService initialized | batch_size={self.internal_batch_size}")

    def ingest_log(self, log_object: Logs) -> Logs:
        try:
            self.batch_caching.add_log_to_cache(log_object)
            current_batch_size = len(self.batch_caching.cache)
            logging.debug(f"Log added to local batch | current_batch_size={current_batch_size}")

            flushed_cache = True
            if current_batch_size >= self.internal_batch_size:
                logging.info(f"Batch size reached {current_batch_size} | flushing_to_redis")
                flushed_cache = self.flush_cache_to_redis()

            if not flushed_cache:
                logging.error("Failed to flush cache to Redis | log ingestion may be delayed")
                return log_object

            redis_log_cache = self.redis_services.get_object() or []
            redis_count = len(redis_log_cache)
            logging.info(f"Fetched logs from Redis | count={redis_count}")

            if redis_count == 0:
                logging.info("No logs found in Redis for Redshift flush")
                return log_object

            if redis_count < self.redis_flush_count:
                logging.info(
                    f"Redis log count {redis_count} has not reached flush threshold {self.redis_flush_count} | "
                    "deferring Redshift flush"
                )
                return log_object

            flushed_redis = self.flush_redis_to_redshift()
            if not flushed_redis:
                logging.error("Failed to flush Redis to Redshift | log ingestion may be delayed")

            return log_object

        except Exception as e:
            logging.exception(f"Error ingesting log | error={e}")
            raise

    def flush_cache_to_redis(self) -> bool:
        try:
            start = time.time()

            for log in self.batch_caching.cache:
                log_id = str(uuid.uuid4())
                try:
                    redis_resp = self.redis_services.insert_object(log_pair=(log_id, log))
                    logging.debug(f"Redis insert successful | log_id={log_id} | event={log.event_name} | resp={redis_resp}")
                except Exception as e:
                    logging.exception(f"Redis insert failed | log_id={log_id} | event={getattr(log, 'event_name', None)} | error={e}")
                    return False

            self.batch_caching.flush_cache()
            duration = round(time.time() - start, 3)
            logging.info(f"Redis flush completed | duration={duration}s")
            return True

        except Exception as e:
            logging.exception(f"Failed to flush cache to Redis | error={e}")
            return False

    def flush_redis_to_redshift(self) -> bool:
        try:
            redis_log_cache = self.redis_services.get_object() or []
            redis_count = len(redis_log_cache)

            if redis_count == 0:
                logging.info("Redis empty | skipping Redshift flush")
                return True

            start = time.time()

            try:
                inserted = self.redshift_services.insert_log(redis_log_cache)
                success_count = inserted or 0
            except Exception as e:
                logging.exception(f"Redshift insert failed | error={e}")
                return False

            duration = round(time.time() - start, 3)
            logging.info(f"Redshift flush completed | attempted={redis_count} | inserted={success_count} | duration={duration}s")

            if success_count == redis_count:
                try:
                    self.redis_services.delete_object()
                    logging.info(f"Redis cleared after successful Redshift flush | cleared_count={redis_count}")
                except Exception as e:
                    logging.exception(f"Failed to clear Redis after Redshift flush | error={e}")
                    return False
                return True

            logging.warning("Partial Redshift insert detected | Redis NOT cleared to prevent data loss")
            return False

        except Exception as e:
            logging.exception(f"Failed to flush Redis to Redshift | error={e}")
            return False


def main():
    service = LogIngestionService(internal_batch_size=1, redis_flush_count=5)

    for i in range(7):
        print("=" * 50)
        print(f"{i + 1})")

        log_entry = Logs(
            timestamp=datetime.now(),
            event_type="ingestion_test",
            event_name=f"Test Event {i}",
            event_category="unit_test",
            server_info=ServerInfo(
                hostname=os.getenv("HOSTNAME", "local"),
                portnumber=int(os.getenv("PORTNUMBER", "0")) or None,
            ),
            request_info=RequestInfo(
                severity_level="INFO",
                status_code=200,
                session_id=str(uuid.uuid4()),
                request_type="local_ingestion_test",
                success_flag=True,
            ),
            message_info=MessageInfo(
                message=f"This is a test log entry {i}.",
                description=f"This log entry {i} is created for testing purposes.",
            ),
            source_info=SourceInfo(
                diagnostics={"note": "No diagnostics available."},
                source={"UnitTest": True, "index": i},
            ),
        )

        time.sleep(1)
        service.ingest_log(log_entry)


if __name__ == "__main__":
    main()