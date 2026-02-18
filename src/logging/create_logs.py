from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Any

from src.models.logs import Logs
from src.utils.utils import logging
from src.db.services import Services

class CreateLogs:
    def __init__(self,):
        self.services = Services()
    
    def get_ist_time(self):
        return datetime.now(tz=ZoneInfo('Asia/Kolkata'))
        
    def create_log_entry(self, timestamp: datetime = None, event_name: str = None, message: str = None, 
                         description: str = None, diagnostics: dict[str, Any] = None, source: str = None) -> Logs:
        log_entry = Logs(timestamp = timestamp if timestamp is not None else self.get_ist_time(),
                         event_name=event_name, message=message,
            description=description,
            diagnostics=diagnostics,
            source=source
        )
        result = self.services.insert_log_entry(log_entry)
        logging.info(f"Log entry created: {log_entry}. \n{result}")
        
        return log_entry
    
    
        
        
if __name__ == "__main__":
    log_creator = CreateLogs()
    log_entry = log_creator.create_log_entry(
        timestamp=datetime.now(),
        event_name="Test Event",
        message="This is a test log entry.",
        description="This log entry is created for testing purposes.",
        diagnostics="No diagnostics available.",
        source="UnitTest"
    )