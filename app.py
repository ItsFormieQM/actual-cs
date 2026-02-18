from flask import Flask, render_template, request, redirect, url_for
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from flask import send_file
import os
import shutil
import io
import zipfile

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///students.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)

# -------------------- MODELS --------------------
class Student(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(100), nullable=False)
    lrn = db.Column(db.String(20), nullable=True)
    nickname = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.now)
    grades = db.relationship("Grade", backref="student", cascade="all, delete-orphan")

class Grade(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    student_id = db.Column(db.Integer, db.ForeignKey("student.id"))
    subject = db.Column(db.String(50), nullable=False)
    q1 = db.Column(db.Float, default=5.0)
    q2 = db.Column(db.Float, default=5.0)
    q3 = db.Column(db.Float, default=5.0)
    q4 = db.Column(db.Float, default=5.0)

    def average(self):
        return round((self.q1 + self.q2 + self.q3 + self.q4) / 4, 2)

# -------------------- ANALYTICS --------------------
def compute_student_stats(student):
    highest = {"subjects": [], "score": -1}
    lowest = {"subjects": [], "score": 101}
    total = 0
    count = 0

    for g in student.grades:
        avg = g.average()
        total += avg
        count += 1

        # Highest
        if avg > highest["score"]:
            highest["score"] = avg
            highest["subjects"] = [g.subject]
        elif avg == highest["score"]:
            highest["subjects"].append(g.subject)

        # Lowest
        if avg < lowest["score"]:
            lowest["score"] = avg
            lowest["subjects"] = [g.subject]
        elif avg == lowest["score"]:
            lowest["subjects"].append(g.subject)

    average = round(total / count, 2) if count else 0
    return highest, lowest, average

def grade_status(gwa):
    if gwa == 1.0:
        return "Highest DL"
    elif 1.0 < gwa <= 1.5:
        return "DL"
    elif 1.5 < gwa <= 2.5:
        return "Normal"
    elif 2.5 < gwa <= 2.75:
        return "Probationary"
    elif 2.75 < gwa <= 3.0:
        return "Student removed from the system"
    else:
        return "Student did not take the subject"
    
def compute_student_stats(student):
    highest = {"subjects": [], "score": -1}
    lowest = {"subjects": [], "score": 101}
    total = 0
    count = 0

    # Flag to check if any quarter has 5
    any_five = False

    for g in student.grades:
        quarters = [g.q1, g.q2, g.q3, g.q4]

        # Check if any quarter is 5
        if 5.0 in quarters:
            any_five = True

        avg = round(sum(quarters) / 4, 2)
        total += avg
        count += 1

        # Highest
        if avg > highest["score"]:
            highest["score"] = avg
            highest["subjects"] = [g.subject]
        elif avg == highest["score"]:
            highest["subjects"].append(g.subject)

        # Lowest
        if avg < lowest["score"]:
            lowest["score"] = avg
            lowest["subjects"] = [g.subject]
        elif avg == lowest["score"]:
            lowest["subjects"].append(g.subject)

    # Calculate average
    average = round(total / count, 2) if count else 0

    # Apply the special rule: if any quarter is 5, overall average = 5
    if any_five:
        average = 5.0

    return highest, lowest, average

# -------------------- ROUTES --------------------


@app.route("/download_source")
def download_source():
    project_folder = os.path.abspath(os.path.dirname(__file__))

    # Create an in-memory bytes buffer
    memory_file = io.BytesIO()

    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        # Walk through project folder
        for foldername, subfolders, filenames in os.walk(project_folder):
            for filename in filenames:
                # Skip the temporary ZIP itself if exists
                if filename.endswith("student_tracker_sourceCode.zip"):
                    continue

                # Full path
                file_path = os.path.join(foldername, filename)
                # Archive name relative to project folder
                arcname = os.path.relpath(file_path, project_folder)
                zipf.write(file_path, arcname)

    memory_file.seek(0)

    return send_file(
        memory_file,
        as_attachment=True,
        download_name="student_tracker_sourceCode.zip",
        mimetype='application/zip'
    )

@app.route("/")
def index():
    subjects = sorted({g.subject for g in Grade.query.all()})
    selected_subject = request.args.get("subject", "")

    if selected_subject:
        # Get all grades for that subject
        grades = Grade.query.filter_by(subject=selected_subject).all()
        # Extract unique students who have this grade
        students = sorted({g.student for g in grades}, key=lambda s: s.name)
        # Pass the grades separately so we can display only that subject
        grades_dict = {g.student.id: g for g in grades}
    else:
        students = Student.query.all()
        grades_dict = {}  # empty when showing all subjects

    return render_template(
        "index.html",
        students=students,
        subjects=subjects,
        selected_subject=selected_subject,
        compute_student_stats=compute_student_stats,
        grade_status=grade_status,
        grades_dict=grades_dict
    )

@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    subjects = ["Math 2", "Math 3", "ES", "SocSci", "English", "Filipino",
                "PE", "AdTech", "Physics", "Health", "Biology", "CS2"]
    if request.method == "POST":
        name = request.form.get("name")
        lrn = request.form.get("lrn")
        nickname = request.form.get("nickname")
        if not name:
            return "Name is required", 400

        student = Student(name=name, lrn=lrn, nickname=nickname)
        db.session.add(student)
        db.session.commit()

        for subj in subjects:
            try:
                q1 = float(request.form.get(f"{subj}_q1", 5))
                q2 = float(request.form.get(f"{subj}_q2", 5))
                q3 = float(request.form.get(f"{subj}_q3", 5))
                q4 = float(request.form.get(f"{subj}_q4", 5))
            except ValueError:
                q1 = q2 = q3 = q4 = 5
            # Clamp between 1-5 and 2 decimals
            q1 = round(min(max(q1, 1.0), 5.0), 2)
            q2 = round(min(max(q2, 1.0), 5.0), 2)
            q3 = round(min(max(q3, 1.0), 5.0), 2)
            q4 = round(min(max(q4, 1.0), 5.0), 2)
            grade = Grade(student_id=student.id, subject=subj, q1=q1, q2=q2, q3=q3, q4=q4)
            db.session.add(grade)

        db.session.commit()
        return redirect(url_for("index"))

    return render_template("add_student.html", subjects=subjects)

@app.route("/view/<int:student_id>")
def view_student(student_id):
    student = Student.query.get_or_404(student_id)
    subjects = ["Math 2", "Math 3", "ES", "SocSci", "English", "Filipino",
                "PE", "AdTech", "Physics", "Health", "Biology", "CS2"]
    return render_template("view_student.html", student=student, subjects=subjects)


@app.route("/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    student = Student.query.get_or_404(student_id)
    subjects = ["Math 2", "Math 3", "ES", "SocSci", "English", "Filipino",
                "PE", "AdTech", "Physics", "Health", "Biology", "CS2"]

    if request.method == "POST":
        student.name = request.form.get("name")
        student.lrn = request.form.get("lrn")
        student.nickname = request.form.get("nickname")
        db.session.commit()

        # Update grades
        for subj in subjects:
            grade = next((g for g in student.grades if g.subject == subj), None)
            if grade:
                try:
                    grade.q1 = round(float(request.form.get(f"{subj}_q1", 5)), 2)
                    grade.q2 = round(float(request.form.get(f"{subj}_q2", 5)), 2)
                    grade.q3 = round(float(request.form.get(f"{subj}_q3", 5)), 2)
                    grade.q4 = round(float(request.form.get(f"{subj}_q4", 5)), 2)
                except ValueError:
                    grade.q1 = grade.q2 = grade.q3 = grade.q4 = 5
        db.session.commit()
        return redirect(url_for("index"))

    return render_template("add_student.html", student=student, subjects=subjects)

@app.route("/delete_student/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    student = Student.query.get_or_404(student_id)
    db.session.delete(student)
    db.session.commit()
    return redirect(url_for("index"))

# -------------------- MAIN --------------------
if __name__ == "__main__":
    with app.app_context():
        db.create_all()
    app.run(debug=True)
