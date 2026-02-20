import redis

from src.models.logs import Logs
from src.db.clickhouse.services import ClickHouseServices

class BatchCaching:
    def __init__(self, cache_batch: list[Logs] = []):
        self.cache: list[Logs] = cache_batch

    def add_log_to_cache(self, log_entry: Logs):
        self.cache.append(log_entry)
        
    def flush_cache(self):
        self.cache.clear()
        
        
if __name__ == "__main__":
    batch_caching = BatchCaching()
    log1 = Logs(service_name="service1", log_level="INFO", message="This is a log message 1")
    log2 = Logs(service_name="service2", log_level="ERROR", message="This is a log message 2")
    log3 = Logs(service_name="service3", log_level="DEBUG", message="This is a log message 3")

    batch_caching.add_log_to_cache(log1)
    batch_caching.add_log_to_cache(log2)  # This will trigger a flush
    batch_caching.add_log_to_cache(log3)  # This will be added to cache but not flushed yet
    print(f"Current cache size: {len(batch_caching.cache)}")  # Should be 1 after flush
    print(f"Cache contents: {batch_caching.cache}")
    print(f"Flushing cache...")
    batch_caching.flush_cache()
    print(f"Current cache size after flush: {len(batch_caching.cache)}")