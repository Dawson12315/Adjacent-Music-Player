_PROGRESS = {
    "is_running": False,
    "is_stopping": False,
    "is_stopped": False,
    "current_batch": 0,
    "current_index": 0,
    "current_total": 0,
    "total_checked": 0,
    "total_processed": 0,
    "total_skipped": 0,
    "current_track_id": None,
    "current_title": None,
    "last_result": None,
}


def get_progress():
    return dict(_PROGRESS)


def reset_progress():
    global _PROGRESS
    _PROGRESS = {
        "is_running": False,
        "is_stopping": False,
        "is_stopped": False,
        "current_batch": 0,
        "current_index": 0,
        "current_total": 0,
        "total_checked": 0,
        "total_processed": 0,
        "total_skipped": 0,
        "current_track_id": None,
        "current_title": None,
        "last_result": None,
    }


def start_progress():
    reset_progress()
    _PROGRESS["is_running"] = True
    _PROGRESS["last_result"] = "started"


def mark_stopping():
    _PROGRESS["is_stopping"] = True
    _PROGRESS["last_result"] = "stop_requested"


def mark_stopped():
    _PROGRESS["is_running"] = False
    _PROGRESS["is_stopping"] = False
    _PROGRESS["is_stopped"] = True
    _PROGRESS["current_track_id"] = None
    _PROGRESS["current_title"] = None
    _PROGRESS["last_result"] = "stopped"


def update_progress(
    *,
    current_batch: int,
    current_index: int,
    current_total: int,
    total_checked: int,
    total_processed: int,
    total_skipped: int,
    current_track_id,
    current_title,
    last_result,
):
    _PROGRESS["current_batch"] = current_batch
    _PROGRESS["current_index"] = current_index
    _PROGRESS["current_total"] = current_total
    _PROGRESS["total_checked"] = total_checked
    _PROGRESS["total_processed"] = total_processed
    _PROGRESS["total_skipped"] = total_skipped
    _PROGRESS["current_track_id"] = current_track_id
    _PROGRESS["current_title"] = current_title
    _PROGRESS["last_result"] = last_result


def finish_progress():
    _PROGRESS["is_running"] = False
    _PROGRESS["is_stopping"] = False
    _PROGRESS["is_stopped"] = False
    _PROGRESS["current_track_id"] = None
    _PROGRESS["current_title"] = None
    if _PROGRESS["last_result"] in (None, "started", "stop_requested"):
        _PROGRESS["last_result"] = "finished"