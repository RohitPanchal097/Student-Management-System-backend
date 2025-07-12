from flask import Flask, request, jsonify, send_file
import sqlite3
import os
from flask_cors import CORS
from reportlab.lib.pagesizes import A4
from reportlab.pdfgen import canvas
import io
import json
import re
from werkzeug.utils import secure_filename
ALLOWED_EXTENSIONS = {'pdf', 'jpg', 'jpeg', 'png'}
def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

app = Flask(__name__)
CORS(app)
DB_PATH = os.path.join(os.path.dirname(__file__), 'student_mgmt.db')

# --- Database Setup ---
def init_db():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Courses table
    c.execute('''CREATE TABLE IF NOT EXISTS courses (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL UNIQUE
    )''')
    # Batches table
    c.execute('''CREATE TABLE IF NOT EXISTS batches (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        course_id INTEGER NOT NULL,
        name TEXT NOT NULL,
        FOREIGN KEY(course_id) REFERENCES courses(id)
    )''')
    # Students table
    c.execute('''CREATE TABLE IF NOT EXISTS students (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        name TEXT NOT NULL,
        father_name TEXT,
        dob TEXT,
        mobile TEXT,
        email TEXT,
        gender TEXT,
        admission_date TEXT,
        year TEXT,
        semester TEXT,
        course_id INTEGER,
        batch_id INTEGER,
        fees_total REAL DEFAULT 0,
        FOREIGN KEY(course_id) REFERENCES courses(id),
        FOREIGN KEY(batch_id) REFERENCES batches(id)
    )''')
    # Add fees_total column if not exists
    c.execute("PRAGMA table_info(students)")
    columns = [row[1] for row in c.fetchall()]
    if 'fees_total' not in columns:
        c.execute('ALTER TABLE students ADD COLUMN fees_total REAL DEFAULT 0')
    # Fees Payments table
    c.execute('''CREATE TABLE IF NOT EXISTS fees_payments (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        amount REAL NOT NULL,
        mode TEXT NOT NULL,
        date TEXT NOT NULL,
        note TEXT,
        FOREIGN KEY(student_id) REFERENCES students(id)
    )''')
    # Exam Forms table
    c.execute('''CREATE TABLE IF NOT EXISTS exam_forms (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        student_id INTEGER NOT NULL,
        exam_date TEXT,
        subjects TEXT,
        created_at TEXT DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(student_id) REFERENCES students(id)
    )''')
    conn.commit()
    conn.close()

init_db()

# --- API Endpoints ---
@app.route('/api/courses', methods=['GET'])
def get_courses():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT id, name FROM courses')
    courses = [{'id': row[0], 'name': row[1]} for row in c.fetchall()]
    conn.close()
    return jsonify(courses)

@app.route('/api/courses', methods=['POST'])
def add_course():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Course name required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('INSERT INTO courses (name) VALUES (?)', (name,))
        conn.commit()
        course_id = c.lastrowid
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Course already exists'}), 400
    conn.close()
    return jsonify({'id': course_id, 'name': name}), 201

@app.route('/api/courses/<int:course_id>', methods=['PUT'])
def update_course(course_id):
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': 'Course name required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    try:
        c.execute('UPDATE courses SET name = ? WHERE id = ?', (name, course_id))
        conn.commit()
        if c.rowcount == 0:
            conn.close()
            return jsonify({'error': 'Course not found'}), 404
    except sqlite3.IntegrityError:
        conn.close()
        return jsonify({'error': 'Course name already exists'}), 400
    conn.close()
    return jsonify({'id': course_id, 'name': name})

@app.route('/api/courses/<int:course_id>', methods=['DELETE'])
def delete_course(course_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Check if course has batches
    c.execute('SELECT COUNT(*) FROM batches WHERE course_id = ?', (course_id,))
    batch_count = c.fetchone()[0]
    if batch_count > 0:
        conn.close()
        return jsonify({'error': f'Cannot delete course: {batch_count} batches are associated with this course'}), 400
    
    # Check if course has students
    c.execute('SELECT COUNT(*) FROM students WHERE course_id = ?', (course_id,))
    student_count = c.fetchone()[0]
    if student_count > 0:
        conn.close()
        return jsonify({'error': f'Cannot delete course: {student_count} students are enrolled in this course'}), 400
    
    c.execute('DELETE FROM courses WHERE id = ?', (course_id,))
    conn.commit()
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Course not found'}), 404
    conn.close()
    return jsonify({'success': True})

@app.route('/api/batches', methods=['GET'])
def get_batches():
    course_id = request.args.get('course_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if course_id:
        c.execute('SELECT id, name, course_id FROM batches WHERE course_id = ?', (course_id,))
    else:
        c.execute('SELECT id, name, course_id FROM batches')
    batches = [{'id': row[0], 'name': row[1], 'course_id': row[2]} for row in c.fetchall()]
    conn.close()
    return jsonify(batches)

@app.route('/api/batches', methods=['POST'])
def add_batch():
    data = request.json
    name = data.get('name')
    course_id = data.get('course_id')
    if not name or not course_id:
        return jsonify({'error': 'Batch name and course_id required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO batches (name, course_id) VALUES (?, ?)', (name, course_id))
    conn.commit()
    batch_id = c.lastrowid
    conn.close()
    return jsonify({'id': batch_id, 'name': name, 'course_id': course_id}), 201

@app.route('/api/batches/<int:batch_id>', methods=['PUT'])
def update_batch(batch_id):
    data = request.json
    name = data.get('name')
    course_id = data.get('course_id')
    if not name or not course_id:
        return jsonify({'error': 'Batch name and course_id required'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('UPDATE batches SET name = ?, course_id = ? WHERE id = ?', (name, course_id, batch_id))
    conn.commit()
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Batch not found'}), 404
    conn.close()
    return jsonify({'id': batch_id, 'name': name, 'course_id': course_id})

@app.route('/api/batches/<int:batch_id>', methods=['DELETE'])
def delete_batch(batch_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Check if batch has students
    c.execute('SELECT COUNT(*) FROM students WHERE batch_id = ?', (batch_id,))
    student_count = c.fetchone()[0]
    if student_count > 0:
        conn.close()
        return jsonify({'error': f'Cannot delete batch: {student_count} students are enrolled in this batch'}), 400
    
    c.execute('DELETE FROM batches WHERE id = ?', (batch_id,))
    conn.commit()
    if c.rowcount == 0:
        conn.close()
        return jsonify({'error': 'Batch not found'}), 404
    conn.close()
    return jsonify({'success': True})

@app.route('/api/students', methods=['POST'])
def add_student():
    data = request.json
    required = ['name', 'father_name', 'dob', 'mobile', 'email', 'gender', 'admission_date', 'year', 'semester', 'course_id', 'batch_id']
    if not all(k in data and data[k] for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO students (name, father_name, dob, mobile, email, gender, admission_date, year, semester, course_id, batch_id)
                 VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)''',
              (data['name'], data['father_name'], data['dob'], data['mobile'], data['email'], data['gender'], data['admission_date'], data['year'], data['semester'], data['course_id'], data['batch_id']))
    conn.commit()
    student_id = c.lastrowid
    conn.close()
    return jsonify({'id': student_id}), 201

@app.route('/api/students', methods=['GET'])
def get_students():
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT s.id, s.name, s.father_name, s.dob, s.mobile, s.email, s.gender, s.admission_date, s.year, s.semester,
                        s.course_id, s.batch_id, c.name as course_name, b.name as batch_name
                 FROM students s
                 LEFT JOIN courses c ON s.course_id = c.id
                 LEFT JOIN batches b ON s.batch_id = b.id
                 ORDER BY s.id DESC''')
    students = [
        {
            'id': row[0],
            'name': row[1],
            'father_name': row[2],
            'dob': row[3],
            'mobile': row[4],
            'email': row[5],
            'gender': row[6],
            'admission_date': row[7],
            'year': row[8],
            'semester': row[9],
            'course_id': row[10],
            'batch_id': row[11],
            'course': row[12],
            'batch': row[13],
        }
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify(students)

@app.route('/api/students/<int:student_id>', methods=['PUT'])
def update_student(student_id):
    data = request.json
    required = ['name', 'father_name', 'dob', 'mobile', 'email', 'gender', 'admission_date', 'year', 'semester', 'course_id', 'batch_id']
    if not all(k in data and data[k] for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''UPDATE students SET name=?, father_name=?, dob=?, mobile=?, email=?, gender=?, admission_date=?, year=?, semester=?, course_id=?, batch_id=? WHERE id=?''',
              (data['name'], data['father_name'], data['dob'], data['mobile'], data['email'], data['gender'], data['admission_date'], data['year'], data['semester'], data['course_id'], data['batch_id'], student_id))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/students/<int:student_id>', methods=['DELETE'])
def delete_student(student_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('DELETE FROM students WHERE id=?', (student_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/exam_forms', methods=['POST'])
def add_exam_form():
    data = request.json
    required = ['student_id', 'exam_date', 'subjects']
    if not all(k in data and data[k] for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    import json
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''INSERT INTO exam_forms (student_id, exam_date, subjects) VALUES (?, ?, ?)''',
              (data['student_id'], data['exam_date'], json.dumps(data['subjects'])))
    conn.commit()
    form_id = c.lastrowid
    conn.close()
    return jsonify({'id': form_id}), 201

@app.route('/api/exam_forms', methods=['GET'])
def get_exam_forms():
    student_id = request.args.get('student_id')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    if student_id:
        c.execute('''SELECT id, student_id, exam_date, subjects, created_at FROM exam_forms WHERE student_id = ? ORDER BY created_at DESC''', (student_id,))
    else:
        c.execute('''SELECT id, student_id, exam_date, subjects, created_at FROM exam_forms ORDER BY created_at DESC''')
    import json
    forms = [
        {
            'id': row[0],
            'student_id': row[1],
            'exam_date': row[2],
            'subjects': json.loads(row[3]),
            'created_at': row[4],
        }
        for row in c.fetchall()
    ]
    conn.close()
    return jsonify(forms)

@app.route('/api/exam_forms/<int:form_id>/pdf', methods=['GET'])
def get_exam_form_pdf(form_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT ef.exam_date, ef.subjects, s.name, s.course_id, s.batch_id, s.year, s.semester, s.id
                 FROM exam_forms ef
                 JOIN students s ON ef.student_id = s.id
                 WHERE ef.id = ?''', (form_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Exam form not found'}), 404
    exam_date, subjects_json, student_name, course_id, batch_id, year, semester, student_id = row
    subjects = json.loads(subjects_json)
    # Get course and batch names
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT name FROM courses WHERE id = ?', (course_id,))
    course_name = c.fetchone()[0] if c.fetchone() else 'Unknown'
    c.execute('SELECT name FROM batches WHERE id = ?', (batch_id,))
    batch_name = c.fetchone()[0] if c.fetchone() else 'Unknown'
    conn.close()
    # Folder structure
    base_dir = os.path.join(os.path.dirname(__file__), 'SMS', course_name, batch_name, year, student_name.replace(' ', '_'))
    os.makedirs(base_dir, exist_ok=True)
    pdf_path = os.path.join(base_dir, f'ExamForm_{exam_date}.pdf')
    # Generate PDF
    buffer = io.BytesIO()
    p = canvas.Canvas(buffer, pagesize=A4)
    p.setFont('Helvetica-Bold', 16)
    p.drawString(100, 800, 'Exam Form')
    p.setFont('Helvetica', 12)
    p.drawString(100, 780, f'Student Name: {student_name}')
    p.drawString(100, 760, f'Course: {course_name}')
    p.drawString(100, 740, f'Batch: {batch_name}')
    p.drawString(100, 720, f'Year: {year}')
    p.drawString(100, 700, f'Semester: {semester}')
    p.drawString(100, 680, f'Exam Date: {exam_date}')
    p.drawString(100, 660, 'Subjects/Papers:')
    y = 640
    for idx, subj in enumerate(subjects, 1):
        p.drawString(120, y, f'{idx}. {subj}')
        y -= 20
    p.showPage()
    p.save()
    buffer.seek(0)
    # Save PDF to disk
    with open(pdf_path, 'wb') as f:
        f.write(buffer.getvalue())
    buffer.seek(0)
    return send_file(buffer, as_attachment=True, download_name=f'ExamForm_{exam_date}.pdf', mimetype='application/pdf')

@app.route('/api/promote_batch', methods=['POST'])
def promote_batch():
    data = request.json
    required = ['from_batch_id', 'from_year', 'from_semester', 'to_batch_id', 'to_year', 'to_semester']
    if not all(k in data and data[k] for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    from_batch_id = data['from_batch_id']
    from_year = data['from_year']
    from_semester = data['from_semester']
    to_batch_id = data['to_batch_id']
    to_year = data['to_year']
    to_semester = data['to_semester']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get students to promote
    c.execute('SELECT id, fees_total FROM students WHERE batch_id=? AND year=? AND semester=?', (from_batch_id, from_year, from_semester))
    students = c.fetchall()
    not_paid = []
    for sid, fees_total in students:
        c.execute('SELECT SUM(amount) FROM fees_payments WHERE student_id=?', (sid,))
        paid = c.fetchone()[0] or 0
        if paid < (fees_total or 0):
            not_paid.append(sid)
    if not_paid:
        return jsonify({'error': f'Cannot promote. Fees not fully paid for students: {not_paid}'}), 400
    # Update students in from_batch_id, from_year, from_semester to new batch/year/semester
    c.execute('''UPDATE students SET batch_id=?, year=?, semester=? WHERE batch_id=? AND year=? AND semester=?''',
              (to_batch_id, to_year, to_semester, from_batch_id, from_year, from_semester))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'promoted': affected})

@app.route('/api/passout_students', methods=['POST'])
def passout_students():
    data = request.json
    required = ['batch_id', 'year', 'semester']
    if not all(k in data and data[k] for k in required):
        return jsonify({'error': 'Missing required fields'}), 400
    batch_id = data['batch_id']
    year = data['year']
    semester = data['semester']
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Delete students in this batch/year/semester
    c.execute('''DELETE FROM students WHERE batch_id=? AND year=? AND semester=?''', (batch_id, year, semester))
    affected = c.rowcount
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'deleted': affected})

@app.route('/api/promote_all', methods=['POST'])
def promote_all():
    # Course duration mapping (can be extended)
    course_durations = {
        'B.A.': 3,
        'B.Sc.': 3,
        'B.Com.': 3,
        'B.Tech.': 4,
    }
    year_order = ['1st Year', '2nd Year', '3rd Year', '4th Year']
    semester_order = [
        '1st Semester', '2nd Semester', '3rd Semester', '4th Semester',
        '5th Semester', '6th Semester', '7th Semester', '8th Semester'
    ]
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    # Get all students with course, year, semester, batch
    c.execute('''SELECT s.id, s.course_id, s.batch_id, s.year, s.semester, c.name as course_name
                 FROM students s
                 LEFT JOIN courses c ON s.course_id = c.id''')
    students = c.fetchall()
    promoted = 0
    passout = 0
    for sid, course_id, batch_id, year, semester, course_name in students:
        duration = course_durations.get(course_name, 3)
        if not year or not course_name:
            continue
        # Find current year index
        try:
            yidx = year_order.index(year)
        except ValueError:
            continue
        # If final year, delete student (passout)
        if yidx + 1 == duration:
            c.execute('DELETE FROM students WHERE id=?', (sid,))
            passout += 1
            continue
        # Else, promote to next year
        next_year = year_order[yidx + 1] if yidx + 1 < len(year_order) else year
        # Promote semester if possible
        semidx = semester_order.index(semester) if semester in semester_order else -1
        next_semester = semester_order[semidx + 1] if semidx != -1 and semidx + 1 < len(semester_order) else semester
        # Batch promotion: find next batch (by name, e.g. 2024-25 -> 2025-26)
        c.execute('SELECT name FROM batches WHERE id=?', (batch_id,))
        batch_name_row = c.fetchone()
        if batch_name_row:
            batch_name = batch_name_row[0]
            # Try to increment batch year (e.g. 2024-25 -> 2025-26)
            match = re.match(r'(\d{4})-(\d{2})', batch_name)
            if match:
                start_year = int(match.group(1))
                end_year = int(match.group(2))
                new_start = start_year + 1
                new_end = (end_year + 1) % 100
                new_batch_name = f"{new_start}-{new_end:02d}"
                # Find batch with this name
                c.execute('SELECT id FROM batches WHERE name=? AND course_id=?', (new_batch_name, course_id))
                new_batch_row = c.fetchone()
                if new_batch_row:
                    new_batch_id = new_batch_row[0]
                else:
                    new_batch_id = batch_id  # fallback: stay in same batch
            else:
                new_batch_id = batch_id
        else:
            new_batch_id = batch_id
        # Update student
        c.execute('''UPDATE students SET year=?, semester=?, batch_id=? WHERE id=?''',
                  (next_year, next_semester, new_batch_id, sid))
        promoted += 1
    conn.commit()
    conn.close()
    return jsonify({'success': True, 'promoted': promoted, 'passout': passout})

@app.route('/api/students/<int:student_id>/upload_document', methods=['POST'])
def upload_student_document(student_id):
    # Expected fields: doc_type (10th_marksheet, 12th_marksheet, photo, signature, aadhar, other), file
    doc_type = request.form.get('doc_type')
    file = request.files.get('file')
    if not doc_type or not file or not allowed_file(file.filename):
        return jsonify({'error': 'Missing or invalid file/doc_type'}), 400
    # Get student info for folder structure
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT s.name, s.year, s.semester, c.name, b.name FROM students s
                 LEFT JOIN courses c ON s.course_id = c.id
                 LEFT JOIN batches b ON s.batch_id = b.id
                 WHERE s.id = ?''', (student_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Student not found'}), 404
    student_name, year, semester, course_name, batch_name = row
    base_dir = os.path.join(os.path.dirname(__file__), 'uploads', str(course_name), str(batch_name), str(year), str(semester), str(student_name).replace(' ', '_'), 'documents')
    os.makedirs(base_dir, exist_ok=True)
    filename = secure_filename(f"{doc_type}_{file.filename}")
    file.save(os.path.join(base_dir, filename))
    return jsonify({'success': True, 'filename': filename})

@app.route('/api/students/<int:student_id>/upload_exam_form', methods=['POST'])
def upload_exam_form(student_id):
    # Expected: file (PDF/JPG/PNG)
    file = request.files.get('file')
    if not file or not allowed_file(file.filename):
        return jsonify({'error': 'Missing or invalid file'}), 400
    # Get student info for folder structure
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT s.name, s.year, s.semester, c.name, b.name FROM students s
                 LEFT JOIN courses c ON s.course_id = c.id
                 LEFT JOIN batches b ON s.batch_id = b.id
                 WHERE s.id = ?''', (student_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({'error': 'Student not found'}), 404
    student_name, year, semester, course_name, batch_name = row
    base_dir = os.path.join(os.path.dirname(__file__), 'uploads', str(course_name), str(batch_name), str(year), str(semester), str(student_name).replace(' ', '_'), 'exam_form')
    os.makedirs(base_dir, exist_ok=True)
    filename = secure_filename(file.filename)
    file.save(os.path.join(base_dir, filename))
    return jsonify({'success': True, 'filename': filename})

@app.route('/api/students/<int:student_id>/exam_form_status', methods=['GET'])
def exam_form_status(student_id):
    import glob
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''SELECT s.name, s.year, s.semester, c.name, b.name FROM students s
                 LEFT JOIN courses c ON s.course_id = c.id
                 LEFT JOIN batches b ON s.batch_id = b.id
                 WHERE s.id = ?''', (student_id,))
    row = c.fetchone()
    conn.close()
    if not row:
        return jsonify({'uploaded': False, 'filenames': []})
    student_name, year, semester, course_name, batch_name = row
    base_dir = os.path.join(os.path.dirname(__file__), 'uploads', str(course_name), str(batch_name), str(year), str(semester), str(student_name).replace(' ', '_'), 'exam_form')
    files = []
    for ext in ['pdf', 'jpg', 'jpeg', 'png']:
        files.extend(glob.glob(os.path.join(base_dir, f'*.{ext}')))
    filenames = [os.path.basename(f) for f in files]
    return jsonify({'uploaded': bool(filenames), 'filenames': filenames})

@app.route('/api/students/<int:student_id>/add_fees_payment', methods=['POST'])
def add_fees_payment(student_id):
    data = request.json
    amount = data.get('amount')
    mode = data.get('mode')
    date = data.get('date')
    note = data.get('note', '')
    if not amount or not mode or not date:
        return jsonify({'error': 'Missing required fields'}), 400
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('INSERT INTO fees_payments (student_id, amount, mode, date, note) VALUES (?, ?, ?, ?, ?)',
              (student_id, amount, mode, date, note))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/api/students/<int:student_id>/fees_history', methods=['GET'])
def fees_history(student_id):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('SELECT amount, mode, date, note FROM fees_payments WHERE student_id = ? ORDER BY date DESC, id DESC', (student_id,))
    history = [
        {'amount': row[0], 'mode': row[1], 'date': row[2], 'note': row[3]} for row in c.fetchall()
    ]
    conn.close()
    return jsonify(history)

@app.route('/api/fees_collection_summary', methods=['GET'])
def fees_collection_summary():
    from_date = request.args.get('from')
    to_date = request.args.get('to')
    mode = request.args.get('mode')
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    query = 'SELECT date, mode, SUM(amount) FROM fees_payments WHERE 1=1'
    params = []
    if from_date:
        query += ' AND date >= ?'
        params.append(from_date)
    if to_date:
        query += ' AND date <= ?'
        params.append(to_date)
    if mode:
        query += ' AND mode = ?'
        params.append(mode)
    query += ' GROUP BY date, mode ORDER BY date DESC'
    c.execute(query, params)
    summary = [
        {'date': row[0], 'mode': row[1], 'total': row[2]} for row in c.fetchall()
    ]
    conn.close()
    return jsonify(summary)

if __name__ == '__main__':
    app.run(debug=True, port=5000) 