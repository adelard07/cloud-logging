from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class Logs(BaseModel):
    timestamp: Optional[datetime] = None
    event_type: Optional[str] = None
    event_name: Optional[str] = None
    event_category: Optional[str] = None
    
    hostname: Optional[str] = None
    portnumber: Optional[int] = None
    api_key: Optional[str] = None
    
    severity_level: Optional[str] = None
    status_code: Optional[int] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = None
    success_flag: Optional[bool] = None

    message: Optional[str] = None
    description: Optional[str] = None
    diagnostics: Optional[str] = None
    source: Optional[dict[str, Any]] = None
    
    
if __name__ == "__main__":
    log_entry = Logs(
        timestamp=datetime.now(),
        event_name="Test Event",
        message="This is a test log entry.",
        description="This log entry is created for testing purposes.",
        diagnostics="No diagnostics available.",
        source="UnitTest"
    )
    print(log_entry.model_dump_json(indent=4))