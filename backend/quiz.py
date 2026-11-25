import datetime
import uuid
from database import (
    questions_col,
    students_col,
    quiz_attempts_col,
    quiz_settings_col,
    quiz_activity_logs_col
)

def get_utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def get_all_questions_admin():
    """Returns all questions with correct answers for admin view."""
    cursor = questions_col.find({})
    results = []
    for doc in cursor:
        doc["_id"] = str(doc.get("_id"))
        results.append(doc)
    return results

def add_question(data):
    """Adds a new question."""
    question_text = str(data.get("question_text", "")).strip()
    options = data.get("options", {})
    correct_answer = str(data.get("correct_answer", "")).strip().upper()
    marks = int(data.get("marks", 1))
    time_limit = int(data.get("time_limit", 30))

    if not question_text:
        raise ValueError("Question text is required")
    if not isinstance(options, dict) or not all(k in options for k in ["A", "B", "C", "D"]):
        raise ValueError("All 4 options (A, B, C, D) must be provided")
    if correct_answer not in ["A", "B", "C", "D"]:
        raise ValueError("Correct answer must be one of A, B, C, or D")
    if marks <= 0:
        raise ValueError("Marks must be greater than 0")
    if time_limit < 5:
        raise ValueError("Question time limit must be at least 5 seconds")

    doc = {
        "question_text": question_text,
        "options": {
            "A": str(options.get("A", "")).strip(),
            "B": str(options.get("B", "")).strip(),
            "C": str(options.get("C", "")).strip(),
            "D": str(options.get("D", "")).strip()
        },
        "correct_answer": correct_answer,
        "marks": marks,
        "time_limit": time_limit,
        "created_at": get_utc_now_iso(),
        "updated_at": get_utc_now_iso()
    }
    res = questions_col.insert_one(doc)
    doc["_id"] = str(getattr(res, "inserted_id", doc.get("_id")))
    return doc

def update_question(question_id, data):
    """Updates an existing question."""
    q_id_str = str(question_id).strip()
    existing = questions_col.find_one({"_id": q_id_str})
    if not existing:
        return None

    update_fields = {}
    if "question_text" in data:
        update_fields["question_text"] = str(data["question_text"]).strip()
    if "options" in data:
        opts = data["options"]
        update_fields["options"] = {
            "A": str(opts.get("A", "")).strip(),
            "B": str(opts.get("B", "")).strip(),
            "C": str(opts.get("C", "")).strip(),
            "D": str(opts.get("D", "")).strip()
        }
    if "correct_answer" in data:
        update_fields["correct_answer"] = str(data["correct_answer"]).strip().upper()
    if "marks" in data:
        update_fields["marks"] = int(data["marks"])
    if "time_limit" in data:
        update_fields["time_limit"] = int(data["time_limit"])

    update_fields["updated_at"] = get_utc_now_iso()

    questions_col.update_one({"_id": q_id_str}, {"$set": update_fields})
    updated = questions_col.find_one({"_id": q_id_str})
    if updated:
        updated["_id"] = str(updated["_id"])
    return updated

def delete_question(question_id):
    """Deletes a question by ID."""
    q_id_str = str(question_id).strip()
    res = questions_col.delete_one({"_id": q_id_str})
    return getattr(res, "deleted_count", 0) > 0


# ----------------- QUIZ SETTINGS -----------------

def get_settings():
    """Retrieves main quiz settings."""
    settings = quiz_settings_col.find_one({"type": "main_config"})
    if not settings:
        settings = {
            "type": "main_config",
            "quiz_title": "Online General & Technical Knowledge Assessment",
            "quiz_status": "active",
            "is_enabled": True,
            "total_duration": 15,
            "pass_percentage": 50,
            "instructions": "Answer each question within its timer. Select one option. Submit before duration ends.",
            "updated_at": get_utc_now_iso()
        }
        quiz_settings_col.insert_one(settings)
    settings["_id"] = str(settings.get("_id", ""))
    return settings

def update_settings(data):
    """Updates quiz settings."""
    settings = get_settings()
    update_fields = {}
    
    if "quiz_status" in data:
        val = str(data["quiz_status"]).strip().lower()
        if val in ["active", "stopped", "disabled"]:
            update_fields["quiz_status"] = val
            update_fields["is_enabled"] = (val == "active")
    if "total_duration" in data:
        update_fields["total_duration"] = max(1, int(data["total_duration"]))
    if "instructions" in data:
        update_fields["instructions"] = str(data["instructions"]).strip()
    if "quiz_title" in data:
        update_fields["quiz_title"] = str(data["quiz_title"]).strip()
    if "pass_percentage" in data:
        update_fields["pass_percentage"] = int(data["pass_percentage"])

    update_fields["updated_at"] = get_utc_now_iso()
    quiz_settings_col.update_one({"type": "main_config"}, {"$set": update_fields})
    return get_settings()


# ----------------- STUDENT & QUIZ ATTEMPTS -----------------

def register_student(name, register_number):
    """Registers or fetches an existing student."""
    name = str(name).strip()
    register_number = str(register_number).strip().upper()

    if not name or not register_number:
        raise ValueError("Student Name and Register Number are required.")

    student = students_col.find_one({"register_number": register_number})
    if not student:
        doc = {
            "name": name,
            "register_number": register_number,
            "created_at": get_utc_now_iso()
        }
        res = students_col.insert_one(doc)
        doc["_id"] = str(getattr(res, "inserted_id", doc.get("_id")))
        return doc
    else:
        # Update name if changed
        students_col.update_one(
            {"register_number": register_number},
            {"$set": {"name": name}}
        )
        student["name"] = name
        student["_id"] = str(student.get("_id"))
        return student

def get_student_attempt(register_number):
    """Finds existing attempt for student."""
    reg = str(register_number).strip().upper()
    return quiz_attempts_col.find_one({"register_number": reg})

def get_sanitized_questions_for_student():
    """
    CRITICAL SECURITY FUNCTION:
    Returns questions list WITHOUT the correct_answer field!
    """
    cursor = questions_col.find({})
    sanitized = []
    for doc in cursor:
        sanitized.append({
            "_id": str(doc.get("_id")),
            "question_text": doc.get("question_text"),
            "options": doc.get("options"),
            "marks": doc.get("marks", 1),
            "time_limit": doc.get("time_limit", 30)
        })
    return sanitized

def start_quiz_attempt(name, register_number, client_ip=""):
    """Starts or resumes an active quiz attempt for student with authoritative timer & session tracking."""
    student = register_student(name, register_number)
    reg = student["register_number"]

    # Check quiz settings
    settings = get_settings()
    if settings.get("quiz_status") != "active" or not settings.get("is_enabled", True):
        raise ValueError("The quiz is currently not active or has been stopped by the administrator.")

    total_duration_mins = int(settings.get("total_duration", 15))
    total_duration_secs = total_duration_mins * 60

    # Check existing attempt
    existing = quiz_attempts_col.find_one({"register_number": reg})
    if existing:
        status = existing.get("status", "")
        if status in ["completed", "auto_submitted"]:
            raise ValueError(f"Student with Register Number {reg} has already submitted the quiz.")
        if status == "terminated":
            raise ValueError(f"Your quiz session has been terminated by the administrator.")

        # Calculate authoritative server-side remaining time
        now_dt = datetime.datetime.now(datetime.timezone.utc)
        try:
            start_dt = datetime.datetime.fromisoformat(existing["start_time"].replace("Z", "+00:00"))
            elapsed = int((now_dt - start_dt).total_seconds())
        except Exception:
            elapsed = 0

        remaining_secs = max(0, total_duration_secs - elapsed)
        if remaining_secs <= 0 and status in ["in_progress", "active"]:
            # Authoritative server-side expiration
            evaluated = submit_quiz_attempt(str(existing["_id"]), is_auto_submit=True)
            raise ValueError(f"Quiz total duration has expired for Register Number {reg}. Your responses were auto-submitted.")

        # Multiple session detection: check if there's an existing session with recent heartbeat
        last_hb_str = existing.get("last_heartbeat")
        if last_hb_str:
            try:
                last_hb_dt = datetime.datetime.fromisoformat(last_hb_str.replace("Z", "+00:00"))
                if (now_dt - last_hb_dt).total_seconds() < 25:
                    # Active session on another device / tab
                    log_student_activity(
                        str(existing["_id"]),
                        "MULTIPLE_SESSION",
                        f"Simultaneous login detected from IP {client_ip or 'unknown'}",
                        1
                    )
            except Exception:
                pass

        session_token = str(uuid.uuid4())
        quiz_attempts_col.update_one(
            {"_id": str(existing["_id"])},
            {"$set": {
                "session_token": session_token,
                "last_heartbeat": get_utc_now_iso(),
                "status": "active"
            }}
        )
        existing["session_token"] = session_token
        existing["_id"] = str(existing.get("_id"))
        existing["server_remaining_seconds"] = remaining_secs
        return existing, get_sanitized_questions_for_student(), settings

    # Create new attempt
    questions = get_sanitized_questions_for_student()
    if not questions:
        raise ValueError("No questions available in the quiz yet. Please contact the administrator.")

    total_marks = sum(q.get("marks", 1) for q in questions)
    session_token = str(uuid.uuid4())
    
    new_attempt = {
        "student_id": str(student.get("_id")),
        "student_name": student["name"],
        "register_number": reg,
        "session_token": session_token,
        "answers": {},                # { question_id: "A" }
        "start_time": get_utc_now_iso(),
        "submission_time": None,
        "last_heartbeat": get_utc_now_iso(),
        "score": 0,
        "total_marks": total_marks,
        "percentage": 0,
        "status": "active",           # active, completed, auto_submitted, terminated
        "tab_switches_count": 0,
        "fullscreen_exits_count": 0,
        "suspicious_events_count": 0,
        "correct_count": 0,
        "wrong_count": 0,
        "unanswered_count": len(questions),
        "total_questions": len(questions),
        "client_ip": client_ip
    }

    res = quiz_attempts_col.insert_one(new_attempt)
    new_attempt["_id"] = str(getattr(res, "inserted_id", new_attempt.get("_id")))
    new_attempt["server_remaining_seconds"] = total_duration_secs
    return new_attempt, questions, settings

def save_student_answer(attempt_id, question_id, selected_option):
    """Autosaves a selected option for a question with status & timer verification."""
    attempt_id_str = str(attempt_id).strip()
    attempt = quiz_attempts_col.find_one({"_id": attempt_id_str})
    if not attempt:
        raise ValueError("Invalid quiz attempt session")
    if attempt.get("status") in ["completed", "auto_submitted"]:
        raise ValueError("Quiz has already been submitted")
    if attempt.get("status") == "terminated":
        raise ValueError("Your examination session has been terminated by the administrator.")

    # Server-side timer expiration check
    settings = get_settings()
    total_duration_secs = int(settings.get("total_duration", 15)) * 60
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    try:
        start_dt = datetime.datetime.fromisoformat(attempt["start_time"].replace("Z", "+00:00"))
        # Add 30 seconds network grace period
        if (now_dt - start_dt).total_seconds() > (total_duration_secs + 30):
            submit_quiz_attempt(attempt_id_str, is_auto_submit=True)
            raise ValueError("Quiz total duration has expired. Answers auto-submitted.")
    except Exception as e:
        if "Quiz total duration has expired" in str(e):
            raise e

    answers = attempt.get("answers", {})
    if selected_option:
        answers[str(question_id)] = str(selected_option).upper()
    elif str(question_id) in answers:
        # Clear if null
        del answers[str(question_id)]

    quiz_attempts_col.update_one(
        {"_id": attempt_id_str},
        {"$set": {
            "answers": answers,
            "last_heartbeat": get_utc_now_iso()
        }}
    )
    return True

def submit_quiz_attempt(attempt_id, is_auto_submit=False):
    """
    CRITICAL SECURITY FUNCTION:
    Evaluates student answers securely on the Python backend against database questions.
    """
    attempt_id_str = str(attempt_id).strip()
    attempt = quiz_attempts_col.find_one({"_id": attempt_id_str})
    if not attempt:
        raise ValueError("Quiz attempt not found")

    if attempt.get("status") in ["completed", "auto_submitted"]:
        # Return existing result
        attempt["_id"] = str(attempt.get("_id"))
        return attempt

    student_answers = attempt.get("answers", {})

    # Fetch all questions with correct answers from DB
    all_questions = list(questions_col.find({}))
    total_questions = len(all_questions)
    total_marks = 0
    score = 0
    correct_count = 0
    wrong_count = 0
    unanswered_count = 0

    evaluated_details = []

    for q in all_questions:
        qid = str(q.get("_id"))
        q_marks = int(q.get("marks", 1))
        total_marks += q_marks
        correct_opt = str(q.get("correct_answer", "")).upper()
        student_opt = str(student_answers.get(qid, "")).upper()

        if not student_opt:
            unanswered_count += 1
            is_correct = False
        elif student_opt == correct_opt:
            correct_count += 1
            score += q_marks
            is_correct = True
        else:
            wrong_count += 1
            is_correct = False

        evaluated_details.append({
            "question_id": qid,
            "question_text": q.get("question_text"),
            "options": q.get("options"),
            "student_answer": student_opt if student_opt else None,
            "correct_answer": correct_opt,
            "marks": q_marks,
            "is_correct": is_correct
        })

    percentage = round((score / total_marks) * 100, 2) if total_marks > 0 else 0.0

    submission_status = "auto_submitted" if is_auto_submit else "completed"
    submission_time = get_utc_now_iso()

    update_payload = {
        "score": score,
        "total_marks": total_marks,
        "percentage": percentage,
        "correct_count": correct_count,
        "wrong_count": wrong_count,
        "unanswered_count": unanswered_count,
        "total_questions": total_questions,
        "status": submission_status,
        "submission_time": submission_time,
        "detailed_results": evaluated_details
    }

    quiz_attempts_col.update_one({"_id": attempt_id_str}, {"$set": update_payload})
    
    attempt.update(update_payload)
    attempt["_id"] = str(attempt.get("_id"))
    return attempt


# ----------------- ANTI-CHEATING & ACTIVITY LOGGING -----------------

VALID_EVENT_TYPES = [
    "TAB_SWITCH",
    "WINDOW_BLUR",
    "WINDOW_HIDDEN",
    "FULLSCREEN_EXIT",
    "COPY_ATTEMPT",
    "PASTE_ATTEMPT",
    "CUT_ATTEMPT",
    "RIGHT_CLICK",
    "DEVELOPER_TOOLS_SHORTCUT",
    "MULTIPLE_SESSION",
    "SESSION_DISCONNECTED"
]

def log_student_activity(attempt_id, event_type, event_description="", event_count=1):
    """Stores suspicious event in MongoDB quiz_activity_logs and updates attempt stats."""
    attempt_id_str = str(attempt_id).strip()
    attempt = quiz_attempts_col.find_one({"_id": attempt_id_str})
    if not attempt:
        return False

    event_type_clean = str(event_type).strip().upper()
    if event_type_clean not in VALID_EVENT_TYPES:
        event_type_clean = "SUSPICIOUS_EVENT"

    now_iso = get_utc_now_iso()
    log_doc = {
        "student_name": attempt.get("student_name", "Anonymous"),
        "register_number": attempt.get("register_number", ""),
        "quiz_session_id": attempt_id_str,
        "event_type": event_type_clean,
        "event_description": str(event_description).strip() or f"Detected {event_type_clean}",
        "event_timestamp": now_iso,
        "event_count": int(event_count) if event_count else 1
    }
    quiz_activity_logs_col.insert_one(log_doc)

    # Increment counter on the attempt
    updates = {
        "last_heartbeat": now_iso,
        "suspicious_events_count": int(attempt.get("suspicious_events_count", 0)) + 1
    }
    if event_type_clean in ["TAB_SWITCH", "WINDOW_BLUR", "WINDOW_HIDDEN"]:
        updates["tab_switches_count"] = int(attempt.get("tab_switches_count", 0)) + 1
    elif event_type_clean == "FULLSCREEN_EXIT":
        updates["fullscreen_exits_count"] = int(attempt.get("fullscreen_exits_count", 0)) + 1

    quiz_attempts_col.update_one({"_id": attempt_id_str}, {"$set": updates})
    return True

def process_heartbeat(attempt_id, session_token=None):
    """Processes student heartbeat to confirm active participation and detects termination."""
    attempt_id_str = str(attempt_id).strip()
    attempt = quiz_attempts_col.find_one({"_id": attempt_id_str})
    if not attempt:
        return {"status": "not_found", "is_terminated": True}

    current_status = attempt.get("status", "active")
    if current_status == "terminated":
        return {"status": "terminated", "is_terminated": True, "message": "Your session has been terminated by the administrator."}

    if current_status in ["completed", "auto_submitted"]:
        return {"status": current_status, "is_terminated": False}

    # Session token check
    if session_token and attempt.get("session_token") and attempt.get("session_token") != str(session_token):
        return {"status": "multiple_session", "is_terminated": False, "message": "Another session is active for this registration."}

    # Calculate remaining time
    settings = get_settings()
    total_duration_secs = int(settings.get("total_duration", 15)) * 60
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    try:
        start_dt = datetime.datetime.fromisoformat(attempt["start_time"].replace("Z", "+00:00"))
        elapsed = int((now_dt - start_dt).total_seconds())
    except Exception:
        elapsed = 0

    remaining = max(0, total_duration_secs - elapsed)
    if remaining <= 0:
        submit_quiz_attempt(attempt_id_str, is_auto_submit=True)
        return {"status": "auto_submitted", "is_terminated": False, "remaining_seconds": 0}

    quiz_attempts_col.update_one(
        {"_id": attempt_id_str},
        {"$set": {
            "last_heartbeat": get_utc_now_iso(),
            "status": "active"
        }}
    )
    return {"status": "active", "is_terminated": False, "remaining_seconds": remaining}

def terminate_student_session(attempt_id):
    """Terminates an ongoing student session."""
    attempt_id_str = str(attempt_id).strip()
    attempt = quiz_attempts_col.find_one({"_id": attempt_id_str})
    if not attempt:
        return False

    quiz_attempts_col.update_one(
        {"_id": attempt_id_str},
        {"$set": {
            "status": "terminated",
            "terminated_at": get_utc_now_iso()
        }}
    )

    log_student_activity(
        attempt_id_str,
        "SESSION_DISCONNECTED",
        "Session terminated by administrator",
        1
    )
    return True

def get_live_monitoring_students():
    """Returns active and recent student attempts with live status and anti-cheat counters."""
    attempts = list(quiz_attempts_col.find({}, sort=[("start_time", -1)]))
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    live_list = []

    for a in attempts:
        a_id = str(a.get("_id"))
        raw_status = a.get("status", "active")
        last_hb_str = a.get("last_heartbeat") or a.get("start_time")

        # Determine if disconnected
        calc_status = raw_status
        if raw_status in ["active", "in_progress"]:
            if last_hb_str:
                try:
                    hb_dt = datetime.datetime.fromisoformat(last_hb_str.replace("Z", "+00:00"))
                    diff_secs = (now_dt - hb_dt).total_seconds()
                    if diff_secs > 45:
                        calc_status = "disconnected"
                    else:
                        calc_status = "active"
                except Exception:
                    calc_status = "active"

        live_list.append({
            "_id": a_id,
            "student_name": a.get("student_name", "Anonymous"),
            "register_number": a.get("register_number", ""),
            "status": calc_status,
            "tab_switches_count": int(a.get("tab_switches_count", 0)),
            "fullscreen_exits_count": int(a.get("fullscreen_exits_count", 0)),
            "suspicious_events_count": int(a.get("suspicious_events_count", 0)),
            "start_time": a.get("start_time"),
            "submission_time": a.get("submission_time"),
            "last_heartbeat": last_hb_str
        })
    return live_list

def get_student_activity_logs(attempt_id):
    """Fetches all suspicious activity events recorded for a quiz session."""
    attempt_id_str = str(attempt_id).strip()
    logs = list(quiz_activity_logs_col.find(
        {"quiz_session_id": attempt_id_str},
        sort=[("event_timestamp", -1)]
    ))
    for l in logs:
        l["_id"] = str(l.get("_id"))
    return logs


# ----------------- ADMIN DASHBOARD & RESULTS -----------------

def get_admin_dashboard_stats():
    """Gathers summary statistics for the Admin Dashboard."""
    total_questions = questions_col.count_documents({})
    total_students = students_col.count_documents({})
    total_attempts = quiz_attempts_col.count_documents({})
    
    settings = get_settings()
    quiz_status = settings.get("quiz_status", "active")

    # Calculate average score and pass rate
    all_attempts = list(quiz_attempts_col.find({}))
    now_dt = datetime.datetime.now(datetime.timezone.utc)
    
    completed_count = 0
    active_students = 0
    suspicious_alerts_count = 0
    total_score_sum = 0
    pass_count = 0
    pass_threshold = settings.get("pass_percentage", 50)

    for a in all_attempts:
        st = a.get("status", "")
        if st in ["completed", "auto_submitted"]:
            completed_count += 1
            pct = float(a.get("percentage", 0))
            total_score_sum += pct
            if pct >= pass_threshold:
                pass_count += 1
        elif st in ["active", "in_progress"]:
            last_hb_str = a.get("last_heartbeat") or a.get("start_time")
            if last_hb_str:
                try:
                    hb_dt = datetime.datetime.fromisoformat(last_hb_str.replace("Z", "+00:00"))
                    if (now_dt - hb_dt).total_seconds() <= 45:
                        active_students += 1
                except Exception:
                    pass

        # High risk threshold: 3 or more suspicious events
        if int(a.get("suspicious_events_count", 0)) >= 3 or int(a.get("tab_switches_count", 0)) >= 3:
            suspicious_alerts_count += 1

    avg_percentage = round(total_score_sum / completed_count, 1) if completed_count > 0 else 0.0

    return {
        "total_questions": total_questions,
        "total_students": total_students,
        "total_quiz_attempts": total_attempts,
        "active_students": active_students,
        "completed_attempts": completed_count,
        "completed_quizzes": completed_count,
        "suspicious_alerts_count": suspicious_alerts_count,
        "quiz_status": quiz_status,
        "is_enabled": settings.get("is_enabled", True),
        "total_duration": settings.get("total_duration", 15),
        "average_percentage": avg_percentage,
        "pass_count": pass_count
    }

def get_all_results_admin():
    """Returns all student attempts for admin table."""
    cursor = quiz_attempts_col.find({}, sort=[("submission_time", -1)])
    results = []
    for doc in cursor:
        doc["_id"] = str(doc.get("_id"))
        # Strip heavy detailed_results from list view for performance
        if "detailed_results" in doc:
            doc.pop("detailed_results")
        results.append(doc)
    return results

def get_individual_result_detail(attempt_id):
    """Returns single attempt with question-by-question breakdown."""
    doc = quiz_attempts_col.find_one({"_id": str(attempt_id).strip()})
    if doc:
        doc["_id"] = str(doc.get("_id"))
    return doc
