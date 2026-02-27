from __future__ import annotations
from pydantic import BaseModel, Field
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
    request_id: uuid.UUID = Field(default_factory=uuid.uuid4)
    request_type: Optional[str] = None
    success_flag: Optional[bool] = None


class MessageInfo(BaseModel):
    message: Optional[str] = None
    description: Optional[str] = None


class SourceInfo(BaseModel):
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    source: dict[str, Any] = Field(default_factory=dict)


class Logs(BaseModel):
    timestamp: datetime = Field(default_factory=datetime.now)
    event_type: Optional[str] = None
    event_name: Optional[str] = None
    event_category: Optional[str] = None
    version: Optional[str] = None

    server_info: Optional[ServerInfo] = None
    request_info: Optional[RequestInfo] = None
    message_info: Optional[MessageInfo] = None
    source_info: Optional[SourceInfo] = None
    
    extra: Optional[dict] = None
    
    
if __name__ == "__main__":
    from datetime import datetime

    log_entry = Logs(
        timestamp=datetime.now(),
        event_name="Test Event",
        message_info=MessageInfo(
            message="This is a test log entry.",
            description="This log entry is created for testing purposes.",
        ),
        source=SourceInfo(
            diagnostics="No diagnostics available.",
            source={"origin": "UnitTest"}
        ),
    )

    print(log_entry.model_dump_json(indent=4))