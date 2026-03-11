import redis
import dotenv 
import os

dotenv.load_dotenv()

class Initialise:
    def __init__(self):
        try:
            self.pool = redis.ConnectionPool(
                host=os.getenv("REDIS_HOST"),
                port=os.getenv("REDIS_PORT"),
                password=os.getenv("REDIS_PASSWORD"),
            )
            self.redis_client = redis.Redis(
                connection_pool=self.pool,
                decode_responses=os.getenv("REDIS_DECODE_RESPONSE"),
                username=os.getenv("REDIS_USERNAME"),
                socket_connect_timeout=5,
                socket_timeout=5,
                max_connections=10
            )
            
            if not self.redis_client.ping():
                raise ConnectionError("Failed to connect to Redis server.")
                
        except ConnectionError as ce:
            print(f"Redis connection failed: {ce}")
            raise    
        
if __name__ == "__main__":
    initialise = Initialise()
    print(initialise.redis_client.ping())