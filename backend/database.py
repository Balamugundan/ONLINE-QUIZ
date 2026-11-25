import os
import json
import uuid
import datetime
from dotenv import load_dotenv

load_dotenv()

MONGO_URI = os.getenv("MONGO_URI", "").strip()
DB_NAME = os.getenv("DB_NAME", "online_quiz_db").strip()

use_mongo = False
mongo_client = None
db = None

if MONGO_URI:
    try:
        from pymongo import MongoClient
        mongo_client = MongoClient(MONGO_URI, serverSelectionTimeoutMS=5000)
        # Verify connection
        mongo_client.admin.command('ping')
        db = mongo_client[DB_NAME]
        use_mongo = True
        print(f"[*] Successfully connected to MongoDB Atlas: {DB_NAME}")
    except Exception as e:
        print(f"[!] Warning: Failed to connect to MongoDB Atlas ({e}). Falling back to local persistent JSON store.")
        use_mongo = False
else:
    print("[*] No MONGO_URI provided in environment. Using local persistent JSON store.")


class LocalCollection:
    """A lightweight MongoDB collection emulator for offline/local development with in-memory caching."""
    _memory_store = {}

    def __init__(self, filename, collection_name):
        self.filename = filename
        self.collection_name = collection_name
        if self.collection_name not in LocalCollection._memory_store:
            LocalCollection._memory_store[self.collection_name] = self._load_initial()

    def _load_initial(self):
        try:
            if os.path.exists(self.filename):
                with open(self.filename, 'r', encoding='utf-8') as f:
                    data = json.load(f)
                    return data.get(self.collection_name, [])
        except Exception:
            pass
        return []

    def _load_data(self):
        return list(LocalCollection._memory_store.get(self.collection_name, []))

    def _save_data(self, docs):
        LocalCollection._memory_store[self.collection_name] = list(docs)
        try:
            all_data = {}
            if os.path.exists(self.filename):
                try:
                    with open(self.filename, 'r', encoding='utf-8') as f:
                        all_data = json.load(f)
                except Exception:
                    all_data = {}
            all_data[self.collection_name] = docs
            with open(self.filename, 'w', encoding='utf-8') as f:
                json.dump(all_data, f, indent=2, default=str)
        except Exception:
            # Safe in-memory fallback
            pass

    def insert_one(self, doc):
        docs = self._load_data()
        doc = dict(doc)
        if "_id" not in doc:
            doc["_id"] = str(uuid.uuid4())
        docs.append(doc)
        self._save_data(docs)
        class Result:
            inserted_id = doc["_id"]
        return Result()

    def find_one(self, query=None):
        docs = self._load_data()
        if not query:
            return docs[0] if docs else None
        for doc in docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                return dict(doc)
        return None

    def find(self, query=None, sort=None):
        docs = self._load_data()
        if not query:
            res = list(docs)
        else:
            res = []
            for doc in docs:
                match = True
                for k, v in query.items():
                    if doc.get(k) != v:
                        match = False
                        break
                if match:
                    res.append(dict(doc))
        if sort and len(sort) > 0:
            key, direction = sort[0]
            res.sort(key=lambda x: str(x.get(key, "")), reverse=(direction == -1))
        return res

    def update_one(self, query, update_doc):
        docs = self._load_data()
        modified = 0
        set_fields = update_doc.get("$set", {})
        for doc in docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match:
                doc.update(set_fields)
                modified += 1
                break
        if modified > 0:
            self._save_data(docs)
        class Result:
            modified_count = modified
        return Result()

    def delete_one(self, query):
        docs = self._load_data()
        deleted = 0
        new_docs = []
        for doc in docs:
            match = True
            for k, v in query.items():
                if doc.get(k) != v:
                    match = False
                    break
            if match and deleted == 0:
                deleted += 1
                continue
            new_docs.append(doc)
        if deleted > 0:
            self._save_data(new_docs)
        class Result:
            deleted_count = deleted
        return Result()

    def count_documents(self, query=None):
        if not query:
            return len(self._load_data())
        return len(self.find(query))


LOCAL_DB_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "local_db.json")

def get_collection(name):
    """Returns either real PyMongo collection or LocalCollection emulator."""
    if use_mongo and db is not None:
        return db[name]
    return LocalCollection(LOCAL_DB_FILE, name)

def get_utc_now_iso():
    return datetime.datetime.now(datetime.timezone.utc).isoformat()

admins_col = get_collection("admins")
questions_col = get_collection("questions")
students_col = get_collection("students")
quiz_attempts_col = get_collection("quiz_attempts")
quiz_settings_col = get_collection("quiz_settings")
quiz_activity_logs_col = get_collection("quiz_activity_logs")

def init_default_data():
    """Initializes admin account and default quiz settings if absent."""
    from werkzeug.security import generate_password_hash
    
    # 1. Admin account initialization
    admin_user = admins_col.find_one({"username": "Admin"})
    if not admin_user:
        hashed_password = generate_password_hash("Admin@01")
        admins_col.insert_one({
            "username": "Admin",
            "password_hash": hashed_password,
            "created_at": get_utc_now_iso()
        })
        print("[*] Default admin initialized: Username=Admin, Password=Admin@01")

    # 2. Default Quiz Settings initialization
    settings = quiz_settings_col.find_one({"type": "main_config"})
    if not settings:
        default_settings = {
            "type": "main_config",
            "quiz_title": "Online General & Technical Knowledge Assessment",
            "quiz_status": "active",      # active, stopped, disabled
            "is_enabled": True,
            "total_duration": 15,          # 15 minutes overall
            "pass_percentage": 50,
            "instructions": (
                "1. Each question has its own countdown timer. When the timer expires, the quiz automatically moves to the next question.\n"
                "2. You cannot extend the question timer once it reaches zero.\n"
                "3. Select one option (A, B, C, or D) for each question.\n"
                "4. Your chosen answers are saved automatically.\n"
                "5. The quiz will automatically submit when the total quiz duration runs out.\n"
                "6. Do not refresh or close the browser tab during the test."
            ),
            "updated_at": get_utc_now_iso()
        }
        quiz_settings_col.insert_one(default_settings)
        print("[*] Default quiz settings created.")

    # 3. Seed initial standard questions if empty
    if questions_col.count_documents({}) == 0:
        seed_questions = [
            {
                "question_text": "What does REST stand for in web architecture?",
                "options": {
                    "A": "Representational State Transfer",
                    "B": "Remote Execution Standard Template",
                    "C": "Rapid Entity Sync Transmission",
                    "D": "Responsive Enterprise Server Tech"
                },
                "correct_answer": "A",
                "marks": 5,
                "time_limit": 45,
                "created_at": get_utc_now_iso()
            },
            {
                "question_text": "Which HTTP method is typically used to update an existing resource idempotently?",
                "options": {
                    "A": "GET",
                    "B": "POST",
                    "C": "PUT",
                    "D": "DELETE"
                },
                "correct_answer": "C",
                "marks": 5,
                "time_limit": 30,
                "created_at": get_utc_now_iso()
            },
            {
                "question_text": "In MongoDB, what is the primary data structure used to store documents?",
                "options": {
                    "A": "XML",
                    "B": "BSON (Binary JSON)",
                    "C": "CSV",
                    "D": "YAML"
                },
                "correct_answer": "B",
                "marks": 5,
                "time_limit": 45,
                "created_at": get_utc_now_iso()
            },
            {
                "question_text": "Which of the following JavaScript methods parses a JSON string into an object?",
                "options": {
                    "A": "JSON.stringify()",
                    "B": "JSON.parse()",
                    "C": "JSON.toObject()",
                    "D": "JSON.decode()"
                },
                "correct_answer": "B",
                "marks": 5,
                "time_limit": 30,
                "created_at": get_utc_now_iso()
            },
            {
                "question_text": "In Flask, which decorator is standardly used to bind a function to a URL route?",
                "options": {
                    "A": "@app.route()",
                    "B": "@app.bind()",
                    "C": "@app.endpoint()",
                    "D": "@app.listen()"
                },
                "correct_answer": "A",
                "marks": 5,
                "time_limit": 30,
                "created_at": get_utc_now_iso()
            }
        ]
        for q in seed_questions:
            questions_col.insert_one(q)
        print(f"[*] Seeded {len(seed_questions)} initial questions.")
