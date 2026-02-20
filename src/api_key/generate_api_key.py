from pydantic import BaseModel


class APIKeyAttibutes(BaseModel):
    user_id: str
    permissions: list[str]
    server_id: str
    


class GenerateAPIKey:
    def __init__(self):
        pass

    def generate_key(self) -> str:
        # Implement your API key generation logic here
        # For example, you can use UUID or any other method to create a unique key
        import uuid
        return str(uuid.uuid4())