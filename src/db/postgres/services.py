from src.db.postgres.initialise import InitialiseDB
from src.utils.utils import logging


class PostgresServices:
    def __init__(self):
        self.dbi = InitialiseDB()

    def get_app_by_app_id(self, app_id: str) -> dict:
        try:
            query = """
                SELECT json_agg(a)
                FROM apps a
                WHERE app_id = %s
            """
            return self.dbi.execute_query(query, (app_id,), fetch='one')[0][0]
            
        except Exception as e:
            print(f"Error inserting log into PostgreSQL: {str(e)}")
            
 
    def create_app(self, app_name: str, app_description: str, server_id: str) -> bool:
        try:
            query = """
                INSERT INTO apps (app_name, app_description, server_id) 
                VALUES (%s, %s)
            """
            self.dbi.execute_query(query, (app_name, app_description, server_id))
            return True
        except Exception as e:
            print(f"Error inserting log into PostgreSQL: {str(e)}")
            return False
        
    
    def create_server(self, app_id: str, server_id: str) -> bool:
        try:
            query = """
                INSERT INTO servers (server_name, server_description)
                VALUES (%s, %s)
            """
            self.dbi.execute_query(query, (app_id, server_id))
            return True
        except Exception as e:
            print(f"Error inserting log into PostgreSQL: {str(e)}")
            return False
        
        
if __name__ == "__main__":
    pgs = PostgresServices()
    app = pgs.get_app_by_app_id("722efa73-aaf8-4dea-abf8-7ec22aa14a40")
    print(app)