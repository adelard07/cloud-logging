from src.db.postgres.initialise import InitialiseDB
from src.utils.utils import logging


class PostgresServices:
    def __init__(self):
        self.dbi = InitialiseDB()
        
        
    # ====================== GET ======================


    def get_app_by_app_id(self, app_id: str) -> dict:
        try:
            query = """
                SELECT json_agg(a)
                FROM apps a
                WHERE app_id = %s
            """
            return self.dbi.execute_query(query, (app_id,), fetch='one')[0][0]
            
        except Exception as e:
            logging.error(f"Error getting app using app_id from PostgreSQL: {str(e)}")
            
    def get_servers_by_app_id(self, app_id: str) -> list[dict]:
        try:
            query = """
                SELECT json_agg(
                    json_build_object(
                        'server_id', s.server_id,
                        'server_name', s.server_name,
                        'server_type', s.server_type
                    )
                )
                FROM servers s
                WHERE app_id = %s
            """
            return self.dbi.execute_query(query, (app_id,), fetch='all')[0][0]
            
        except Exception as e:
            logging.error(f"Error getting servers using app_id from PostgreSQL: {str(e)}")
            return False
            
            
    def get_api_key(self, app_id: str, api_key: str):
        try:
            query = """
                SELECT app_id
                FROM api_keys
                WHERE app_id = %s AND api_key = %s
                LIMIT 1
            """
            row = self.dbi.execute_query(query, (app_id, api_key))
            if not row:
                return None
            
            return row
        except Exception as e:
            logging.error(f"Error getting servers using app_id from PostgreSQL: {str(e)}")
            return False

            
    # ====================== INSERT ======================
 

    def insert_app(self, app_name: str, app_description: str, server_id: str) -> bool:
        try:
            query = """
                INSERT INTO apps (app_name, app_description, server_id) 
                VALUES (%s, %s)
            """
            self.dbi.execute_query(query, (app_name, app_description, server_id))
            return True
        except Exception as e:
            logging.error(f"Error inserting log into PostgreSQL: {str(e)}")
            return False
        
    
    def insert_server(self, app_id: str, server_id: str) -> bool:
        try:
            query = """
                INSERT INTO servers (server_name, server_description)
                VALUES (%s, %s)
            """
            self.dbi.execute_query(query, (app_id, server_id))
            return True
        except Exception as e:
            logging.error(f"Error inserting log into PostgreSQL: {str(e)}")
            return False
        
        
    def insert_api_key(self, app_id, api_key):
        try:
            query = """
            
                INSERT INTO api_keys(app_id, api_key)
                VALUES (%s, %s)
            """
            self.dbi.execute_query(query=query, params=(app_id, api_key,))
            return True
        except Exception as e:
            logging.error(f"Error inserting api_key into PostgreSQL: {str(e)}")
            return False
        
        
    # ====================== UPDATE ======================

    
    
    # ====================== DELETE ======================
        
if __name__ == "__main__":
    pgs = PostgresServices()
    app = pgs.get_servers_by_app_id("b158dac7-eb5a-4823-81fa-a2c1143eceab")[0].get('server_id')
    print(app)