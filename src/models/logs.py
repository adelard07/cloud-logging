from pydantic import BaseModel
from typing import Optional, Any
from datetime import datetime

class Logs(BaseModel):
    timestamp: Optional[datetime] = None
    event_name: Optional[str] = None
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