from src.db.postgres.initialise import InitialiseDB
from src.utils.utils import logging


class PostgresServices:
    def __init__(self):
        self.dbi = InitialiseDB()

    def get_app_by__app_id(self, app_id: str) -> dict:
        try:
            query = """
                SELECT json_agg(a)
                FROM apps a
                WHERE app_id = %s
            """
            return self.dbi.execute_query(query, (app_id,), fetch='one')
            
        except Exception as e:
            print(f"Error inserting log into PostgreSQL: {str(e)}")
            
 
    def insert_app(self, app_name: str, app_description: str) -> bool:
        try:
            query = """
                INSERT INTO apps (app_name, app_description) 
                VALUES (%s, %s)
            """
            self.dbi.execute_query(query, (app_name, app_description))
            return True
        except Exception as e:
            print(f"Error inserting log into PostgreSQL: {str(e)}")
            return False
        
    