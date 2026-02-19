from flask import Flask, render_template, request, redirect, url_for, send_file, json
import os
import io
import zipfile

app = Flask(__name__)

students = {}
next_student_id = 1

subjects = ["Math 2", "Math 3", "ES", "SocSci", "English", "Filipino",
            "PE", "AdTech", "Physics", "Health", "Biology", "CS2"]

def compute_student_stats(student):
    highest = {"subjects": [], "score": -1}
    lowest = {"subjects": [], "score": 101}
    total = 0
    count = 0
    any_five = False

    for subj, grades in student["grades"].items():
        avg = round(sum(grades) / 4, 2)
        total += avg
        count += 1
        if 5.0 in grades:
            any_five = True

        if avg > highest["score"]:
            highest["score"] = avg
            highest["subjects"] = [subj]
        elif avg == highest["score"]:
            highest["subjects"].append(subj)

        if avg < lowest["score"]:
            lowest["score"] = avg
            lowest["subjects"] = [subj]
        elif avg == lowest["score"]:
            lowest["subjects"].append(subj)

    average = round(total / count, 2) if count else 0
    if any_five:
        average = 5.0
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

@app.route("/download_source")
def download_source():
    project_folder = os.path.abspath(os.path.dirname(__file__))
    memory_file = io.BytesIO()
    with zipfile.ZipFile(memory_file, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for foldername, subfolders, filenames in os.walk(project_folder):
            for filename in filenames:
                if filename.endswith("student_tracker_sourceCode.zip"):
                    continue
                file_path = os.path.join(foldername, filename)
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
    selected_subject = request.args.get("subject", "")
    if selected_subject:
        filtered_students = [s for s in students.values() if selected_subject in s["grades"]]
    else:
        filtered_students = list(students.values())

    return render_template(
        "index.html",
        students=filtered_students,
        subjects=subjects,
        selected_subject=selected_subject,
        compute_student_stats=compute_student_stats,
        grade_status=grade_status
    )

@app.route("/add_student", methods=["GET", "POST"])
def add_student():
    global next_student_id
    if request.method == "POST":
        name = request.form.get("name")
        lrn = request.form.get("lrn")
        nickname = request.form.get("nickname")
        if not name:
            return "Your name is required", 400

        grades_dict = {}
        for subj in subjects:
            try:
                q1 = round(float(request.form.get(f"{subj}_q1", 5)), 2)
                q2 = round(float(request.form.get(f"{subj}_q2", 5)), 2)
                q3 = round(float(request.form.get(f"{subj}_q3", 5)), 2)
                q4 = round(float(request.form.get(f"{subj}_q4", 5)), 2)
            except ValueError:
                q1 = q2 = q3 = q4 = 5.0
            grades_dict[subj] = [q1, q2, q3, q4]

        students[next_student_id] = {
            "id": next_student_id,
            "name": name,
            "lrn": lrn,
            "nickname": nickname,
            "grades": grades_dict
        }
        next_student_id += 1
        return redirect(url_for("index"))

    return render_template("add_student.html", subjects=subjects)

@app.route("/view/<int:student_id>")
def view_student(student_id):
    student = students.get(student_id)
    if not student:
        return "Student not found", 404

    student_grades = student.get("grades", {})

    return render_template(
        "view_student.html",
        student=student,   
        subjects=subjects,
        compute_student_stats=compute_student_stats,
        grade_status=grade_status
    )

@app.route("/edit/<int:student_id>", methods=["GET", "POST"])
def edit_student(student_id):
    student = students.get(student_id)
    if not student:
        return "Student not found", 404

    if request.method == "POST":
        student["name"] = request.form.get("name")
        student["lrn"] = request.form.get("lrn")
        student["nickname"] = request.form.get("nickname")

        for subj in subjects:
            try:
                q1 = round(float(request.form.get(f"{subj}_q1", 5)), 2)
                q2 = round(float(request.form.get(f"{subj}_q2", 5)), 2)
                q3 = round(float(request.form.get(f"{subj}_q3", 5)), 2)
                q4 = round(float(request.form.get(f"{subj}_q4", 5)), 2)
            except ValueError:
                q1 = q2 = q3 = q4 = 5.0
            student["grades"][subj] = [q1, q2, q3, q4]

        return redirect(url_for("index"))

    return render_template("add_student.html", student=student, subjects=subjects)

@app.route("/delete_student/<int:student_id>", methods=["POST"])
def delete_student(student_id):
    if student_id in students:
        del students[student_id]
    return redirect(url_for("index"))

@app.route("/export_student/<int:student_id>") # its so i dont have to keep putting entries lol
def export_student(student_id):
    student = students.get(student_id)
    if not student:
        return "Student not found", 404

    student_json = json.dumps(student, indent=4)

    memory_file = io.BytesIO()
    memory_file.write(student_json.encode('utf-8'))
    memory_file.seek(0)

    return send_file(
        memory_file,
        as_attachment=True,
        download_name=f"{student['name'].replace(' ', '_')}_grades.json",
        mimetype='application/json'
    )

@app.route("/import_student", methods=["POST"])
def import_student():
    global next_student_id
    file = request.files.get("student_file")
    if not file:
        return "No file uploaded", 400

    try:
        data = json.load(file)
    except json.JSONDecodeError:
        return "Invalid JSON file", 400

    if "name" not in data or "grades" not in data:
        return "Invalid student file", 400

    data["id"] = next_student_id
    students[next_student_id] = data
    next_student_id += 1

    return redirect(url_for("index"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
