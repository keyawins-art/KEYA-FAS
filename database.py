import sqlite3
import psycopg2
from psycopg2.extras import RealDictCursor
import os
import datetime
from dotenv import load_dotenv

load_dotenv()

DB_URL = os.getenv('DATABASE_URL')
SQLITE_PATH = os.path.join(os.path.dirname(__file__), 'data', 'attendance.db')

db_pool = None
if DB_URL:
    from psycopg2 import pool
    # Connection pool to drastically reduce connection time to remote database
    db_pool = pool.ThreadedConnectionPool(1, 10, DB_URL)

def get_db_connection():
    if DB_URL:
        # PostgreSQL (Supabase) using Pool
        conn = db_pool.getconn()
        return conn
    else:
        # Local SQLite
        conn = sqlite3.connect(SQLITE_PATH)
        conn.row_factory = sqlite3.Row
        return conn

def release_db_connection(conn):
    if DB_URL:
        db_pool.putconn(conn)
    else:
        conn.close()

def get_cursor(conn):
    if DB_URL:
        return conn.cursor(cursor_factory=RealDictCursor)
    return conn.cursor()

def get_placeholder():
    return "%s" if DB_URL else "?"

def init_db():
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()

    # Create Employees table
    if DB_URL:
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT,
                phone TEXT,
                email TEXT,
                face_encoding BYTEA NOT NULL
            )
        ''')
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS attendance (
                id SERIAL PRIMARY KEY,
                employee_id TEXT NOT NULL,
                date TEXT NOT NULL,
                login_time TEXT,
                logout_time TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_emp_date ON attendance(employee_id, date)')
    else:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS employees (
                employee_id TEXT PRIMARY KEY,
                name TEXT NOT NULL,
                department TEXT,
                phone TEXT,
                email TEXT,
                face_encoding BLOB NOT NULL
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS attendance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                employee_id TEXT NOT NULL,
                date TEXT NOT NULL,
                login_time TEXT,
                logout_time TEXT,
                FOREIGN KEY (employee_id) REFERENCES employees (employee_id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_date ON attendance(date)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_attendance_emp_date ON attendance(employee_id, date)')

    conn.commit()
    release_db_connection(conn)

# Helper functions
def add_employee(employee_id, name, department, phone, email, face_encoding_bytes):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    try:
        blob = psycopg2.Binary(face_encoding_bytes) if DB_URL else face_encoding_bytes
        cursor.execute(f'''
            INSERT INTO employees (employee_id, name, department, phone, email, face_encoding)
            VALUES ({p}, {p}, {p}, {p}, {p}, {p})
        ''', (employee_id, name, department, phone, email, blob))
        conn.commit()
        return True
    except (sqlite3.IntegrityError, psycopg2.IntegrityError):
        return False
    except Exception as e:
        print(f"Error adding employee: {e}")
        return False
    finally:
        release_db_connection(conn)

def get_all_employees():
    conn = get_db_connection()
    cursor = get_cursor(conn)
    cursor.execute('SELECT * FROM employees')
    employees = cursor.fetchall()
    release_db_connection(conn)
    return employees

def get_all_employees_no_blob():
    conn = get_db_connection()
    cursor = get_cursor(conn)
    # Exclude face_encoding (BLOB) for faster GUI loads
    cursor.execute('SELECT employee_id, name, department, phone, email FROM employees')
    employees = cursor.fetchall()
    release_db_connection(conn)
    return employees

def update_employee(old_eid, new_eid, name, department, phone, email):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    try:
        # If ID changed, we must update attendance records with FK considerations
        if old_eid != new_eid:
            # 1. Get the face encoding from the old record
            cursor.execute(f"SELECT face_encoding FROM employees WHERE employee_id = {p}", (old_eid,))
            old_emp = cursor.fetchone()
            if not old_emp:
                return False
            
            face_encoding = old_emp['face_encoding'] if isinstance(old_emp, dict) else old_emp[0]
            
            # 2. Insert new employee record with new ID
            cursor.execute(f'''
                INSERT INTO employees (employee_id, name, department, phone, email, face_encoding)
                VALUES ({p}, {p}, {p}, {p}, {p}, {p})
            ''', (new_eid, name, department, phone, email, face_encoding))
            
            # 3. Update all attendance records to the new ID
            cursor.execute(f"UPDATE attendance SET employee_id = {p} WHERE employee_id = {p}", (new_eid, old_eid))
            
            # 4. Delete the old employee record
            cursor.execute(f"DELETE FROM employees WHERE employee_id = {p}", (old_eid,))
        else:
            # Standard update (ID hasn't changed)
            cursor.execute(f'''
                UPDATE employees 
                SET name = {p}, department = {p}, phone = {p}, email = {p}
                WHERE employee_id = {p}
            ''', (name, department, phone, email, old_eid))
        
        conn.commit()
        return True
    except Exception as e:
        if conn: conn.rollback()
        print(f"Error updating employee: {e}")
        return False
    finally:
        release_db_connection(conn)

def delete_employee(employee_id):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    # Delete child records first to respect Foreign Key constraints
    cursor.execute(f'DELETE FROM attendance WHERE employee_id = {p}', (employee_id,))
    cursor.execute(f'DELETE FROM employees WHERE employee_id = {p}', (employee_id,))
    conn.commit()
    release_db_connection(conn)

def mark_attendance(employee_id):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    today = datetime.date.today().strftime('%Y-%m-%d')
    now_time = datetime.datetime.now().strftime('%H:%M:%S')

    cursor.execute(f'''
        SELECT id, login_time, logout_time FROM attendance 
        WHERE employee_id = {p} AND date = {p}
    ''', (employee_id, today))
    
    record = cursor.fetchone()

    if not record:
        # First scan of the day -> Check-In
        now_time_parsed = datetime.datetime.strptime(now_time, '%H:%M:%S').time()
        nine_am = datetime.time(9, 0, 0)
        if now_time_parsed > nine_am:
            release_db_connection(conn)
            return "LATE", "Login Not Accepted (After 9:00 AM)"

        cursor.execute(f'''
            INSERT INTO attendance (employee_id, date, login_time, logout_time)
            VALUES ({p}, {p}, {p}, {p})
        ''', (employee_id, today, now_time, ""))
        conn.commit()
        release_db_connection(conn)
        return "IN", f"Check-In: {now_time}"
    else:
        # Extract values (handle both dict and tuple)
        try:
            rid = record['id']
            login_val = record['login_time']
            logout_val = record['logout_time']
        except (TypeError, IndexError):
            rid, login_val, logout_val = record[0], record[1], record[2]

        # Safety: If manual override is active, don't update
        if login_val == 'Absent' or logout_val == 'Absent' or login_val == 'Sick Leave' or login_val == 'Paid Leave':
            release_db_connection(conn)
            return "OVERRIDE", "Manual Leave Active"

        # ADD RESTRICTION: Prevent logout between 17:15 and 17:30
        now_time_parsed = datetime.datetime.strptime(now_time, '%H:%M:%S').time()
        start_restrict = datetime.time(17, 15, 0)
        end_restrict = datetime.time(17, 30, 0)
        
        if start_restrict <= now_time_parsed <= end_restrict:
            release_db_connection(conn)
            return "RESTRICTED", "Log out not allowed between 5:15 PM and 5:30 PM"

        # We no longer block if already logged out; we update the checkout time
        # so that the latest scan becomes the final check-out time.
        
        # SAFETY WINDOW: Prevent accidental Check-Out if it's within 30 mins of Check-In
        try:
            from datetime import datetime as dt
            # Handle potential different time formats like with or without AM/PM
            try:
                t1 = dt.strptime(login_val, '%H:%M:%S')
            except ValueError:
                # If it fails, try parsing with AM/PM (in case of manual entry)
                t1 = dt.strptime(login_val, '%I:%M %p')
                
            t2 = dt.strptime(now_time, '%H:%M:%S')
            diff_sec = (t2 - t1).total_seconds()
            
            # If less than 30 minutes (1800 seconds)
            if 0 <= diff_sec < 1800:
                release_db_connection(conn)
                return "ALREADY_IN", f"Already Checked-In! (Wait 30m to Out)"
        except Exception as e:
            print(f"Time comparison error: {e}")

        cursor.execute(f"UPDATE attendance SET logout_time = {p} WHERE id = {p}", (now_time, rid))
        conn.commit()
        release_db_connection(conn)
        
        if logout_val and logout_val != "":
            return "OUT", f"Check-Out Updated: {now_time}"
            
        return "OUT", f"Check-Out: {now_time}"

def get_attendance_logs(date=None, limit=None, offset=None):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    if date:
        query = f'''
            SELECT a.id, a.employee_id, e.name, e.department, a.date, a.login_time, a.logout_time 
            FROM attendance a 
            JOIN employees e ON a.employee_id = e.employee_id
            WHERE a.date = {p}
            ORDER BY a.login_time DESC
        '''
        if limit:
            query += f" LIMIT {limit}"
        if offset:
            query += f" OFFSET {offset}"
        cursor.execute(query, (date,))
    else:
        query = '''
            SELECT a.id, a.employee_id, e.name, e.department, a.date, a.login_time, a.logout_time 
            FROM attendance a 
            JOIN employees e ON a.employee_id = e.employee_id
            ORDER BY a.date DESC, a.login_time DESC
        '''
        if limit:
            query += f" LIMIT {limit}"
        if offset:
            query += f" OFFSET {offset}"
        cursor.execute(query)
    logs = cursor.fetchall()
    release_db_connection(conn)
    return logs

def get_attendance_logs_count(date=None):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    if date:
        cursor.execute(f"SELECT COUNT(*) FROM attendance WHERE date = {p}", (date,))
    else:
        cursor.execute("SELECT COUNT(*) FROM attendance")
    
    count_row = cursor.fetchone()
    # Handle dict or tuple
    count = count_row['count'] if isinstance(count_row, dict) and 'count' in count_row else count_row[0]
    release_db_connection(conn)
    return count

def update_attendance_time(record_id, login_time, logout_time):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    try:
        cursor.execute(f'''
            UPDATE attendance 
            SET login_time = {p}, logout_time = {p} 
            WHERE id = {p}
        ''', (login_time, logout_time, record_id))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error updating attendance time: {e}")
        return False
    finally:
        release_db_connection(conn)

def delete_attendance_record(record_id):
    conn = get_db_connection()
    cursor = get_cursor(conn)
    p = get_placeholder()
    try:
        cursor.execute(f"DELETE FROM attendance WHERE id = {p}", (record_id,))
        conn.commit()
        return True
    except Exception as e:
        print(f"Error deleting attendance record: {e}")
        return False
    finally:
        release_db_connection(conn)
