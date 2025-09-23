from datetime import datetime, timedelta

def __date_string(format: str = '%Y-%m-%d %H:%M:%S'):
    return datetime.now().strftime(format)

def create_date_state():
    return f"{__date_string()}"