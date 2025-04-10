from flask import Flask, render_template, request, redirect
import mysql.connector

app = Flask(__name__)

# --- Database Configuration ---
db = mysql.connector.connect(
    host="localhost",
    user="STCDBAdmin",  # Replace with your DB user
    password="12345",  # Replace with your DB password
    database="student_registration"
)
cursor = db.cursor(dictionary=True)

# --- Home Page: Course selection form ---
@app.route("/")
def index():
    cursor.execute("SELECT * FROM courses")
    courses = cursor.fetchall()
    return render_template("index.html", courses=courses)

# --- Register for a Class ---
@app.route("/register", methods=["POST"])
def register():
    name = request.form["name"]
    email = request.form["email"]
    class_id = request.form["class_id"]

    # Create or find student
    cursor.execute("SELECT id FROM students WHERE email = %s", (email,))
    student = cursor.fetchone()
    if not student:
        cursor.execute("INSERT INTO students (name, email) VALUES (%s, %s)", (name, email))
        db.commit()
        student_id = cursor.lastrowid
    else:
        student_id = student["id"]

    # Check capacity
    cursor.execute("SELECT capacity FROM classes WHERE id = %s", (class_id,))
    class_data = cursor.fetchone()
    capacity = class_data["capacity"]

    cursor.execute("SELECT COUNT(*) AS count FROM registrations WHERE class_id = %s", (class_id,))
    registered_count = cursor.fetchone()["count"]

    is_overflow = registered_count >= capacity

    # Register
    cursor.execute("""
        INSERT INTO registrations (student_id, class_id, is_overflow)
        VALUES (%s, %s, %s)
    """, (student_id, class_id, is_overflow))
    db.commit()

    return redirect("/")

# --- Return list of classes for a course (AJAX endpoint) ---
@app.route("/classes/<int:course_id>")
def get_classes(course_id):
    cursor.execute("SELECT * FROM classes WHERE course_id = %s", (course_id,))
    return {"classes": cursor.fetchall()}

# --- Full class list page (with registration toggle) ---
@app.route("/classes")
def class_list():
    email = request.args.get("email")

    student_id = None
    if email:
        cursor.execute("SELECT id FROM students WHERE email = %s", (email,))
        result = cursor.fetchone()
        if result:
            student_id = result["id"]

    # Get all class info
    cursor.execute("""
        SELECT classes.*, courses.name AS course_name
        FROM classes
        JOIN courses ON classes.course_id = courses.id
    """)
    all_classes = cursor.fetchall()

    # Registration count
    cursor.execute("""
        SELECT class_id, COUNT(*) AS registered
        FROM registrations
        GROUP BY class_id
    """)
    reg_map = {row['class_id']: row['registered'] for row in cursor.fetchall()}

    # Check if student is registered
    student_registrations = set()
    if student_id:
        cursor.execute("SELECT class_id FROM registrations WHERE student_id = %s", (student_id,))
        student_registrations = {row["class_id"] for row in cursor.fetchall()}

    # Add calculated fields to class objects
    for c in all_classes:
        c_id = c["id"]
        c["registered"] = reg_map.get(c_id, 0)
        c["remaining"] = max(0, c["capacity"] - c["registered"])
        c["is_registered"] = c_id in student_registrations

    return render_template("class_list.html", classes=all_classes, email=email)

# --- Register or Unregister a student from a class ---
@app.route("/toggle_registration", methods=["POST"])
def toggle_registration():
    email = request.form["email"]
    class_id = int(request.form["class_id"])

    # Find student
    cursor.execute("SELECT id FROM students WHERE email = %s", (email,))
    student = cursor.fetchone()
    if not student:
        return "Student not found", 404
    student_id = student["id"]

    # Check if already registered
    cursor.execute("SELECT id FROM registrations WHERE student_id = %s AND class_id = %s", (student_id, class_id))
    existing = cursor.fetchone()

    if existing:
        # Unregister
        cursor.execute("DELETE FROM registrations WHERE id = %s", (existing["id"],))
    else:
        # Register
        cursor.execute("SELECT capacity FROM classes WHERE id = %s", (class_id,))
        capacity = cursor.fetchone()["capacity"]

        cursor.execute("SELECT COUNT(*) AS count FROM registrations WHERE class_id = %s", (class_id,))
        registered_count = cursor.fetchone()["count"]

        is_overflow = registered_count >= capacity

        cursor.execute("""
            INSERT INTO registrations (student_id, class_id, is_overflow)
            VALUES (%s, %s, %s)
        """, (student_id, class_id, is_overflow))

    db.commit()
    return redirect(f"/classes?email={email}")

# --- Run the Flask app ---
if __name__ == "__main__":
    app.run(debug=True, host="0.0.0.0")
