from flask import Flask, render_template, request, redirect, session, flash
import sqlite3
import os
import re

app = Flask(__name__)
app.secret_key = 'your_secret_key_here'
app.config['TEMPLATES_AUTO_RELOAD'] = True
app.config['SEND_FILE_MAX_AGE_DEFAULT'] = 0

# ---------- DATABASE SETUP ----------
def init_db():
    conn = sqlite3.connect('database.db')
    conn.execute('''CREATE TABLE IF NOT EXISTS users (
        email TEXT PRIMARY KEY,  -- Actually stores enrollment number for students
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
        subject_code TEXT,
        credits INTEGER,
        grade_point REAL
    )''')
    conn.commit()
    conn.close()

# ---------- INITIALIZE DATABASE + DEFAULT ADMIN ----------
with app.app_context():
    init_db()
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email='ADMIN001'")
    if not cur.fetchone():
        cur.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                    ('ADMIN001', 'Admin', 'admin@123', 'Admin Dept', '2020 - 2024', 'admin'))
    conn.commit()
    conn.close()

# ---------- ROUTES ----------

@app.route('/')
def home():
    return render_template('login.html')

@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        name = request.form['name']
        enrollment = request.form['enrollment']
        password = request.form['password']
        department = request.form['department']
        graduation = request.form['graduation']

        # Password validation
        if not re.match(r'^(?=.*[A-Z])(?=.*[!@#$%^&*]).{8,}$', password):
            return "Password must be 8+ characters long, include one capital and one special character."

        conn = sqlite3.connect('database.db')
        try:
            # Use enrollment number as the primary key (email field in database)
            # This maintains compatibility with existing database structure
            conn.execute("INSERT INTO users VALUES (?, ?, ?, ?, ?, ?)",
                         (enrollment, name, password, department, graduation, 'student'))
            conn.commit()
        except sqlite3.IntegrityError:
            return "Enrollment number already registered."
        finally:
            conn.close()
        return redirect('/')
    return render_template('signup.html')

@app.route('/login', methods=['POST'])
def login():
    enrollment = request.form['enrollment']
    password = request.form['password']

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT * FROM users WHERE email=? AND password=?", (enrollment, password))
    user = cur.fetchone()
    conn.close()

    if user:
        session['user'] = user[0]  # enrollment
        session['role'] = user[5]  # role
        return redirect('/dashboard')
    else:
        return render_template('login.html', error="Incorrect credentials")

@app.route('/dashboard')
def dashboard():
    if 'user' not in session:
        return redirect('/')
    if session['role'] == 'admin':
        return render_template('dashboard_admin.html')

    # For students, calculate SGPA and CGPA using standard academic formula
    # CGPA = Σ(C × GP) / Σ C (for semesters 1 to 8)
    # For CGPA: Use only the most recent marks for each subject code
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Get all marks for SGPA calculation (semester-wise)
    cur.execute("SELECT semester, subject_code, credits, grade_point FROM marks WHERE enrollment=? AND semester BETWEEN 1 AND 8 ORDER BY semester", (session['user'],))
    all_marks = cur.fetchall()

    # Get most recent marks for each subject for CGPA calculation
    # Handle UNKNOWN subject codes separately - treat each as individual subject
    cur.execute("""
        SELECT m1.subject_code, m1.credits, m1.grade_point, m1.semester, m1.id
        FROM marks m1
        WHERE m1.enrollment=? AND m1.semester BETWEEN 1 AND 8
        AND (
            m1.subject_code = 'UNKNOWN'
            OR m1.id IN (
                SELECT MAX(id) as max_id
                FROM marks
                WHERE enrollment=? AND semester BETWEEN 1 AND 8 AND subject_code != 'UNKNOWN'
                GROUP BY subject_code
            )
        )
        ORDER BY m1.semester, m1.id
    """, (session['user'], session['user']))
    recent_marks = cur.fetchall()
    conn.close()

    if all_marks:
        # Calculate SGPA for each semester (1 to 8) using all marks
        semester_data = {}
        for semester, subject_code, credits, grade_point in all_marks:
            if semester not in semester_data:
                semester_data[semester] = {'total_credits': 0, 'total_points': 0}
            semester_data[semester]['total_credits'] += credits
            semester_data[semester]['total_points'] += credits * grade_point

        sgpa_list = []
        # Process semesters 1 to 8 in order for SGPA display
        for semester in range(1, 9):
            if semester in semester_data:
                # Calculate SGPA for this semester
                sgpa = round(semester_data[semester]['total_points'] / semester_data[semester]['total_credits'], 2)
                sgpa_list.append((semester, sgpa))

        # Calculate CGPA using only most recent marks for each subject
        # Variables for CGPA calculation: Σ(C × GP) / Σ C
        sum_c_gp = 0  # Σ(C × GP) - Sum of (Credits × Grade Points) for unique subjects
        sum_c = 0     # Σ C - Sum of Credits for unique subjects

        for subject_code, credits, grade_point, semester, mark_id in recent_marks:
            sum_c_gp += credits * grade_point
            sum_c += credits

        # Calculate CGPA using standard formula: CGPA = Σ(C × GP) / Σ C
        cgpa = round(sum_c_gp / sum_c, 2) if sum_c > 0 else 0
        cgpa_percent = round((cgpa / 10) * 100, 2)

        return render_template('dashboard_student.html',
                             sgpa_list=sgpa_list,
                             cgpa=cgpa,
                             cgpa_percent=cgpa_percent)

    return render_template('dashboard_student.html')

@app.route('/student/enter', methods=['GET', 'POST'])
def student_enter_marks():
    if 'user' not in session or session['role'] != 'student':
        return redirect('/')
    if request.method == 'POST':
        semester = int(request.form['semester'])
        subjects = int(request.form['subjects'])

        subject_codes = []
        credits = []
        grades = []
        for i in range(subjects):
            subject_codes.append(request.form[f'subject_code_{i}'].upper().strip())
            credits.append(int(request.form[f'credit_{i}']))
            grades.append(float(request.form[f'grade_{i}']))

        conn = sqlite3.connect('database.db')
        for i in range(subjects):
            conn.execute("INSERT INTO marks (enrollment, semester, subject_code, credits, grade_point) VALUES (?, ?, ?, ?, ?)",
                         (session['user'], semester, subject_codes[i], credits[i], grades[i]))
        conn.commit()
        conn.close()
        flash("Grades entered successfully!")
        return redirect('/dashboard')

    # Return template directly to bypass caching
    template_content = '''<!DOCTYPE html>
<html>
<head>
    <title>Enter Grades with Subject Codes</title>
    <style>
        body { font-family: Arial, sans-serif; background-color: #f1f1f1; padding: 20px; }
        .container { max-width: 800px; margin: auto; padding: 30px; background: white; border-radius: 10px; box-shadow: 0 4px 6px rgba(0,0,0,0.1); }
        h2 { text-align: center; color: #333; margin-bottom: 30px; }
        h4 { color: #007bff; margin-top: 20px; margin-bottom: 10px; border-bottom: 2px solid #007bff; padding-bottom: 5px; }
        input[type="number"], input[type="text"] { width: 100%; padding: 12px; margin: 8px 0; border: 2px solid #ddd; border-radius: 6px; font-size: 16px; box-sizing: border-box; }
        input[type="number"]:focus, input[type="text"]:focus { border-color: #007bff; outline: none; box-shadow: 0 0 5px rgba(0,123,255,0.3); }
        button { background-color: #28a745; color: white; padding: 15px 30px; border: none; border-radius: 6px; cursor: pointer; font-size: 16px; font-weight: bold; width: 100%; margin-top: 20px; }
        button:hover { background-color: #218838; }
        .back-link { display: inline-block; margin-top: 20px; color: #007bff; text-decoration: none; font-weight: bold; padding: 10px 20px; border: 2px solid #007bff; border-radius: 6px; }
        .back-link:hover { background-color: #007bff; color: white; }
        #subjects { margin-top: 20px; }
        .subject-group { background-color: #f8f9fa; padding: 15px; border-radius: 8px; margin-bottom: 15px; border-left: 4px solid #007bff; }
        .field-label { font-weight: bold; color: #495057; margin-bottom: 5px; display: block; }
    </style>
    <script>
        function generateFields() {
            const count = document.getElementById("subject_count").value;
            const container = document.getElementById("subjects");
            container.innerHTML = "";
            for (let i = 1; i <= count; i++) {
                const subjectDiv = document.createElement('div');
                subjectDiv.className = 'subject-group';
                subjectDiv.innerHTML = `
                    <h4>Subject ${i}</h4>
                    <label class="field-label">Subject Code:</label>
                    <input type="text" name="subject_code_${i-1}" placeholder="Subject Code (e.g., CS101, MATH101)" required maxlength="10" style="text-transform: uppercase;">
                    <label class="field-label">Credits:</label>
                    <input type="number" name="credit_${i-1}" placeholder="Credits (1-10)" required min="1" max="10">
                    <label class="field-label">Grade Point:</label>
                    <input type="number" name="grade_${i-1}" placeholder="Grade Point (0-10)" min="0" max="10" step="0.1" required>
                `;
                container.appendChild(subjectDiv);
            }
        }
    </script>
</head>
<body>
<div class="container">
    <h2>Enter Grades with Subject Codes</h2>
    <form method="post">
        <label class="field-label">Semester:</label>
        <input type="number" name="semester" placeholder="Semester (1-8)" required min="1" max="8">
        <label class="field-label">Number of Subjects:</label>
        <input type="number" id="subject_count" name="subjects" placeholder="Number of Subjects" required oninput="generateFields()">
        <div id="subjects"></div>
        <button type="submit">Submit Grades</button>
    </form>
    <a href="/dashboard" class="back-link">Back to Dashboard</a>
</div>
</body>
</html>'''
    from flask import make_response
    response = make_response(template_content)
    response.headers['Content-Type'] = 'text/html'
    response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
    response.headers['Pragma'] = 'no-cache'
    response.headers['Expires'] = '0'
    return response

@app.route('/student/edit', methods=['GET', 'POST'])
def student_edit_marks():
    if 'user' not in session or session['role'] != 'student':
        return redirect('/')

    if request.method == 'POST':
        # Handle mark updates
        mark_id = request.form['mark_id']
        new_subject_code = request.form['subject_code'].upper().strip()
        new_credits = int(request.form['credits'])
        new_grade = float(request.form['grade_point'])

        conn = sqlite3.connect('database.db')
        conn.execute("UPDATE marks SET subject_code=?, credits=?, grade_point=? WHERE id=? AND enrollment=?",
                     (new_subject_code, new_credits, new_grade, mark_id, session['user']))
        conn.commit()
        conn.close()
        flash("Marks updated successfully!")
        return redirect('/dashboard')

    # GET request - show all marks for editing
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT id, semester, subject_code, credits, grade_point FROM marks WHERE enrollment=? ORDER BY semester",
                (session['user'],))
    marks = cur.fetchall()
    conn.close()

    return render_template('edit_marks.html', marks=marks)

@app.route('/student/delete_mark', methods=['POST'])
def student_delete_mark():
    if 'user' not in session or session['role'] != 'student':
        return redirect('/')

    mark_id = request.form['mark_id']
    conn = sqlite3.connect('database.db')
    conn.execute("DELETE FROM marks WHERE id=? AND enrollment=?", (mark_id, session['user']))
    conn.commit()
    conn.close()
    flash("Mark deleted successfully!")
    return redirect('/student/edit')

@app.route('/student/view')
def student_view_marks():
    if 'user' not in session or session['role'] != 'student':
        return redirect('/')
    conn = sqlite3.connect('database.db')
    cur = conn.cursor()
    cur.execute("SELECT semester, credits, grade_point FROM marks WHERE enrollment=?", (session['user'],))
    data = cur.fetchall()
    conn.close()
    return render_template('view.html', data=data)

@app.route('/admin/view', methods=['GET', 'POST'])
def admin_view():
    if 'user' not in session or session['role'] != 'admin':
        return redirect('/')

    data = []
    sgpa_list = []
    cgpa = 0
    cgpa_percent = 0
    student_info = None

    if request.method == 'POST':
        enrollment = request.form['enrollment']
        conn = sqlite3.connect('database.db')
        cur = conn.cursor()

        # Get student information
        cur.execute("SELECT name, department, graduation_year FROM users WHERE email=?", (enrollment,))
        student_info = cur.fetchone()

        # Get all marks for the student
        cur.execute("SELECT semester, subject_code, credits, grade_point FROM marks WHERE enrollment=? ORDER BY semester", (enrollment,))
        all_marks = cur.fetchall()

        # Get most recent marks for CGPA calculation (same logic as student dashboard)
        cur.execute("""
            SELECT m1.subject_code, m1.credits, m1.grade_point, m1.semester, m1.id
            FROM marks m1
            WHERE m1.enrollment=? AND m1.semester BETWEEN 1 AND 8
            AND (
                m1.subject_code = 'UNKNOWN'
                OR m1.id IN (
                    SELECT MAX(id) as max_id
                    FROM marks
                    WHERE enrollment=? AND semester BETWEEN 1 AND 8 AND subject_code != 'UNKNOWN'
                    GROUP BY subject_code
                )
            )
            ORDER BY m1.semester, m1.id
        """, (enrollment, enrollment))
        recent_marks = cur.fetchall()
        conn.close()

        if all_marks:
            # Calculate SGPA for each semester (1 to 8) using all marks
            semester_data = {}
            for semester, subject_code, credits, grade_point in all_marks:
                if semester not in semester_data:
                    semester_data[semester] = {'total_credits': 0, 'total_points': 0}
                semester_data[semester]['total_credits'] += credits
                semester_data[semester]['total_points'] += credits * grade_point

            # Process semesters 1 to 8 in order for SGPA display
            for semester in range(1, 9):
                if semester in semester_data:
                    # Calculate SGPA for this semester
                    sgpa = round(semester_data[semester]['total_points'] / semester_data[semester]['total_credits'], 2)
                    sgpa_list.append((semester, sgpa))

            # Calculate CGPA using only most recent marks for each subject
            sum_c_gp = 0  # Σ(C × GP) - Sum of (Credits × Grade Points) for unique subjects
            sum_c = 0     # Σ C - Sum of Credits for unique subjects

            for subject_code, credits, grade_point, semester, mark_id in recent_marks:
                sum_c_gp += credits * grade_point
                sum_c += credits

            # Calculate CGPA using standard formula: CGPA = Σ(C × GP) / Σ C
            cgpa = round(sum_c_gp / sum_c, 2) if sum_c > 0 else 0
            cgpa_percent = round((cgpa / 10) * 100, 2)

        # Prepare data for individual marks display
        data = all_marks

    return render_template('view.html',
                         data=data,
                         sgpa_list=sgpa_list,
                         cgpa=cgpa,
                         cgpa_percent=cgpa_percent,
                         student_info=student_info)

@app.route('/admin/view_all', methods=['GET', 'POST'])
def admin_view_all():
    if 'user' not in session or session['role'] != 'admin':
        return redirect('/')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Get filter parameters
    department_filter = request.form.get('department', '') if request.method == 'POST' else ''
    graduation_filter = request.form.get('graduation_year', '') if request.method == 'POST' else ''

    # Base query to get all students (excluding admin)
    # Note: u.email field actually contains register numbers for students
    # Calculate CGPA using standard academic formula: CGPA = Σ(C × GP) / Σ C
    # Only consider semesters 1 to 8 and use most recent marks for each subject
    query = """
    SELECT u.name, u.email, u.graduation_year, u.department,
           COALESCE(ROUND(SUM(recent_marks.credits * recent_marks.grade_point) / SUM(recent_marks.credits), 2), 0) as cgpa
    FROM users u
    LEFT JOIN (
        SELECT m1.enrollment, m1.subject_code, m1.credits, m1.grade_point
        FROM marks m1
        INNER JOIN (
            SELECT enrollment, subject_code, MAX(id) as max_id
            FROM marks
            WHERE semester BETWEEN 1 AND 8
            GROUP BY enrollment, subject_code
        ) m2 ON m1.enrollment = m2.enrollment AND m1.subject_code = m2.subject_code AND m1.id = m2.max_id
        WHERE m1.semester BETWEEN 1 AND 8
    ) recent_marks ON u.email = recent_marks.enrollment
    WHERE u.role = 'student'
    """
    params = []

    # Add filters if provided
    if department_filter:
        query += " AND u.department = ?"
        params.append(department_filter)

    if graduation_filter:
        query += " AND u.graduation_year = ?"
        params.append(graduation_filter)

    query += " GROUP BY u.email ORDER BY u.email"  # Sort by register number (stored in email field)

    cur.execute(query, params)
    students = cur.fetchall()

    # Get unique departments and graduation years for filter dropdowns
    cur.execute("SELECT DISTINCT department FROM users WHERE role = 'student' ORDER BY department")
    departments = [row[0] for row in cur.fetchall()]

    cur.execute("SELECT DISTINCT graduation_year FROM users WHERE role = 'student' ORDER BY graduation_year")
    graduation_years = [row[0] for row in cur.fetchall()]

    conn.close()

    return render_template('admin_view_all.html',
                         students=students,
                         departments=departments,
                         graduation_years=graduation_years,
                         selected_department=department_filter,
                         selected_graduation=graduation_filter)

@app.route('/admin/delete', methods=['POST'])
def admin_delete():
    if 'user' not in session or session['role'] != 'admin':
        return redirect('/')
    enrollment = request.form['enrollment']
    conn = sqlite3.connect('database.db')
    conn.execute("DELETE FROM marks WHERE enrollment=?", (enrollment,))
    conn.execute("DELETE FROM users WHERE email=?", (enrollment,))
    conn.commit()
    conn.close()
    flash("Student record deleted successfully!")
    return redirect('/dashboard')

@app.route('/admin/export', methods=['GET', 'POST'])
def admin_export():
    if 'user' not in session or session['role'] != 'admin':
        return redirect('/')

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Build query with filters
    query = "SELECT name, email, department, graduation_year FROM users WHERE role = 'student'"
    params = []

    # Apply filters if this is a POST request
    if request.method == 'POST':
        department_filter = request.form.get('department', '').strip()
        batch_filter = request.form.get('batch', '').strip()

        if department_filter:
            query += " AND department = ?"
            params.append(department_filter)

        if batch_filter:
            query += " AND graduation_year = ?"
            params.append(batch_filter)

    query += " ORDER BY email"  # Sort by register number (stored in email field)

    # Get filtered students
    cur.execute(query, params)
    students = cur.fetchall()

    export_data = []

    for student in students:
        name, enrollment, department, graduation_year = student

        # Get all marks for this student
        cur.execute("SELECT semester, subject_code, credits, grade_point FROM marks WHERE enrollment=? ORDER BY semester", (enrollment,))
        all_marks = cur.fetchall()

        # Get most recent marks for CGPA calculation
        cur.execute("""
            SELECT m1.subject_code, m1.credits, m1.grade_point, m1.semester, m1.id
            FROM marks m1
            WHERE m1.enrollment=? AND m1.semester BETWEEN 1 AND 8
            AND (
                m1.subject_code = 'UNKNOWN'
                OR m1.id IN (
                    SELECT MAX(id) as max_id
                    FROM marks
                    WHERE enrollment=? AND semester BETWEEN 1 AND 8 AND subject_code != 'UNKNOWN'
                    GROUP BY subject_code
                )
            )
            ORDER BY m1.semester, m1.id
        """, (enrollment, enrollment))
        recent_marks = cur.fetchall()

        # Calculate SGPA for each semester
        semester_sgpa = {}
        if all_marks:
            semester_data = {}
            for semester, subject_code, credits, grade_point in all_marks:
                if semester not in semester_data:
                    semester_data[semester] = {'total_credits': 0, 'total_points': 0}
                semester_data[semester]['total_credits'] += credits
                semester_data[semester]['total_points'] += credits * grade_point

            for semester in range(1, 9):
                if semester in semester_data:
                    sgpa = round(semester_data[semester]['total_points'] / semester_data[semester]['total_credits'], 2)
                    semester_sgpa[semester] = sgpa
                else:
                    semester_sgpa[semester] = 0.0
        else:
            for semester in range(1, 9):
                semester_sgpa[semester] = 0.0

        # Calculate CGPA
        cgpa = 0.0
        if recent_marks:
            sum_c_gp = sum(credits * grade_point for _, credits, grade_point, _, _ in recent_marks)
            sum_c = sum(credits for _, credits, _, _, _ in recent_marks)
            cgpa = round(sum_c_gp / sum_c, 2) if sum_c > 0 else 0.0

        # Add to export data
        export_data.append({
            'enrollment': enrollment,
            'name': name,
            'department': department,
            'batch': graduation_year,
            'sgpa_sem1': semester_sgpa[1],
            'sgpa_sem2': semester_sgpa[2],
            'sgpa_sem3': semester_sgpa[3],
            'sgpa_sem4': semester_sgpa[4],
            'sgpa_sem5': semester_sgpa[5],
            'sgpa_sem6': semester_sgpa[6],
            'sgpa_sem7': semester_sgpa[7],
            'sgpa_sem8': semester_sgpa[8],
            'cgpa': cgpa
        })

    conn.close()

    # Generate CSV content
    import io
    output = io.StringIO()

    # Write CSV header
    header = ['Register Number', 'Name', 'Department', 'Batch',
              'SGPA Sem 1', 'SGPA Sem 2', 'SGPA Sem 3', 'SGPA Sem 4',
              'SGPA Sem 5', 'SGPA Sem 6', 'SGPA Sem 7', 'SGPA Sem 8', 'CGPA']
    output.write(','.join(header) + '\n')

    # Write data rows
    for student in export_data:
        row = [
            student['enrollment'], student['name'], student['department'], student['batch'],
            str(student['sgpa_sem1']), str(student['sgpa_sem2']), str(student['sgpa_sem3']), str(student['sgpa_sem4']),
            str(student['sgpa_sem5']), str(student['sgpa_sem6']), str(student['sgpa_sem7']), str(student['sgpa_sem8']),
            str(student['cgpa'])
        ]
        output.write(','.join(row) + '\n')

    # Create response with dynamic filename
    from flask import make_response

    # Generate filename based on filters
    filename = "student_academic_records"
    if request.method == 'POST':
        department_filter = request.form.get('department', '').strip()
        batch_filter = request.form.get('batch', '').strip()

        if department_filter:
            filename += f"_{department_filter.replace(' ', '_')}"
        if batch_filter:
            filename += f"_{batch_filter.replace('-', '_')}"

    filename += ".csv"

    response = make_response(output.getvalue())
    response.headers['Content-Type'] = 'text/csv'
    response.headers['Content-Disposition'] = f'attachment; filename={filename}'

    return response

@app.route('/admin/get_filters', methods=['GET'])
def admin_get_filters():
    if 'user' not in session or session['role'] != 'admin':
        return {'error': 'Unauthorized'}, 401

    conn = sqlite3.connect('database.db')
    cur = conn.cursor()

    # Get unique departments
    cur.execute("SELECT DISTINCT department FROM users WHERE role = 'student' AND department IS NOT NULL ORDER BY department")
    departments = [row[0] for row in cur.fetchall()]

    # Get unique graduation years (batches)
    cur.execute("SELECT DISTINCT graduation_year FROM users WHERE role = 'student' AND graduation_year IS NOT NULL ORDER BY graduation_year")
    batches = [row[0] for row in cur.fetchall()]

    conn.close()

    return {
        'departments': departments,
        'batches': batches
    }

@app.route('/logout')
def logout():
    session.clear()
    return redirect('/')

# ---------- RUN APP ----------
if __name__ == '__main__':
    port = int(os.environ.get("PORT", 5000))
    app.run(host='0.0.0.0', port=port, debug=True)
