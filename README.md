# 🎓 Online Quiz Management System

A modern, responsive, and secure **Online Quiz Management System** built with **HTML5, CSS3, Vanilla JavaScript**, **Python (Flask)**, and **MongoDB Atlas**. Designed with separate **Admin** and **Student** panels, individual question timers, server-side grading, and cloud deployment ready for **Vercel** (Frontend) and **Render** (Backend).

---

## 🌟 Key Features

### 🛡️ Admin Panel
- **Secure Authentication**: Protected via username and password (`Admin` / `Admin@01`) with signed HMAC authentication tokens.
- **Interactive Dashboard**: Real-time statistics on Total Questions, Registered Students, Total Quiz Attempts, Average Scores, and Quiz Status.
- **Question Management**:
  - Add, edit, delete, and view all questions.
  - 4 answer options (A, B, C, D) with correct answer designation.
  - Configurable marks for each question.
  - **Individual Question Timers**: Custom countdowns (30s, 45s, 60s, etc.) per question.
- **Quiz Controls**: Start, Stop, or Disable quiz availability at any time; configure overall quiz duration.
- **Student Performance Analytics**:
  - Review all student submissions with scores, percentages, and timestamps.
  - Detailed modal inspection showing question-by-question candidate selections vs correct answers.
  - Search and filter by name or register number.

### 👨‍🎓 Student Panel
- **Frictionless Entry**: Login with Full Name and Register Number (no student password required).
- **Pre-Quiz Instructions**: Overview of question counts, timers, marks, guidelines, and an instant start button.
- **Active Quiz Interface**:
  - Clean, distraction-free examination view displaying one question at a time.
  - **Dual Countdown Timers**:
    1. Dedicated per-question timer with visual warning pulses under 10 seconds.
    2. Overall quiz duration timer.
  - **Automatic Answer Saving**: Answers are autosaved asynchronously to the backend database on selection.
  - **Auto-Advance on Expiry**: Automatically locks and advances to the next question when the question timer expires.
  - **Interactive Question Palette**: Live status grid displaying Answered (Green), Unanswered (Gray), Current (Blue ring), and Timer Expired (Locked).
  - **Auto-Submit on Total Expiry**: Submits the test automatically when the overall duration runs out.
  - Confirmation modal summarizing answered vs unanswered questions before final submission.

### 🔒 Enterprise-Grade Security
- **No Client-Side Answer Leakage**: Correct answers are **never sent** to the student browser.
- **Server-Side Scoring**: Calculations are performed strictly in Python on the backend.
- **Duplicate Prevention**: Prevents duplicate submissions for the same Register Number.
- **Protected Admin Endpoints**: All admin operations require valid bearer authorization tokens.

---

## 📁 Project Structure

```text
ONLINE-QUIZ/
│
├── frontend/
│   ├── index.html          # Main landing portal with student/admin card entry
│   ├── admin.html          # Admin login and full management dashboard
│   ├── student.html        # Student entry & quiz guidelines page
│   ├── quiz.html           # Live timed quiz interface with question palette
│   ├── result.html         # Score summary & performance certificate
│   ├── css/
│   │   └── style.css       # Premium responsive glassmorphic design system
│   └── js/
│       ├── config.js       # Dynamic API endpoint detection & toast notification system
│       ├── admin.js        # Admin CRUD, settings, and result inspection logic
│       ├── student.js      # Student registration and status validation
│       ├── quiz.js         # Core quiz engine, dual timers, autosave, & submission
│       └── result.js       # Result rendering, score calculation display, & PDF printing
│
├── backend/
│   ├── app.py              # Flask REST API entry point & CORS configuration
│   ├── database.py         # MongoDB Atlas connection + persistent offline fallback
│   ├── auth.py             # Admin credential verification & signed token handler
│   ├── quiz.py             # Question management, scoring logic, & analytics
│   ├── requirements.txt    # Python dependencies
│   ├── Procfile            # Deployment configuration for Render
│   ├── .env                # Local environment variables
│   └── .env.example        # Environment template for deployment
│
├── vercel.json             # Vercel deployment configuration
└── README.md               # Complete documentation
```

---

## 🚀 Getting Started (Local Development)

### 1. Prerequisites
- Python 3.9+ installed
- Modern Web Browser (Chrome, Firefox, Edge, Safari)

### 2. Backend Setup
```bash
# Navigate to the backend directory
cd ONLINE-QUIZ/backend

# Install required Python packages
pip install -r requirements.txt

# (Optional) Add your MongoDB Atlas connection URI to .env
# If left blank, an embedded persistent local store is automatically used!
```

### 3. Run the Application
```bash
# Start the Flask backend server
python app.py
```

The server will launch at:
- **Local URL**: `http://127.0.0.1:5000`
- **Default Admin Username**: `Admin`
- **Default Admin Password**: `Admin@01`

Because the backend serves the frontend statically as well, you can open `http://127.0.0.1:5000` directly in your browser, or open `frontend/index.html` via Live Server!

---

## ☁️ Online Cloud Deployment

### 1. MongoDB Atlas Setup
1. Create a free cluster at [MongoDB Atlas](https://www.mongodb.com/cloud/atlas).
2. Go to **Database Access** and create a user (e.g., `quiz_admin`).
3. Under **Network Access**, add IP `0.0.0.0/0` (allow access from anywhere).
4. Click **Connect** -> **Drivers** (Python) and copy your connection string:
   ```text
   mongodb+srv://<username>:<password>@cluster0.mongodb.net/online_quiz_db?retryWrites=true&w=majority
   ```

### 2. Render Deployment (Backend)
1. Push your repository to GitHub.
2. Sign in to [Render](https://render.com) and create a new **Web Service**.
3. Select your repository and configure:
   - **Root Directory**: `ONLINE-QUIZ/backend`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn app:app --bind 0.0.0.0:$PORT`
4. In the **Environment Variables** tab, add:
   - `MONGO_URI`: `mongodb+srv://<username>:<password>@cluster0.mongodb.net/online_quiz_db?retryWrites=true&w=majority`
   - `DB_NAME`: `online_quiz_db`
   - `SECRET_KEY`: `your_random_secret_string`
5. Click **Deploy**. Copy your Render backend URL (e.g., `https://online-quiz-api.onrender.com`).

### 3. Vercel Deployment (Frontend)
1. Sign in to [Vercel](https://vercel.com) and import your repository.
2. Set the **Root Directory** to `ONLINE-QUIZ` or `ONLINE-QUIZ/frontend`.
3. Deploy the project.
4. On your live frontend website, click the **⚙️ API** button in the top navigation bar and enter your Render backend URL (e.g., `https://online-quiz-api.onrender.com`), or set `QUIZ_API_URL` in `config.js`.

---

## 📡 REST API Reference

| Method | Endpoint | Description | Auth Required |
|---|---|---|---|
| `GET` | `/api/health` | Health check and server status | No |
| `GET` | `/api/quiz/settings` | Public quiz status and instructions | No |
| `POST` | `/api/admin/login` | Admin login | No |
| `GET` | `/api/admin/verify` | Token validity verification | Admin Token |
| `GET` | `/api/admin/dashboard` | Dashboard metrics & summary statistics | Admin Token |
| `GET` | `/api/admin/questions` | List all questions with correct answers | Admin Token |
| `POST` | `/api/admin/questions` | Add a new question | Admin Token |
| `PUT` | `/api/admin/questions/<id>` | Update an existing question | Admin Token |
| `DELETE` | `/api/admin/questions/<id>` | Delete a question | Admin Token |
| `GET` | `/api/admin/settings` | Get quiz settings | Admin Token |
| `POST` | `/api/admin/settings` | Update quiz settings & availability | Admin Token |
| `GET` | `/api/admin/results` | List all student submissions | Admin Token |
| `GET` | `/api/admin/results/<id>` | Inspect candidate question-by-question breakdown | Admin Token |
| `DELETE` | `/api/admin/results/<id>` | Remove candidate attempt | Admin Token |
| `POST` | `/api/student/login` | Register or verify candidate entry | No |
| `POST` | `/api/quiz/start` | Start/resume attempt & fetch questions (sanitized) | No |
| `POST` | `/api/quiz/save-answer` | Autosave selected answer | No |
| `POST` | `/api/quiz/submit` | Evaluate responses & compute final results | No |
| `GET` | `/api/quiz/result/<attempt_id>` | Fetch student result summary | No |

---

## 💡 Default Admin Credentials
- **Username**: `Admin`
- **Password**: `Admin@01`
