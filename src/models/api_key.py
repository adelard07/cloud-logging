from pydantic import BaseModel

class APIKeyAttibutes(BaseModel):
    app_id: str
    server_id: str
    