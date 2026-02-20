import redis
import dotenv 
import os

dotenv.load_dotenv()

class Initialise:
    def __init__(self):
        try:
            self.redis_client = redis.Redis(
                host=os.getenv("REDIS_HOST"),
                port=os.getenv("REDIS_PORT"),
                decode_responses=os.getenv("REDIS_DECODE_RESPONSE"),
                username=os.getenv("REDIS_USERNAME"),
                password=os.getenv("REDIS_PASSWORD"),
            )
            
            if not self.redis_client.ping():
                raise ConnectionError("Failed to connect to Redis server.")
                
        except ConnectionError as ce:
            print(f"Redis connection failed: {ce}")
            raise    
        
if __name__ == "__main__":
    initialise = Initialise()
    print(initialise.redis_client.ping())