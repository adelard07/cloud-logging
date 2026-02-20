from src.db.postgres.services import PostgresServices
from src.models.api_key import APIKeyAttibutes
from src.utils.utils import logging, encrypt, decrypt

class GenerateAPIKey:
    def __init__(self):
        self.db_pgs = PostgresServices()


    def generate_api_key(self, app_id, server_id) -> str:
        try:
            return encrypt(f"{app_id}:{server_id}")
        except Exception as e:
            logging.error(f"Error generating API key: {str(e)}")
            return None
        
    
    def validate_api_key(self, api_key: APIKeyAttibutes) -> bool:
        try:
            app_id, security_id = decrypt(api_key).split(":")
            app = self.db_pgs.get_app_by__app_id(app_id)

            if app and app[0]['json_agg'][0]['server_id'] == security_id:
                return True
        except Exception as e:
            logging.error(f"Error decrypting API key: {str(e)}")
            return False


if __name__ == "__main__":
    api_key_manager = GenerateAPIKey()
    new_api_key = api_key_manager.generate_api_key("556cb4f7-a16c-42e3-aced-99ffd09abc12", "server_id_example")
    print(f"Generated API Key: {new_api_key}")

    is_valid = api_key_manager.validate_api_key(new_api_key)
    print(f"Is the API Key valid? {is_valid}")