import os
import datetime
from flask import Flask, request, jsonify, send_from_directory
from flask_cors import CORS
from dotenv import load_dotenv

from database import init_default_data, quiz_attempts_col
from auth import admin_required, authenticate_admin, verify_token
import quiz

load_dotenv()

# Path to frontend directory for optional local serving
FRONTEND_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "frontend"))

app = Flask(__name__, static_folder=FRONTEND_DIR)
app.secret_key = os.getenv("SECRET_KEY", "super-quiz-management-system-secret-key-2026")

# Enable CORS for all REST API endpoints
CORS(app, resources={r"/api/*": {"origins": "*"}}, supports_credentials=True)

# Initialize seed admin, settings and questions
try:
    init_default_data()
except Exception as e:
    print(f"[!] Init data warning: {e}")


# ==========================================
# PUBLIC / HEALTH ROUTES
# ==========================================

@app.route("/api/health", methods=["GET"])
def health_check():
    return jsonify({
        "status": "online",
        "service": "Online Quiz Management API",
        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat()
    })

@app.route("/api/quiz/settings", methods=["GET"])
def get_public_settings():
    """Returns general quiz status and instructions for students."""
    try:
        settings = quiz.get_settings()
        qs = quiz.get_sanitized_questions_for_student()
        total_marks = sum(int(q.get("marks", 1)) for q in qs)
        sanitized = {
            "quiz_title": settings.get("quiz_title", "Online Quiz"),
            "quiz_status": settings.get("quiz_status", "active"),
            "is_enabled": settings.get("is_enabled", True),
            "total_duration": settings.get("total_duration", 15),
            "instructions": settings.get("instructions", ""),
            "pass_percentage": settings.get("pass_percentage", 50),
            "total_questions": len(qs),
            "total_marks": total_marks
        }
        return jsonify({"status": "success", "data": sanitized})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# ADMIN AUTHENTICATION
# ==========================================

@app.route("/api/admin/login", methods=["POST"])
def admin_login():
    data = request.get_json() or {}
    username = data.get("username", "")
    password = data.get("password", "")

    if not username or not password:
        return jsonify({"status": "error", "message": "Username and password are required"}), 400

    client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
    auth_result = authenticate_admin(username, password, client_ip=client_ip)
    
    if auth_result and "error" in auth_result:
        return jsonify({"status": "error", "message": auth_result["error"]}), 429
        
    if not auth_result:
        return jsonify({"status": "error", "message": "Invalid admin username or password"}), 401

    return jsonify({
        "status": "success",
        "message": "Login successful",
        "token": auth_result["token"],
        "username": auth_result["username"]
    })

@app.route("/api/admin/verify", methods=["GET"])
@admin_required
def admin_verify():
    return jsonify({"status": "success", "message": "Token is valid"})


# ==========================================
# ADMIN DASHBOARD & QUESTION MANAGEMENT
# ==========================================

@app.route("/api/admin/dashboard", methods=["GET"])
@admin_required
def admin_dashboard():
    try:
        stats = quiz.get_admin_dashboard_stats()
        return jsonify({"status": "success", "data": stats})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/questions", methods=["GET"])
@admin_required
def admin_get_questions():
    try:
        questions = quiz.get_all_questions_admin()
        return jsonify({"status": "success", "data": questions})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/questions", methods=["POST"])
@admin_required
def admin_add_question():
    try:
        data = request.get_json() or {}
        new_q = quiz.add_question(data)
        return jsonify({"status": "success", "message": "Question added successfully", "data": new_q}), 201
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/questions/<question_id>", methods=["PUT"])
@admin_required
def admin_update_question(question_id):
    try:
        data = request.get_json() or {}
        updated_q = quiz.update_question(question_id, data)
        if not updated_q:
            return jsonify({"status": "error", "message": "Question not found"}), 404
        return jsonify({"status": "success", "message": "Question updated successfully", "data": updated_q})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/questions/<question_id>", methods=["DELETE"])
@admin_required
def admin_delete_question(question_id):
    try:
        success = quiz.delete_question(question_id)
        if not success:
            return jsonify({"status": "error", "message": "Question not found or already deleted"}), 404
        return jsonify({"status": "success", "message": "Question deleted successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# ADMIN QUIZ SETTINGS
# ==========================================

@app.route("/api/admin/settings", methods=["GET"])
@admin_required
def admin_get_settings():
    try:
        settings = quiz.get_settings()
        return jsonify({"status": "success", "data": settings})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/settings", methods=["POST"])
@admin_required
def admin_update_settings():
    try:
        data = request.get_json() or {}
        updated = quiz.update_settings(data)
        return jsonify({"status": "success", "message": "Quiz settings updated successfully", "data": updated})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# ADMIN STUDENT RESULTS
# ==========================================

@app.route("/api/admin/results", methods=["GET"])
@admin_required
def admin_get_results():
    try:
        results = quiz.get_all_results_admin()
        return jsonify({"status": "success", "data": results})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/students", methods=["GET"])
@admin_required
def admin_get_students():
    """Returns all registered students with their latest quiz attempt status."""
    try:
        students = quiz.get_all_students_admin()
        return jsonify({"status": "success", "data": students})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/results/<attempt_id>", methods=["GET"])
@admin_required
def admin_get_result_detail(attempt_id):
    try:
        result = quiz.get_individual_result_detail(attempt_id)
        if not result:
            return jsonify({"status": "error", "message": "Result record not found"}), 404
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/results/<attempt_id>", methods=["DELETE"])
@admin_required
def admin_delete_result(attempt_id):
    try:
        res = quiz_attempts_col.delete_one({"_id": str(attempt_id).strip()})
        if getattr(res, "deleted_count", 0) == 0:
            return jsonify({"status": "error", "message": "Attempt not found"}), 404
        return jsonify({"status": "success", "message": "Result record removed successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# STUDENT QUIZ INTERACTION (PUBLIC / PROTECTED LOGIC)
# ==========================================

@app.route("/api/student/login", methods=["POST"])
def student_login():
    """Validates student credentials and checks existing attempt."""
    try:
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        reg_no = data.get("register_number", "").strip().upper()

        if not name or not reg_no:
            return jsonify({"status": "error", "message": "Please enter both Full Name and Register Number"}), 400

        # Check quiz status
        settings = quiz.get_settings()
        if settings.get("quiz_status") != "active" or not settings.get("is_enabled", True):
            return jsonify({
                "status": "error",
                "message": "The quiz is currently not active. Please check back later."
            }), 403

        # Check if already submitted
        existing = quiz.get_student_attempt(reg_no)
        if existing and existing.get("status") in ["completed", "auto_submitted"]:
            return jsonify({
                "status": "already_submitted",
                "message": f"Student with Register Number {reg_no} has already completed this quiz.",
                "attempt_id": str(existing.get("_id"))
            }), 409

        student = quiz.register_student(name, reg_no)
        return jsonify({
            "status": "success",
            "message": "Student validated",
            "student": student,
            "has_in_progress": (existing and existing.get("status") == "in_progress")
        })
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/quiz/start", methods=["POST"])
def quiz_start():
    """Initializes or resumes quiz attempt and sends sanitized questions."""
    try:
        data = request.get_json() or {}
        name = data.get("name", "").strip()
        reg_no = data.get("register_number", "").strip().upper()

        if not name or not reg_no:
            return jsonify({"status": "error", "message": "Name and Register Number are required"}), 400

        client_ip = request.headers.get("X-Forwarded-For", request.remote_addr or "127.0.0.1").split(",")[0].strip()
        attempt, questions, settings = quiz.start_quiz_attempt(name, reg_no, client_ip=client_ip)

        return jsonify({
            "status": "success",
            "attempt": attempt,
            "questions": questions,     # SANITIZED: No correct_answer!
            "settings": {
                "total_duration": settings.get("total_duration", 15),
                "quiz_title": settings.get("quiz_title", "Online Quiz"),
                "server_remaining_seconds": attempt.get("server_remaining_seconds")
            }
        })
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/quiz/activity-log", methods=["POST"])
def quiz_activity_log():
    """Records student browser anti-cheat activities in MongoDB."""
    try:
        data = request.get_json() or {}
        attempt_id = data.get("attempt_id")
        event_type = data.get("event_type", "UNKNOWN")
        event_desc = data.get("event_description", "")
        event_count = data.get("event_count", 1)

        if not attempt_id:
            return jsonify({"status": "error", "message": "Missing attempt_id"}), 400

        success = quiz.log_student_activity(attempt_id, event_type, event_desc, event_count)
        if not success:
            return jsonify({"status": "error", "message": "Invalid attempt session"}), 404

        return jsonify({"status": "success", "message": "Activity logged"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/quiz/heartbeat", methods=["POST"])
def quiz_heartbeat():
    """Periodic student heartbeat to detect active participation and termination."""
    try:
        data = request.get_json() or {}
        attempt_id = data.get("attempt_id")
        session_token = data.get("session_token")

        if not attempt_id:
            return jsonify({"status": "error", "message": "Missing attempt_id"}), 400

        result = quiz.process_heartbeat(attempt_id, session_token)
        return jsonify({"status": "success", "data": result})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/live-monitoring", methods=["GET"])
@admin_required
def admin_live_monitoring():
    """Live student monitoring table for administrator."""
    try:
        students = quiz.get_live_monitoring_students()
        return jsonify({"status": "success", "data": students})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/activity-logs/<attempt_id>", methods=["GET"])
@admin_required
def admin_activity_logs(attempt_id):
    """Retrieves full suspicious activity timeline for a specific student."""
    try:
        logs = quiz.get_student_activity_logs(attempt_id)
        return jsonify({"status": "success", "data": logs})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/admin/sessions/<attempt_id>/terminate", methods=["POST"])
@admin_required
def admin_terminate_session(attempt_id):
    """Terminates an ongoing student examination session."""
    try:
        success = quiz.terminate_student_session(attempt_id)
        if not success:
            return jsonify({"status": "error", "message": "Session not found"}), 404
        return jsonify({"status": "success", "message": "Student session terminated successfully"})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/quiz/save-answer", methods=["POST"])
def quiz_save_answer():
    """Autosaves a selected answer."""
    try:
        data = request.get_json() or {}
        attempt_id = data.get("attempt_id")
        question_id = data.get("question_id")
        selected_option = data.get("selected_option")

        if not attempt_id or not question_id:
            return jsonify({"status": "error", "message": "Missing attempt_id or question_id"}), 400

        quiz.save_student_answer(attempt_id, question_id, selected_option)
        return jsonify({"status": "success", "message": "Answer saved"})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/quiz/submit", methods=["POST"])
def quiz_submit():
    """Finalizes quiz, calculates scores securely on backend."""
    try:
        data = request.get_json() or {}
        attempt_id = data.get("attempt_id")
        is_auto_submit = bool(data.get("is_auto_submit", False))

        if not attempt_id:
            return jsonify({"status": "error", "message": "Missing attempt_id"}), 400

        evaluated = quiz.submit_quiz_attempt(attempt_id, is_auto_submit=is_auto_submit)
        
        # Build clean summary for student
        summary = {
            "attempt_id": evaluated["_id"],
            "student_name": evaluated.get("student_name"),
            "register_number": evaluated.get("register_number"),
            "total_questions": evaluated.get("total_questions"),
            "correct_answers": evaluated.get("correct_count"),
            "wrong_answers": evaluated.get("wrong_count"),
            "unanswered_questions": evaluated.get("unanswered_count"),
            "total_marks": evaluated.get("total_marks"),
            "score": evaluated.get("score"),
            "percentage": evaluated.get("percentage"),
            "status": evaluated.get("status"),
            "submission_time": evaluated.get("submission_time")
        }
        return jsonify({"status": "success", "message": "Quiz submitted successfully", "data": summary})
    except ValueError as e:
        return jsonify({"status": "error", "message": str(e)}), 400
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500

@app.route("/api/quiz/result/<attempt_id>", methods=["GET"])
def quiz_get_result(attempt_id):
    """Retrieves student result summary."""
    try:
        attempt = quiz.get_individual_result_detail(attempt_id)
        if not attempt:
            return jsonify({"status": "error", "message": "Result not found"}), 404

        summary = {
            "attempt_id": attempt["_id"],
            "student_name": attempt.get("student_name"),
            "register_number": attempt.get("register_number"),
            "total_questions": attempt.get("total_questions"),
            "correct_answers": attempt.get("correct_count"),
            "wrong_answers": attempt.get("wrong_count"),
            "unanswered_questions": attempt.get("unanswered_count"),
            "total_marks": attempt.get("total_marks"),
            "score": attempt.get("score"),
            "percentage": attempt.get("percentage"),
            "status": attempt.get("status"),
            "submission_time": attempt.get("submission_time")
        }
        return jsonify({"status": "success", "data": summary})
    except Exception as e:
        return jsonify({"status": "error", "message": str(e)}), 500


# ==========================================
# STATIC FRONTEND SERVING (FOR LOCAL ALL-IN-ONE CONVENIENCE)
# ==========================================

@app.route("/", defaults={"path": "index.html"})
@app.route("/<path:path>")
def serve_frontend(path):
    if os.path.exists(os.path.join(FRONTEND_DIR, path)):
        return send_from_directory(FRONTEND_DIR, path)
    # Check if html exists with that name
    if os.path.exists(os.path.join(FRONTEND_DIR, f"{path}.html")):
        return send_from_directory(FRONTEND_DIR, f"{path}.html")
    # Default to index.html
    return send_from_directory(FRONTEND_DIR, "index.html")


if __name__ == "__main__":
    port = int(os.getenv("PORT", 5000))
    print(f"\n=======================================================")
    print(f"  Online Quiz Management System Backend Started")
    print(f"  Local URL: http://127.0.0.1:{port}")
    print(f"  Admin Credentials: Username: Admin | Password: Admin@01")
    print(f"=======================================================\n")
    app.run(host="0.0.0.0", port=port, debug=False)
