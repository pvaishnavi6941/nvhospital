from flask import Flask, render_template, request, redirect, url_for, session, flash, jsonify
import psycopg2
from psycopg2.extras import RealDictCursor
import os
from werkzeug.security import generate_password_hash, check_password_hash

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-change-this')

# Database configuration
DB_CONFIG = {
    'host': os.environ.get('DB_HOST', 'dpg-d2lvip15pdvs73b61rs0-a'),
    'database': os.environ.get('DB_NAME', 'nvhospital_db'),
    'user': os.environ.get('DB_USER', 'nvhospital_db_user'),
    'password': os.environ.get('DB_PASSWORD', 'WHQJYXBwjnqWn5oR6gu5euEozt0ftuDY'),
    'port': os.environ.get('DB_PORT', 5432)
}

def get_db_connection():
    """Get database connection"""
    try:
        conn = psycopg2.connect(**DB_CONFIG)
        return conn
    except psycopg2.Error as e:
        print(f"Database connection error: {e}")
        return None

def init_db():
    """Initialize database tables"""
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor()
            
            # Create users table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    username VARCHAR(50) UNIQUE NOT NULL,
                    email VARCHAR(100) UNIQUE NOT NULL,
                    password_hash VARCHAR(255) NOT NULL,
                    role VARCHAR(20) DEFAULT 'patient',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create appointments table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS appointments (
                    id SERIAL PRIMARY KEY,
                    patient_id INTEGER REFERENCES users(id),
                    doctor_name VARCHAR(100) NOT NULL,
                    appointment_date DATE NOT NULL,
                    appointment_time TIME NOT NULL,
                    department VARCHAR(50) NOT NULL,
                    status VARCHAR(20) DEFAULT 'scheduled',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Create doctors table
            cur.execute('''
                CREATE TABLE IF NOT EXISTS doctors (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) NOT NULL,
                    specialization VARCHAR(100) NOT NULL,
                    department VARCHAR(50) NOT NULL,
                    experience INTEGER,
                    contact VARCHAR(15),
                    email VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            print("Database tables created successfully")
            
        except psycopg2.Error as e:
            print(f"Error creating tables: {e}")
            conn.rollback()
        finally:
            cur.close()
            conn.close()

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form.get('username')
        email = request.form.get('email')
        password = request.form.get('password')
        
        if not username or not email or not password:
            flash('All fields are required', 'error')
            return render_template('register.html')
        
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                
                # Check if user already exists
                cur.execute('SELECT id FROM users WHERE username = %s OR email = %s', (username, email))
                if cur.fetchone():
                    flash('Username or email already exists', 'error')
                    return render_template('register.html')
                
                # Create new user
                password_hash = generate_password_hash(password)
                cur.execute(
                    'INSERT INTO users (username, email, password_hash) VALUES (%s, %s, %s)',
                    (username, email, password_hash)
                )
                conn.commit()
                flash('Registration successful! Please login.', 'success')
                return redirect(url_for('login'))
                
            except psycopg2.Error as e:
                flash(f'Registration failed: {e}', 'error')
                conn.rollback()
            finally:
                cur.close()
                conn.close()
        else:
            flash('Database connection failed', 'error')
    
    return render_template('register.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        
        if not username or not password:
            flash('Username and password are required', 'error')
            return render_template('login.html')
        
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor(cursor_factory=RealDictCursor)
                cur.execute('SELECT * FROM users WHERE username = %s', (username,))
                user = cur.fetchone()
                
                if user and check_password_hash(user['password_hash'], password):
                    session['user_id'] = user['id']
                    session['username'] = user['username']
                    session['role'] = user['role']
                    flash('Login successful!', 'success')
                    return redirect(url_for('dashboard'))
                else:
                    flash('Invalid username or password', 'error')
                    
            except psycopg2.Error as e:
                flash(f'Login failed: {e}', 'error')
            finally:
                cur.close()
                conn.close()
        else:
            flash('Database connection failed', 'error')
    
    return render_template('login.html')

@app.route('/dashboard')
def dashboard():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    return render_template('dashboard.html', username=session.get('username'))

@app.route('/book_appointment', methods=['GET', 'POST'])
def book_appointment():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    if request.method == 'POST':
        doctor_name = request.form.get('doctor_name')
        appointment_date = request.form.get('appointment_date')
        appointment_time = request.form.get('appointment_time')
        department = request.form.get('department')
        
        if not all([doctor_name, appointment_date, appointment_time, department]):
            flash('All fields are required', 'error')
            return render_template('book_appointment.html')
        
        conn = get_db_connection()
        if conn:
            try:
                cur = conn.cursor()
                cur.execute(
                    '''INSERT INTO appointments (patient_id, doctor_name, appointment_date, 
                       appointment_time, department) VALUES (%s, %s, %s, %s, %s)''',
                    (session['user_id'], doctor_name, appointment_date, appointment_time, department)
                )
                conn.commit()
                flash('Appointment booked successfully!', 'success')
                return redirect(url_for('my_appointments'))
                
            except psycopg2.Error as e:
                flash(f'Failed to book appointment: {e}', 'error')
                conn.rollback()
            finally:
                cur.close()
                conn.close()
        else:
            flash('Database connection failed', 'error')
    
    return render_template('book_appointment.html')

@app.route('/my_appointments')
def my_appointments():
    if 'user_id' not in session:
        return redirect(url_for('login'))
    
    appointments = []
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute(
                '''SELECT * FROM appointments WHERE patient_id = %s 
                   ORDER BY appointment_date DESC, appointment_time DESC''',
                (session['user_id'],)
            )
            appointments = cur.fetchall()
            
        except psycopg2.Error as e:
            flash(f'Failed to fetch appointments: {e}', 'error')
        finally:
            cur.close()
            conn.close()
    
    return render_template('my_appointments.html', appointments=appointments)

@app.route('/doctors')
def doctors():
    doctors_list = []
    conn = get_db_connection()
    if conn:
        try:
            cur = conn.cursor(cursor_factory=RealDictCursor)
            cur.execute('SELECT * FROM doctors ORDER BY name')
            doctors_list = cur.fetchall()
            
        except psycopg2.Error as e:
            flash(f'Failed to fetch doctors: {e}', 'error')
        finally:
            cur.close()
            conn.close()
    
    return render_template('doctors.html', doctors=doctors_list)

@app.route('/logout')
def logout():
    session.clear()
    flash('You have been logged out successfully', 'success')
    return redirect(url_for('index'))

@app.errorhandler(404)
def not_found(error):
    return render_template('404.html'), 404

@app.errorhandler(500)
def internal_error(error):
    return render_template('500.html'), 500

if __name__ == '__main__':
    # Initialize database tables
    init_db()
    
    # Run the app
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=False)
