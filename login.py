from flask import Flask, render_template, request, jsonify
import smtplib
from email.mime.text import MIMEText
import random
import string

app = Flask(__name__)

# --- CONFIGURATION ---
# REPLACE THESE WITH YOUR ACTUAL CREDENTIALS
SENDER_EMAIL = "keyawins@gmail.com"
SENDER_PASSWORD = "WINS@1313" 
# Note: For Gmail, you need to use an "App Password" if 2FA is on.
# Go to Google Account -> Security -> 2-Step Verification -> App passwords.

# In-memory storage (for demo purposes)
users_db = {}  # {email: {name, password}}
otp_storage = {} # {email: otp_code}

def generate_otp():
    return ''.join(random.choices(string.digits, k=6))

def send_email(to_email, otp):
    subject = "Your Verification Code"
    body = f"Your verification code is: {otp}"
    msg = MIMEText(body)
    msg['Subject'] = subject
    msg['From'] = SENDER_EMAIL
    msg['To'] = to_email

    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.sendmail(SENDER_EMAIL, to_email, msg.as_string())
        return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/send_otp', methods=['POST'])
def send_otp_route():
    data = request.json
    email = data.get('email')
    
    if not email:
        return jsonify({"success": False, "message": "Email is required"}), 400
    
    if email in users_db:
        return jsonify({"success": False, "message": "User already exists"}), 400

    otp = generate_otp()
    otp_storage[email] = otp
    
    # Try to send real email
    if SENDER_EMAIL != "your_email@gmail.com":
        if send_email(email, otp):
            return jsonify({"success": True, "message": "OTP sent to your email"})
        else:
            return jsonify({"success": False, "message": "Failed to send email. Check server logs."}), 500
    else:
        # Fallback for demo if credentials aren't set
        print(f"Simulating email to {email}: OTP is {otp}")
        return jsonify({"success": True, "message": f"OTP sent (Simulated: {otp})"}), 200

@app.route('/register', methods=['POST'])
def register():
    data = request.json
    name = data.get('name')
    email = data.get('email')
    password = data.get('password')
    otp = data.get('otp')

    if not all([name, email, password, otp]):
        return jsonify({"success": False, "message": "All fields are required"}), 400

    if otp_storage.get(email) != otp:
        return jsonify({"success": False, "message": "Invalid OTP"}), 400

    # Register user
    users_db[email] = {"name": name, "password": password}
    
    # Cleanup OTP
    del otp_storage[email]

    return jsonify({"success": True, "message": "Registration successful"})

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    email = data.get('email')
    password = data.get('password')

    user = users_db.get(email)
    
    if user and user['password'] == password:
        return jsonify({"success": True, "message": f"Welcome back, {user['name']}!"})
    else:
        return jsonify({"success": False, "message": "Invalid email or password"}), 401

if __name__ == '__main__':
    app.run(debug=True)
