from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os
import re

app = Flask(__name__)
app.secret_key = "cgpa_secret"
DATABASE = 'database.db'

# Initialize DB and default admin
def init_db():
    if not os.path.exists(DATABASE):
        with open('schema.sql', 'r') as f:
            schema = f.read()
        conn = sqlite3.connect(DATABASE)
        conn.executescript(schema)
        conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", ("admin", "admin@123", "admin"))
        conn.commit()
        conn.close()
        print("Database initialized.")

# Connect to SQLite
def get_db_connection():
    conn = sqlite3.connect(DATABASE)
    conn.row_factory = sqlite3.Row
    return conn

@app.route('/')
def index():
    return redirect('/login')

# -------------------- LOGIN --------------------
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        uname = request.form['username']
        pwd = request.form['password']
        conn = get_db_connection()
        user = conn.execute('SELECT * FROM users WHERE username = ? AND password = ?', (uname, pwd)).fetchone()
        conn.close()
        if user:
            session['username'] = user['username']
            session['role'] = user['role']
            if user['role'] == 'admin':
                return redirect('/admin')
            else:
                return redirect('/student')
        else:
            flash("Incorrect username or password.")
            return render_template('login.html')  # re-render with message
    return render_template('login.html')


# -------------------- SIGNUP --------------------
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        name = request.form['name']
        enrollment = request.form['enrollment']

        # Password strength check
        if (len(password) < 8 or
            not re.search(r"[A-Z]", password) or
            not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password)):
            flash("Password must be at least 8 characters long, contain a capital letter and a special character.")
            return render_template('signup.html')

        try:
            conn = get_db_connection()
            conn.execute("INSERT INTO users (username, password, role) VALUES (?, ?, ?)", (username, password, 'student'))
            conn.execute("INSERT INTO students (enrollment, name, username) VALUES (?, ?, ?)", (enrollment, name, username))
            conn.commit()
            conn.close()
            return redirect('/login')
        except sqlite3.IntegrityError:
            flash("Username or Enrollment already exists.")
            return render_template('signup.html')
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
