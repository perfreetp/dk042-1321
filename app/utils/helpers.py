import uuid
from datetime import datetime


def generate_report_no() -> str:
    return f"RCP-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"


def generate_task_no() -> str:
    return f"PUB-{datetime.utcnow().strftime('%Y%m%d%H%M%S')}-{uuid.uuid4().hex[:8]}"
