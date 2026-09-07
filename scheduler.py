import os
import time
import datetime
import threading
from email_reporter import send_daily_attendance_email, get_email_config

_scheduler_thread = None
_stop_event = threading.Event()
_scheduler_lock = threading.Lock()
_sent_slots = set() # Stores tuples of (date_str, time_str)
_last_status = "Initialized, waiting for scheduled time."

def _scheduler_loop():
    global _last_status
    print("[Scheduler] Daily Attendance Email Scheduler started (Dual Slot: 09:05 AM & 08:00 PM).")
    
    while not _stop_event.is_set():
        try:
            config = get_email_config()
            target_times = config.get('schedule_times', ['09:05', '20:00']) # e.g. ["09:05", "20:00"]
            now = datetime.datetime.now()
            current_date_str = now.strftime('%Y-%m-%d')
            current_time_str = now.strftime('%H:%M')

            # Clean up old dates from _sent_slots to save memory
            if len(_sent_slots) > 50:
                recent_dates = {(now - datetime.timedelta(days=d)).strftime('%Y-%m-%d') for d in range(5)}
                to_remove = {s for s in _sent_slots if s[0] not in recent_dates}
                _sent_slots.difference_update(to_remove)

            # Check if current minute matches any target time
            for target_time in target_times:
                target_time = target_time.strip()
                if current_time_str == target_time:
                    slot_key = (current_date_str, target_time)
                    if slot_key not in _sent_slots:
                        is_evening = (target_time >= "16:00")
                        session_name = "Evening Summary (8:00 PM)" if is_evening else "Morning Check-In (9:05 AM)"
                        
                        print(f"[Scheduler] Triggering {session_name} at {target_time} on {current_date_str}...")
                        success, msg = send_daily_attendance_email(target_date=current_date_str, session_name=session_name)
                        _sent_slots.add(slot_key)
                        _last_status = f"Last triggered [{session_name}] on {current_date_str} at {now.strftime('%H:%M:%S')} - {'SUCCESS' if success else 'FAILED'}: {msg}"
                        print(f"[Scheduler] Result: {_last_status}")
                        
                        # Sleep past this minute
                        time.sleep(65)
                        break

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
        "scheduled_times": config.get('schedule_times', ['09:05', '20:00']),
        "scheduled_display": config.get('schedule_time_display', '09:05 AM & 08:00 PM'),
        "sender_email": config.get('sender', ''),
        "receiver_email": config.get('receiver', ''),
        "sent_slots": list(_sent_slots),
        "last_status": _last_status,
        "current_server_time": datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }
