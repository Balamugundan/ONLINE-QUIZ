/**
 * Online Quiz Management System - Student Entry Logic
 */

let studentData = {
    name: '',
    register_number: ''
};

let quizPublicSettings = null;

document.addEventListener('DOMContentLoaded', async () => {
    await fetchQuizStatus();
});

async function fetchQuizStatus() {
    try {
        const res = await apiRequest('/api/quiz/settings');
        quizPublicSettings = res.data;

        const pill = document.getElementById('quiz-status-pill');
        const text = document.getElementById('quiz-status-text');

        if (quizPublicSettings.quiz_status === 'active' && quizPublicSettings.is_enabled) {
            pill.className = 'status-indicator active';
            text.textContent = 'Quiz Active';
        } else {
            pill.className = 'status-indicator stopped';
            text.textContent = `Quiz ${quizPublicSettings.quiz_status.toUpperCase()}`;

            const err = document.getElementById('entry-error-msg');
            err.style.display = 'block';
            err.innerHTML = '⚠️ <strong>Notice:</strong> The quiz is currently stopped or unavailable. Please contact your administrator.';
            document.getElementById('entry-submit-btn').disabled = true;
        }

        // Fill instruction badges
        if (quizPublicSettings) {
            document.getElementById('badge-total-q').textContent = quizPublicSettings.total_questions || 0;
            document.getElementById('badge-total-duration').textContent = `${quizPublicSettings.total_duration || 15}m`;
            if (document.getElementById('badge-total-marks')) {
                document.getElementById('badge-total-marks').textContent = `${quizPublicSettings.total_marks ?? '--'} pts`;
            }
            if (quizPublicSettings.quiz_title) {
                document.getElementById('instructions-quiz-title').textContent = quizPublicSettings.quiz_title;
            }
        }
    } catch (err) {
        console.error('Quiz settings load error:', err);
    }
}

async function handleStudentEntry(e) {
    e.preventDefault();
    const nameInput = document.getElementById('student-name').value.trim();
    const regInput = document.getElementById('student-regno').value.trim().toUpperCase();
    const errBox = document.getElementById('entry-error-msg');
    const submitBtn = document.getElementById('entry-submit-btn');

    errBox.style.display = 'none';

    if (!nameInput || nameInput.length < 2) {
        errBox.textContent = 'Please provide a valid Full Name (at least 2 characters).';
        errBox.style.display = 'block';
        return;
    }

    const regRegex = /^[A-Z0-9_-]{3,25}$/;
    if (!regInput || !regRegex.test(regInput)) {
        errBox.textContent = 'Please enter a valid Register / Roll Number (3 to 25 letters or numbers).';
        errBox.style.display = 'block';
        return;
    }

    submitBtn.disabled = true;
    submitBtn.innerHTML = '<span>Checking registration...</span>';

    try {
        const res = await apiRequest('/api/student/login', {
            method: 'POST',
            body: { name: nameInput, register_number: regInput }
        });

        studentData.name = nameInput;
        studentData.register_number = regInput;

        // Store in session storage for quiz page
        sessionStorage.setItem('student_name', nameInput);
        sessionStorage.setItem('student_regno', regInput);

        // Display instructions section
        showInstructionsView();

    } catch (err) {
        // Check if already submitted
        if (err.message && err.message.includes('already completed')) {
            errBox.innerHTML = `
                ⚠️ You have already completed this examination.<br>
                Please contact the examination administrator if you require assistance.
            `;
            errBox.style.display = 'block';
        } else {
            errBox.textContent = err.message || 'Unable to verify registration. Please try again.';
            errBox.style.display = 'block';
        }
    } finally {
        submitBtn.disabled = false;
        submitBtn.innerHTML = '<span>Continue to Instructions</span> <span>→</span>';
    }
}

function showInstructionsView() {
    document.getElementById('student-entry-section').style.display = 'none';
    const instrSection = document.getElementById('quiz-instructions-section');
    instrSection.style.display = 'block';

    document.getElementById('cand-name').textContent = studentData.name;
    document.getElementById('cand-reg').textContent = studentData.register_number;

    if (quizPublicSettings && quizPublicSettings.instructions) {
        const lines = quizPublicSettings.instructions.split('\n').filter(l => l.trim().length > 0);
        if (lines.length > 0) {
            document.getElementById('instructions-list-content').innerHTML = lines.map(line => `<li>${escapeHtml(line)}</li>`).join('');
        }
    }
}

function backToEntry() {
    document.getElementById('quiz-instructions-section').style.display = 'none';
    document.getElementById('student-entry-section').style.display = 'block';
}

function launchQuiz() {
    window.location.href = 'quiz.html';
}

function escapeHtml(text) {
    if (!text) return '';
    return String(text)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}
