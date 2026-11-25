import datetime
import uuid
from database import (
    questions_col,
    students_col,
    quiz_attempts_col,
    quiz_settings_col
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

def start_quiz_attempt(name, register_number):
    """Starts or resumes an active quiz attempt for student."""
    student = register_student(name, register_number)
    reg = student["register_number"]

    # Check quiz settings
    settings = get_settings()
    if settings.get("quiz_status") != "active" or not settings.get("is_enabled", True):
        raise ValueError("The quiz is currently not active or has been stopped by the administrator.")

    # Check existing attempt
    existing = quiz_attempts_col.find_one({"register_number": reg})
    if existing:
        if existing.get("status") in ["completed", "auto_submitted"]:
            raise ValueError(f"Student with Register Number {reg} has already submitted the quiz.")
        # If in progress, resume existing attempt
        existing["_id"] = str(existing.get("_id"))
        return existing, get_sanitized_questions_for_student(), settings

    # Create new attempt
    questions = get_sanitized_questions_for_student()
    if not questions:
        raise ValueError("No questions available in the quiz yet. Please contact the administrator.")

    total_marks = sum(q.get("marks", 1) for q in questions)
    
    new_attempt = {
        "student_id": str(student.get("_id")),
        "student_name": student["name"],
        "register_number": reg,
        "answers": {},                # { question_id: "A" }
        "start_time": get_utc_now_iso(),
        "submission_time": None,
        "score": 0,
        "total_marks": total_marks,
        "percentage": 0,
        "status": "in_progress",      # in_progress, completed, auto_submitted
        "correct_count": 0,
        "wrong_count": 0,
        "unanswered_count": len(questions),
        "total_questions": len(questions)
    }

    res = quiz_attempts_col.insert_one(new_attempt)
    new_attempt["_id"] = str(getattr(res, "inserted_id", new_attempt.get("_id")))
    return new_attempt, questions, settings

def save_student_answer(attempt_id, question_id, selected_option):
    """Autosaves a selected option for a question."""
    attempt_id_str = str(attempt_id).strip()
    attempt = quiz_attempts_col.find_one({"_id": attempt_id_str})
    if not attempt:
        raise ValueError("Invalid quiz attempt session")
    if attempt.get("status") in ["completed", "auto_submitted"]:
        raise ValueError("Quiz has already been submitted")

    answers = attempt.get("answers", {})
    if selected_option:
        answers[str(question_id)] = str(selected_option).upper()
    elif str(question_id) in answers:
        # Clear if null
        del answers[str(question_id)]

    quiz_attempts_col.update_one(
        {"_id": attempt_id_str},
        {"$set": {"answers": answers}}
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


# ----------------- ADMIN DASHBOARD & RESULTS -----------------

def get_admin_dashboard_stats():
    """Gathers summary statistics for the Admin Dashboard."""
    total_questions = questions_col.count_documents({})
    total_students = students_col.count_documents({})
    total_attempts = quiz_attempts_col.count_documents({})
    
    settings = get_settings()
    quiz_status = settings.get("quiz_status", "active")

    # Calculate average score and pass rate
    all_attempts = list(quiz_attempts_col.find({"status": {"$in": ["completed", "auto_submitted"]}}))
    completed_count = len(all_attempts)
    
    avg_percentage = 0.0
    pass_count = 0
    pass_threshold = settings.get("pass_percentage", 50)
    
    if completed_count > 0:
        total_pct = sum(float(a.get("percentage", 0)) for a in all_attempts)
        avg_percentage = round(total_pct / completed_count, 1)
        pass_count = sum(1 for a in all_attempts if float(a.get("percentage", 0)) >= pass_threshold)

    return {
        "total_questions": total_questions,
        "total_students": total_students,
        "total_quiz_attempts": total_attempts,
        "completed_attempts": completed_count,
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
