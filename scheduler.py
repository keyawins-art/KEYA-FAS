import os
import time
import datetime
import threading
from email_reporter import send_daily_attendance_email, get_email_config

_scheduler_thread = None
_stop_event = threading.Event()
_scheduler_lock = threading.Lock()
_last_sent_date = None
_last_status = "Initialized, waiting for scheduled time."

def _scheduler_loop():
    global _last_sent_date, _last_status
    print("[Scheduler] Daily Attendance Email Scheduler started.")
    
    while not _stop_event.is_set():
        try:
            config = get_email_config()
            target_time_str = config.get('schedule_time', '09:05').strip() # e.g. "09:05"
            now = datetime.datetime.now()
            current_date_str = now.strftime('%Y-%m-%d')
            current_time_str = now.strftime('%H:%M')

            # Check if current time matches target time and hasn't been sent today
            if current_time_str == target_time_str:
                if _last_sent_date != current_date_str:
                    print(f"[Scheduler] Target time {target_time_str} reached on {current_date_str}. Triggering email dispatch...")
                    success, msg = send_daily_attendance_email(target_date=current_date_str)
                    _last_sent_date = current_date_str
                    _last_status = f"Last triggered on {current_date_str} at {now.strftime('%H:%M:%S')} - {'SUCCESS' if success else 'FAILED'}: {msg}"
                    print(f"[Scheduler] Result: {_last_status}")
                    
                    # Sleep slightly longer to move past the current minute
                    time.sleep(65)
                    continue

        except Exception as e:
            _last_status = f"Scheduler error: {str(e)}"
            print(f"[Scheduler] Exception in loop: {e}")

        # Sleep interval (check every 20 seconds)
        time.sleep(20)

def start_scheduler():
    global _scheduler_thread
    with _scheduler_lock:
        if _scheduler_thread is None or not _scheduler_thread.is_alive():
            _stop_event.clear()
            _scheduler_thread = threading.Thread(target=_scheduler_loop, name="DailyAttendanceEmailScheduler", daemon=True)
            _scheduler_thread.start()
            print("[Scheduler] Background scheduler thread spawned successfully.")

def stop_scheduler():
    global _scheduler_thread
    _stop_event.set()
    if _scheduler_thread and _scheduler_thread.is_alive():
        _scheduler_thread.join(timeout=2)
        print("[Scheduler] Scheduler thread stopped.")

def get_scheduler_status():
    config = get_email_config()
    is_alive = _scheduler_thread is not None and _scheduler_thread.is_alive()
    return {
        "is_running": is_alive,
        "scheduled_time": config.get('schedule_time', '09:05'),
        "sender_email": config.get('sender', ''),
        "receiver_email": config.get('receiver', ''),
        "last_sent_date": _last_sent_date,
        "last_status": _last_status,
        "current_server_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
