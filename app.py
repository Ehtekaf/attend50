import json
import os
from datetime import date
from cs50 import SQL
from flask import Flask, flash, redirect, render_template, request, session
from flask_session import Session
from werkzeug.security import check_password_hash, generate_password_hash

from helpers import apology, login_required, calculate_stats

# Configure application
app = Flask(__name__)

# Configure session to use filesystem (instead of signed cookies)
app.config["SESSION_PERMANENT"] = False
app.config["SESSION_TYPE"] = "filesystem"
Session(app)

# Configure CS50 Library to use SQLite database
db = SQL("sqlite:///attendance.db")


@app.after_request
def after_request(response):
    """Ensure responses aren't cached"""
    response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
    response.headers["Expires"] = 0
    response.headers["Pragma"] = "no-cache"
    return response


@app.route("/")
@login_required
def index():
    """Show attendance dashboard with live statistics, margin calculations, and charts"""
    user_id = session["user_id"]

    # 1. Fetch user's registered courses
    courses_raw = db.execute(
        """
        SELECT id, name, code, target_percentage, starting_held, starting_attended
        FROM courses
        WHERE user_id = ?
        ORDER BY name ASC
        """,
        user_id
    )

    # 2. Fetch logged records aggregate counts grouped by course and status
    counts_raw = db.execute(
        """
        SELECT
            course_id,
            SUM(CASE WHEN status = 'Present' THEN 1 ELSE 0 END) AS logged_present,
            SUM(CASE WHEN status = 'Absent' THEN 1 ELSE 0 END) AS logged_absent
        FROM attendance_records
        WHERE user_id = ?
        GROUP BY course_id
        """,
        user_id
    )

    counts_by_course = {
        row["course_id"]: {
            "present": row["logged_present"] or 0,
            "absent": row["logged_absent"] or 0
        }
        for row in counts_raw
    }

    # 3. Combine baseline stats with logged stats and run through helpers.calculate_stats
    dashboard_data = []
    overall_attended = 0
    overall_held = 0

    # Chart datasets
    chart_labels = []
    chart_percentages = []
    chart_targets = []
    chart_colors = []

    for c in courses_raw:
        cid = c["id"]
        logged_p = counts_by_course.get(cid, {}).get("present", 0)
        logged_a = counts_by_course.get(cid, {}).get("absent", 0)

        total_attended = c["starting_attended"] + logged_p
        total_held = c["starting_held"] + logged_p + logged_a

        overall_attended += total_attended
        overall_held += total_held

        stats = calculate_stats(total_attended, total_held, c["target_percentage"])

        dashboard_data.append({
            "id": cid,
            "name": c["name"],
            "code": c["code"],
            "target": c["target_percentage"],
            "stats": stats
        })

        # Populate chart arrays
        display_label = c["code"] if c["code"] else c["name"]
        chart_labels.append(display_label)
        chart_percentages.append(stats["percentage"])
        chart_targets.append(c["target_percentage"])
        chart_colors.append("#198754" if stats["status"] == "safe" else "#dc3545")

    overall_absent = overall_held - overall_attended
    overall_percentage = round((overall_attended / overall_held * 100), 1) if overall_held > 0 else 100.0

    return render_template(
        "index.html",
        courses=dashboard_data,
        overall_attended=overall_attended,
        overall_held=overall_held,
        overall_absent=overall_absent,
        overall_percentage=overall_percentage,
        today=date.today().strftime("%Y-%m-%d"),
        chart_labels=json.dumps(chart_labels),
        chart_percentages=json.dumps(chart_percentages),
        chart_targets=json.dumps(chart_targets),
        chart_colors=json.dumps(chart_colors)
    )


@app.route("/log", methods=["POST"])
@login_required
def log_attendance():
    """Quick 1-click attendance entry"""
    user_id = session["user_id"]
    course_id = request.form.get("course_id")
    status = request.form.get("status")
    log_date = request.form.get("date", date.today().strftime("%Y-%m-%d"))

    if not course_id or not status:
        return apology("Course and status are required", 400)

    if status not in ["Present", "Absent", "Cancelled"]:
        return apology("Invalid attendance status", 400)

    # Validate that the course belongs to the current user
    course = db.execute("SELECT name FROM courses WHERE id = ? AND user_id = ?", course_id, user_id)
    if not course:
        return apology("Course not found or unauthorized", 404)

    # Insert log record
    db.execute(
        """
        INSERT INTO attendance_records (user_id, course_id, date, status)
        VALUES (?, ?, ?, ?)
        """,
        user_id,
        course_id,
        log_date,
        status
    )

    course_name = course[0]["name"]
    flash(f"Logged '{status}' for {course_name} on {log_date}.")
    return redirect("/")


@app.route("/courses", methods=["GET", "POST"])
@login_required
def courses():
    """Manage enrolled courses"""
    user_id = session["user_id"]

    if request.method == "POST":
        name = request.form.get("name", "").strip()
        code = request.form.get("code", "").strip()
        target = request.form.get("target", "75").strip()
        starting_held = request.form.get("starting_held", "0").strip()
        starting_attended = request.form.get("starting_attended", "0").strip()

        # Input validation
        if not name:
            return apology("Course name is required", 400)

        try:
            target = float(target)
            starting_held = int(starting_held)
            starting_attended = int(starting_attended)
        except ValueError:
            return apology("Invalid numbers provided", 400)

        if not (0 < target <= 100):
            return apology("Target percentage must be between 1 and 100", 400)

        if starting_held < 0 or starting_attended < 0:
            return apology("Class counts cannot be negative", 400)

        if starting_attended > starting_held:
            return apology("Attended classes cannot exceed conducted classes", 400)

        try:
            db.execute(
                """
                INSERT INTO courses (user_id, name, code, target_percentage, starting_held, starting_attended)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                user_id,
                name,
                code if code else None,
                target,
                starting_held,
                starting_attended
            )
            flash(f"Course '{name}' added successfully!")
        except ValueError:
            return apology("A course with this name already exists", 400)

        return redirect("/courses")

    # GET request: fetch all courses for this user
    user_courses = db.execute(
        """
        SELECT id, name, code, target_percentage, starting_held, starting_attended
        FROM courses
        WHERE user_id = ?
        ORDER BY name ASC
        """,
        user_id
    )

    return render_template("courses.html", courses=user_courses)


@app.route("/courses/delete", methods=["POST"])
@login_required
def delete_course():
    """Delete a course and all associated attendance logs"""
    user_id = session["user_id"]
    course_id = request.form.get("course_id")

    if not course_id:
        return apology("Invalid course selection", 400)

    # Verify ownership before deletion
    course = db.execute(
        "SELECT id, name FROM courses WHERE id = ? AND user_id = ?",
        course_id,
        user_id
    )

    if not course:
        return apology("Course not found or unauthorized", 404)

    # Delete records and course
    db.execute("DELETE FROM attendance_records WHERE course_id = ? AND user_id = ?", course_id, user_id)
    db.execute("DELETE FROM courses WHERE id = ? AND user_id = ?", course_id, user_id)

    flash(f"Course '{course[0]['name']}' deleted.")
    return redirect("/courses")


@app.route("/history")
@login_required
def history():
    """Display past attendance logs with optional course and status filters"""
    user_id = session["user_id"]

    selected_course = request.args.get("course_id", "").strip()
    selected_status = request.args.get("status", "").strip()

    user_courses = db.execute(
        "SELECT id, name, code FROM courses WHERE user_id = ? ORDER BY name ASC",
        user_id
    )

    query = """
        SELECT
            ar.id,
            ar.date,
            ar.status,
            ar.note,
            c.id AS course_id,
            c.name AS course_name,
            c.code AS course_code
        FROM attendance_records ar
        JOIN courses c ON ar.course_id = c.id
        WHERE ar.user_id = ?
    """
    params = [user_id]

    if selected_course and selected_course.isdigit():
        query += " AND ar.course_id = ?"
        params.append(int(selected_course))

    if selected_status in ["Present", "Absent", "Cancelled"]:
        query += " AND ar.status = ?"
        params.append(selected_status)

    query += " ORDER BY ar.date DESC, ar.id DESC"

    records = db.execute(query, *params)

    return render_template(
        "history.html",
        records=records,
        courses=user_courses,
        selected_course=selected_course,
        selected_status=selected_status
    )


@app.route("/history/delete", methods=["POST"])
@login_required
def delete_log():
    """Delete a misclicked attendance log entry"""
    user_id = session["user_id"]
    record_id = request.form.get("record_id")

    if not record_id or not record_id.isdigit():
        return apology("Invalid record identifier", 400)

    record = db.execute(
        """
        SELECT ar.id, ar.date, ar.status, c.name AS course_name
        FROM attendance_records ar
        JOIN courses c ON ar.course_id = c.id
        WHERE ar.id = ? AND ar.user_id = ?
        """,
        int(record_id),
        user_id
    )

    if not record:
        return apology("Record not found or unauthorized", 404)

    db.execute("DELETE FROM attendance_records WHERE id = ? AND user_id = ?", int(record_id), user_id)

    log_entry = record[0]
    flash(f"Removed '{log_entry['status']}' entry for {log_entry['course_name']} on {log_entry['date']}.")

    redirect_course = request.form.get("current_course", "")
    redirect_status = request.form.get("current_status", "")
    params = []
    if redirect_course:
        params.append(f"course_id={redirect_course}")
    if redirect_status:
        params.append(f"status={redirect_status}")

    redirect_url = "/history"
    if params:
        redirect_url += "?" + "&".join(params)

    return redirect(redirect_url)


@app.route("/register", methods=["GET", "POST"])
def register():
    """Register user"""
    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password")
        confirmation = request.form.get("confirmation")

        if not username:
            return apology("Must provide username", 400)
        if not password:
            return apology("Must provide password", 400)
        if password != confirmation:
            return apology("Passwords do not match", 400)

        hash_val = generate_password_hash(password)
        try:
            user_id = db.execute(
                "INSERT INTO users (username, hash) VALUES (?, ?)",
                username,
                hash_val
            )
        except ValueError:
            return apology("Username already exists", 400)

        session["user_id"] = user_id
        flash("Registered successfully!")
        return redirect("/")

    return render_template("register.html")


@app.route("/login", methods=["GET", "POST"])
def login():
    """Log user in"""
    session.clear()

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        password = request.form.get("password")

        if not username:
            return apology("Must provide username", 403)
        if not password:
            return apology("Must provide password", 403)

        rows = db.execute("SELECT * FROM users WHERE username = ?", username)

        if len(rows) != 1 or not check_password_hash(rows[0]["hash"], password):
            return apology("Invalid username and/or password", 403)

        session["user_id"] = rows[0]["id"]
        return redirect("/")

    return render_template("login.html")


@app.route("/logout")
def logout():
    """Log user out"""
    session.clear()
    return redirect("/login")


if __name__ == "__main__":
    app.run(debug=True)
