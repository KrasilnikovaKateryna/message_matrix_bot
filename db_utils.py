import time
from datetime import datetime, timedelta

from models import Message

def execute_rec_into_task(record):
    print(record)
    if record.status == "active":
        status = True
    else:
        status = False
    task = {
        "id": record.id,
        "name": record.name,
        "room_id": record.room_id,
        "interval": record.interval,
        "start_time": record.start,
        "end_time": record.end,
        "message": record.message,
        "always_on": record.always_on,
        "active": status
    }
    return task


def execute_rec_into_schedule(record):
    print(record)
    if record.status == "active":
        status = True
    else:
        status = False
    task = {
        "id": record.id,
        "name": record.name,
        "group": record.room_id,
        "interval": record.interval,
        "start_time": record.start,
        "end_time": record.end,
        "message": record.message,
        "always_on": record.always_on,
        "active": status
    }
    return task
