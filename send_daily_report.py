#!/usr/bin/env python3
"""
Standalone Daily Attendance Email Sender Script
Usage:
    python send_daily_report.py
    python send_daily_report.py --session "Evening Summary"
    python send_daily_report.py --date 2026-09-07
    python send_daily_report.py --to recipient@example.com
    python send_daily_report.py --preview
"""

import sys
import argparse
import datetime
from email_reporter import send_daily_attendance_email, get_daily_attendance_data, get_email_config

def main():
    parser = argparse.ArgumentParser(description="Send Daily Attendance Report via Email")
    parser.add_argument('--date', type=str, default=None, help="Target date in YYYY-MM-DD format (default: today)")
    parser.add_argument('--to', type=str, default=None, help="Recipient email address (default: from .env)")
    parser.add_argument('--session', type=str, default=None, help="Session label e.g. 'Morning Check-In' or 'Evening Summary'")
    parser.add_argument('--preview', action='store_true', help="Preview summary stats without sending email")

    args = parser.parse_args()
    target_date = args.date or datetime.date.today().strftime('%Y-%m-%d')
    config = get_email_config()

    print("=" * 60)
    print(" Keya Fusion Attendance System - Daily Report Dispatch")
    print("=" * 60)
    print(f"Target Date     : {target_date}")
    print(f"Sender Email    : {config['sender']}")
    print(f"Recipient Email : {args.to or config['receiver']}")
    print(f"Schedule Slots  : {config['schedule_time_display']}")
    if args.session:
        print(f"Session Name    : {args.session}")
    print("-" * 60)

    try:
        summary, records = get_daily_attendance_data(target_date)
        print(f"Total Staff     : {summary['total_employees']}")
        print(f"Present Today   : {summary['present_count']}")
        print(f"Absent Today    : {summary['absent_count']}")
        print(f"Leaves/Holiday  : {summary['leave_count']}")
        print(f"Attendance Rate : {summary['attendance_rate']}%")
        print("-" * 60)

        if args.preview:
            print("Preview mode active - no email was sent.")
            return

        print("Sending email with report and Excel attachment...")
        success, message = send_daily_attendance_email(target_date=target_date, to_email=args.to, session_name=args.session)
        
        if success:
            print(f"[SUCCESS] {message}")
            sys.exit(0)
        else:
            print(f"[FAILED] {message}")
            sys.exit(1)

    except Exception as e:
        print(f"[FATAL ERROR] {e}")
        sys.exit(1)

if __name__ == '__main__':
    main()
