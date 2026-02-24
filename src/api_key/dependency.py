from typing import Dict, Optional

from fastapi import Header, HTTPException

from src.api_key.authenticate import GenerateAPIKey


def require_api_key(x_api_key: Optional[str] = Header(default=None, alias="X-API-Key")) -> Dict[str, str]:
    
    if not x_api_key:
        raise HTTPException(status_code=401, detail="Missing API key (X-API-Key)")

    _api_key_manager = GenerateAPIKey()
    
    is_valid, app_id, server_id = _api_key_manager.validate_api_key(x_api_key)
    if not is_valid or not app_id or not server_id:
        raise HTTPException(status_code=403, detail="Invalid API key")

    return {"app_id": app_id, "server_id": server_id}