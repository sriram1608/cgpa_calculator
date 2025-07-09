from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os
import re

app = Flask(__name__)
app.secret_key = "cgpa_secret"
DATABASE = 'database.db'

# Initialize DB and default admin
def init_db():
    conn = sqlite3.connect('database.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,
        name TEXT,
        password TEXT,
        department TEXT,
        graduation_year TEXT,
        role TEXT
    )''')
    conn.execute('''CREATE TABLE IF NOT EXISTS marks (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        enrollment TEXT,
        semester INTEGER,
        credits INTEGER,
        grade_point REAL
    )''')
    conn.commit()
    conn.close()

# Connect to SQLite
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return redirect('/login')

# -------------------- LOGIN --------------------
@app.route('/login', methods=['POST'])
def login():
    email = request.form['email']
    password = request.form['password']

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password=?", (email, password))
    user = cur.fetchone()
    conn.close()

    if user:
        session['user'] = user[0]  # email
        session['role'] = user[5]
        return redirect('/dashboard')
    return render_template('login.html', error="Incorrect credentials")


# -------------------- SIGNUP --------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        email = request.form['email']
        name = request.form['name']
        password = request.form['password']
        department = request.form['department']
        graduation = request.form['graduation']

        # Validate password strength
        if not re.match(r'^(?=.*[A-Z])(?=.*[!@#$%^&*]).{8,}$', password):
            return "Password must be 8+ characters, with 1 capital and 1 special character"

        conn = sqlite3.connect('database.db')
        try:
            conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                         (email, name, password, department, graduation, 'student'))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Email already registered"
        finally:
            conn.close()
        return redirect('/')
    return render_template('signup.html')

# -------------------- LOGOUT --------------------
@app.route('/logout')
def logout():
    session.clear()
    return redirect('/login')

# -------------------- STUDENT DASHBOARD --------------------
@app.route('/student')
def student_dashboard():
    if 'role' in session and session['role'] == 'student':
        username = session['username']
        conn = get_db_connection()
        student = conn.execute("SELECT enrollment FROM students WHERE username = ?", (username,)).fetchone()
        enrollment = student['enrollment']
        marks = conn.execute("SELECT semester, credits, grade_point FROM marks WHERE enrollment = ?", (enrollment,)).fetchall()

        # Group by semester
        sem_data = {}
        for row in marks:
            sem = row['semester']
            if sem not in sem_data:
                sem_data[sem] = []
            sem_data[sem].append((row['credits'], row['grade_point']))

        sgpa_list = []
        total_weighted = 0
        total_credits = 0

        for sem in sorted(sem_data.keys()):
            sem_credits = 0
            sem_weighted = 0
            for credit, gp in sem_data[sem]:
                sem_weighted += credit * gp
                sem_credits += credit
            sgpa = round(sem_weighted / sem_credits, 2) if sem_credits > 0 else 0
            sgpa_list.append((sem, sgpa))
            total_weighted += sem_weighted
            total_credits += sem_credits

        cgpa = round(total_weighted / total_credits, 2) if total_credits > 0 else 0
        cgpa_percent = round(cgpa * 10, 2)

        conn.close()
        return render_template('dashboard_student.html',
                               sgpa_list=sgpa_list,
                               cgpa=cgpa,
                               cgpa_percent=cgpa_percent)
    return redirect('/login')

# -------------------- STUDENT ENTER GRADES --------------------
@app.route('/student/enter', methods=['GET', 'POST'])
def student_enter_marks():
    if 'role' in session and session['role'] == 'student':
        conn = get_db_connection()
        student = conn.execute("SELECT enrollment FROM students WHERE username = ?", (session['username'],)).fetchone()
        enrollment = student['enrollment']

        if request.method == 'POST':
            semester = int(request.form['semester'])
            subject_count = int(request.form['subject_count'])

            for i in range(1, subject_count + 1):
                credits = int(request.form[f'credits{i}'])
                gp = int(request.form[f'gp{i}'])
                conn.execute("INSERT INTO marks (enrollment, semester, credits, grade_point) VALUES (?, ?, ?, ?)",
                             (enrollment, semester, credits, gp))

            conn.commit()
            conn.close()
            return redirect('/student')
        conn.close()
        return render_template('enter_marks.html')
    return redirect('/login')

# -------------------- ADMIN DASHBOARD --------------------
@app.route('/admin')
def admin_dashboard():
    if 'role' in session and session['role'] == 'admin':
        return render_template('dashboard_admin.html', data=None)
    return redirect('/login')

# -------------------- ADMIN VIEW STUDENT GRADES --------------------
@app.route('/admin/view', methods=['POST'])
def admin_search():
    if 'role' in session and session['role'] == 'admin':
        enrollment = request.form['enrollment']
        conn = get_db_connection()

        student = conn.execute("SELECT name FROM students WHERE enrollment = ?", (enrollment,)).fetchone()
        marks = conn.execute("SELECT semester, credits, grade_point FROM marks WHERE enrollment = ?", (enrollment,)).fetchall()

        # Group by semester
        sem_data = {}
        for row in marks:
            sem = row['semester']
            if sem not in sem_data:
                sem_data[sem] = []
            sem_data[sem].append((row['credits'], row['grade_point']))

        sgpa_list = []
        total_weighted = 0
        total_credits = 0

        for sem in sorted(sem_data.keys()):
            sem_credits = 0
            sem_weighted = 0
            for credit, gp in sem_data[sem]:
                sem_weighted += credit * gp
                sem_credits += credit
            sgpa = round(sem_weighted / sem_credits, 2) if sem_credits > 0 else 0
            sgpa_list.append((sem, sgpa))
            total_weighted += sem_weighted
            total_credits += sem_credits

        cgpa = round(total_weighted / total_credits, 2) if total_credits > 0 else 0
        cgpa_percent = round(cgpa * 10, 2)

        conn.close()

        return render_template('dashboard_admin.html',
                               student_name=student['name'] if student else enrollment,
                               sgpa_list=sgpa_list,
                               cgpa=cgpa,
                               cgpa_percent=cgpa_percent)
    return redirect('/login')

# -------------------- ADMIN DELETE STUDENT --------------------
@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    if 'role' in session and session['role'] == 'admin':
        enrollment = request.form['enrollment']
        conn = get_db_connection()

        student = conn.execute("SELECT username FROM students WHERE enrollment = ?", (enrollment,)).fetchone()

        if student:
            username = student['username']
            conn.execute("DELETE FROM marks WHERE enrollment = ?", (enrollment,))
            conn.execute("DELETE FROM students WHERE enrollment = ?", (enrollment,))
            conn.execute("DELETE FROM users WHERE username = ?", (username,))
            conn.commit()
            flash("Student deleted successfully!")
        else:
            flash("Enrollment not found.")

        conn.close()
        return redirect('/admin')
    return redirect('/login')

# -------------------- RUN APP --------------------
if __name__ == '__main__':
    init_db()
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT",5000)))
