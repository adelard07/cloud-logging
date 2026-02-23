from typing import Optional, Tuple

from src.db.postgres.services import PostgresServices
from src.utils.utils import logging, Crypting

class GenerateAPIKey:
    def __init__(self):
        self.db_pgs = PostgresServices()
        self.crypting = Crypting()

    def generate_api_key(self, app_id: str) -> Optional[str]:
        try:
            server_id = self.db_pgs.get_servers_by_app_id(app_id)[0].get('server_id')
            logging.info(f"Generating api key for app id: {app_id} and server id: {server_id}")
            api_key = self.crypting.encrypt(f"{app_id}:{server_id}")
            insert_true = self.db_pgs.insert_api_key(app_id=app_id, api_key=api_key)

            return api_key
            
        except Exception as e:
            logging.error(f"Error generating API key: {str(e)}")
            return None


    def validate_api_key(self, api_key: str) -> Tuple[bool, Optional[str], Optional[str]]:
        try:
            if not api_key or not isinstance(api_key, str):
                return (False, None, None)

            decrypted = self.crypting.decrypt(api_key)
            if not decrypted or ":" not in decrypted:
                return (False, None, None)

            app_id, server_id = decrypted.split(":", 1)
            logging.info(f"Decrypted API Key - App ID: {app_id}, Server ID: {server_id}")

            app = self.db_pgs.get_app_by_app_id(app_id)
            if not app:
                return (False, None, None)

            key_row = self.db_pgs.get_api_key(app_id=app_id, api_key=api_key)
            if key_row:
                return (True, app_id, server_id)

            servers = self.db_pgs.get_servers_by_app_id(app_id) or []
            valid_server_ids = {s.get("server_id") for s in servers if s.get("server_id")}

            if server_id in valid_server_ids:
                return (True, app_id, server_id)

            return (False, None, None)

        except Exception as e:
            logging.error(f"Error decrypting API key: {str(e)}")
            return (False, None, None)

if __name__=="__main__":
    key_generation = GenerateAPIKey()
    api_key = key_generation.generate_api_key('b158dac7-eb5a-4823-81fa-a2c1143eceab')
    # api_key = 'W5gS3DwFVfXofI29kIG1H6cLRe9o3a/noTFh5GpJo961P8ge1y/9p43lxBHTN1xBCQ/DdTkNfhEoAJczNdxz2yDaxu2Jl8CyFnL9QJ+zxPEOa9xFx1iDmANjppzP8bHO+UlRk10='

    validation = key_generation.validate_api_key(api_key=api_key)
    print('='*100, '\n', api_key, '\n', '='*100, '\n', validation)
