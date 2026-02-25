from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime
import uuid

    
class ServerInfo(BaseModel):
    hostname: Optional[str] = None
    portnumber: Optional[int] = None
    api_key: Optional[str] = None
    
    
class RequestInfo(BaseModel):
    severity_level: Optional[str] = None
    status_code: Optional[int] = None
    session_id: Optional[str] = None
    request_id: Optional[str] = uuid.uuid4()
    request_type: Optional[str] = None
    success_flag: Optional[bool] = None
    
    
class MessageInfo(BaseModel):
    message: Optional[str] = None
    description: Optional[str] = None
    

class Source(BaseModel):
    diagnostics: Optional[dict[str, Any]] = {}
    source: Optional[dict[str, Any]] = {}
    
        
class Logs(BaseModel):
    timestamp: Optional[datetime] = datetime.now()
    event_type: Optional[str] = None
    event_name: Optional[str] = None
    event_category: Optional[str] = None
    
    server_info: Optional[ServerInfo] = None
    request_info: Optional[RequestInfo] = None
    message_info: Optional[MessageInfo] = None
    source_info: Optional[Source] = None
    
    
if __name__ == "__main__":
    from datetime import datetime

    log_entry = Logs(
        timestamp=datetime.now(),
        event_name="Test Event",
        message_info=MessageInfo(
            message="This is a test log entry.",
            description="This log entry is created for testing purposes.",
        ),
        source=Source(
            diagnostics="No diagnostics available.",
            source={"origin": "UnitTest"}
        ),
    )

    print(log_entry.model_dump_json(indent=4))