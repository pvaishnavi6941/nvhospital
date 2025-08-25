from flask import Flask, render_template, request, redirect, url_for, flash, jsonify, session
from flask_mysqldb import MySQL
from werkzeug.security import generate_password_hash, check_password_hash
import os
from datetime import datetime, timedelta
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import secrets

app = Flask(__name__)

# Database Configuration for Render
import os
app.config['MYSQL_HOST'] = os.environ.get('DB_HOST', 'localhost')
app.config['MYSQL_USER'] = os.environ.get('DB_USER', 'root')
app.config['MYSQL_PASSWORD'] = os.environ.get('DB_PASSWORD', '3006')
app.config['MYSQL_DB'] = os.environ.get('DB_NAME', 'hospital_management')
app.config['SECRET_KEY'] = 'hospital_management_secret_key'  # Fixed secret key instead of random

mysql = MySQL(app)

# Routes
@app.route('/')
def home():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        data = request.get_json()
        email = data.get('email')
        password = data.get('password')
        
        cur = mysql.connection.cursor()
        try:
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            print(f"Login attempt for email: {email}")  # Add logging
            print(f"User found: {user is not None}")    # Add logging
            
            if user:
                # Check if password matches the stored hash
                if check_password_hash(user[3], password):
                    # Update last login time
                    cur.execute("UPDATE users SET last_login = %s WHERE id = %s", 
                              (datetime.now(), user[0]))
                    
                    # Set session
                    session['user_id'] = user[0]
                    session['email'] = user[2]
                    session['name'] = user[1]
                    
                    mysql.connection.commit()
                    
                    return jsonify({
                        'success': True,
                        'redirect': url_for('dashboard')
                    })
                else:
                    print("Password verification failed")  # Add logging
            
            return jsonify({
                'success': False,
                'message': 'Invalid email or password'
            })
                
        except Exception as e:
            print(f"Login error: {str(e)}")  # Add logging
            return jsonify({
                'success': False,
                'message': str(e)
            })
        finally:
            cur.close()
            
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        data = request.get_json()
        name = data.get('name')
        email = data.get('email')
        password = data.get('password')
        
        # Generate password hash
        hashed_password = generate_password_hash(password)
        
        cur = mysql.connection.cursor()
        try:
            # First check if email already exists
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            existing_user = cur.fetchone()
            
            if existing_user:
                return jsonify({
                    'success': False,
                    'message': 'Email already registered'
                })
            
            # If email doesn't exist, create new user
            cur.execute("""
                INSERT INTO users (full_name, email, password, created_at)
                VALUES (%s, %s, %s, %s)
            """, (name, email, hashed_password, datetime.now()))
            mysql.connection.commit()
            
            # Get the newly created user
            cur.execute("SELECT * FROM users WHERE email = %s", (email,))
            user = cur.fetchone()
            
            if user:
                # Set session
                session['user_id'] = user[0]
                session['email'] = user[2]
                session['name'] = user[1]
                
                return jsonify({
                    'success': True,
                    'redirect': url_for('dashboard')
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to create user'
                })
                
        except Exception as e:
            print(f"Signup error: {str(e)}")  # Add logging
            return jsonify({
                'success': False,
                'message': f'An error occurred during registration: {str(e)}'
            })
        finally:
            cur.close()
    
    return render_template('login.html')

@app.route('/appointment')
def appointment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('login'))

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    return render_template('user_dashboard.html')



@app.route('/contact', methods=['POST'])
def contact():
    try:
        # Get data from the form
        if request.content_type == 'application/json':
            # Handle JSON requests
            data = request.get_json()
            name = data.get('name')
            email = data.get('email')
            message = data.get('message')
        else:
            # Handle form data requests
            name = request.form.get('name')
            email = request.form.get('email')
            message = request.form.get('message')
        
        # Validate required fields
        if not all([name, email, message]):
            return jsonify({
                'success': False, 
                'message': 'All fields are required (name, email, message)'
            }), 400
        
        # Validate email format (basic validation)
        import re
        email_pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        if not re.match(email_pattern, email):
            return jsonify({
                'success': False, 
                'message': 'Please enter a valid email address'
            }), 400
        
        # Insert into database
        cur = mysql.connection.cursor()
        
        # Insert the contact query
        cur.execute("""
            INSERT INTO contact_queries (name, email, message, submitted_at)
            VALUES (%s, %s, %s, %s)
        """, (name, email, message, datetime.now()))
        
        mysql.connection.commit()
        
        # Get the inserted record ID
        query_id = cur.lastrowid
        
        return jsonify({
            'success': True, 
            'message': 'Thank you for your query! We will get back to you soon.',
            'query_id': query_id
        }), 200
        
    except Exception as e:
        print(f"Contact form error: {str(e)}")
        return jsonify({
            'success': False, 
            'message': 'An error occurred while submitting your query. Please try again.'
        }), 500
        
    finally:
        if 'cur' in locals():
            cur.close()


# Optional: Route to get all contact queries (for admin use)
@app.route('/admin/contact-queries')
def get_contact_queries():
    # Add authentication check here if needed
    # if 'admin' not in session:
    #     return redirect(url_for('login'))
    
    try:
        cur = mysql.connection.cursor()
        cur.execute("""
            SELECT id, name, email, message, submitted_at, status 
            FROM contact_queries 
            ORDER BY submitted_at DESC
        """)
        
        queries = cur.fetchall()
        
        # Convert to list of dictionaries for easier handling
        query_list = []
        for query in queries:
            query_list.append({
                'id': query[0],
                'name': query[1],
                'email': query[2],
                'message': query[3],
                'submitted_at': query[4].strftime('%Y-%m-%d %H:%M:%S') if query[4] else None,
                'status': query[5]
            })
        
        return jsonify({
            'success': True,
            'queries': query_list
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
    finally:
        cur.close()


# Optional: Route to update query status
@app.route('/admin/contact-queries/<int:query_id>/status', methods=['PUT'])
def update_query_status(query_id):
    # Add authentication check here if needed
    
    try:
        data = request.get_json()
        new_status = data.get('status')
        
        if new_status not in ['pending', 'responded', 'closed']:
            return jsonify({
                'success': False,
                'message': 'Invalid status. Must be pending, responded, or closed'
            }), 400
        
        cur = mysql.connection.cursor()
        cur.execute("""
            UPDATE contact_queries 
            SET status = %s, updated_at = %s 
            WHERE id = %s
        """, (new_status, datetime.now(), query_id))
        
        mysql.connection.commit()
        
        if cur.rowcount == 0:
            return jsonify({
                'success': False,
                'message': 'Query not found'
            }), 404
        
        return jsonify({
            'success': True,
            'message': 'Query status updated successfully'
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500
        
    finally:
        cur.close()


# Email configuration
EMAIL_ADDRESS = "nivasreddybobby20@gmail.com"
EMAIL_PASSWORD = "fqkd zuvp bdbq ihkh"

def send_confirmation_email(recipient_email, appointment_details):
    msg = MIMEMultipart()
    msg['From'] = EMAIL_ADDRESS
    msg['To'] = recipient_email
    msg['Subject'] = "Appointment Confirmation"
    
    body = f"""
    Dear {appointment_details['name']},

    Your appointment has been successfully booked!

    Details:
    Doctor: {appointment_details['doctor']}
    Date: {appointment_details['date']}
    Time: {appointment_details['time']}

    Please arrive 10 minutes before your scheduled time.
    If you need to reschedule, please contact us at least 24 hours in advance.

    Best regards,
    Hospital Management Team
    """
    
    msg.attach(MIMEText(body, 'plain'))
    
    try:
        server = smtplib.SMTP('smtp.gmail.com', 587)
        server.starttls()
        server.login(EMAIL_ADDRESS, EMAIL_PASSWORD)
        server.send_message(msg)
        server.quit()
        return True
    except Exception as e:
        print(f"Email error: {str(e)}")
        return False

@app.route('/book-appointment', methods=['POST'])
def book_appointment():
    if 'user_id' not in session:
        return jsonify({
            'success': False,
            'message': 'Please log in to book an appointment'
        })
        
    try:
        data = request.json
        
        # Validate required fields
        required_fields = ['name', 'email', 'doctor', 'date', 'time']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'{field.capitalize()} is required'
                })
        
        # Validate appointment time is in the future
        appointment_datetime = datetime.strptime(
            f"{data['date']} {data['time']}", 
            "%Y-%m-%d %H:%M"
        )
        
        if appointment_datetime < datetime.now():
            return jsonify({
                'success': False,
                'message': 'Please select a future date and time'
            })
        
        # Validate doctor selection
        valid_doctors = [
            'Dr. Naveen Reddy',
            'Dr. Manoj Patel',
            'Dr. Shalini Desai'
        ]
        
        if data['doctor'] not in valid_doctors:
            return jsonify({
                'success': False,
                'message': 'Please select a valid doctor'
            })
        
        # Insert appointment into database
        cur = mysql.connection.cursor()
        cur.execute("""
            INSERT INTO appointments 
            (patient_name, email, doctor, appointment_date, appointment_time, status)
            VALUES (%s, %s, %s, %s, %s, %s)
        """, (
            data['name'],
            data['email'],
            data['doctor'],
            data['date'],
            data['time'],
            'scheduled'
        ))
        
        mysql.connection.commit()
        
        # Send confirmation email
        if send_confirmation_email(data['email'], data):
            return jsonify({
                'success': True,
                'message': 'Appointment booked successfully'
            })
        else:
            return jsonify({
                'success': True,
                'message': 'Appointment booked successfully, but email confirmation failed'
            })
            
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e)
        })
    finally:
        cur.close()


if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
