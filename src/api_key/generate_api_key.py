from src.db.postgres.services import PostgresServices
from src.models.api_key import APIKeyAttibutes
from src.utils.utils import logging, Crypting

class GenerateAPIKey:
    def __init__(self):
        self.db_pgs = PostgresServices()
        self.crypting = Crypting()

    def generate_api_key(self, app_id, server_id) -> str:
        try:
            return self.crypting.encrypt(f"{app_id}:{server_id}")
        except Exception as e:
            logging.error(f"Error generating API key: {str(e)}")
            return None
        
    
    def validate_api_key(self, api_key: APIKeyAttibutes) -> bool:
        try:
            app_id, security_id = self.crypting.decrypt(api_key).split(":")
            logging.info(f"Decrypted API Key - App ID: {app_id}, Server ID: {security_id}")
            app = self.db_pgs.get_app_by_app_id(app_id)

            if app.get('app_id') == app_id and app.get('server_id') == security_id:
                return True
        except Exception as e:
            logging.error(f"Error decrypting API key: {str(e)}")
            return False


if __name__ == "__main__":
    api_key_manager = GenerateAPIKey()
    new_api_key = api_key_manager.generate_api_key("722efa73-aaf8-4dea-abf8-7ec22aa14a40", "b7b7e892-487b-43fb-861e-e8aa7192f190")
    print(f"Generated API Key: {new_api_key}")

    is_valid = api_key_manager.validate_api_key(new_api_key)
    print(f"Is the API Key valid? {is_valid}")