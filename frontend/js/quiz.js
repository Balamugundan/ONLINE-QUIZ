/**
 * Online Quiz Management System - Core Quiz Engine
 */

let attemptId = null;
let questions = [];
let currentIndex = 0;
let userAnswers = {};               // { [questionId]: 'A' }
let questionSecondsLeft = {};       // { [questionId]: number }
let questionExpired = {};           // { [questionId]: boolean }

let questionTimerInterval = null;
let overallTimerInterval = null;
let overallSecondsRemaining = 900;  // 15 mins default
let isSubmitting = false;

document.addEventListener('DOMContentLoaded', async () => {
    const studentName = sessionStorage.getItem('student_name');
    const studentReg = sessionStorage.getItem('student_regno');

    if (!studentName || !studentReg) {
        window.location.href = 'student.html';
        return;
    }

    document.getElementById('student-badge-name').textContent = studentName;
    document.getElementById('student-badge-reg').textContent = studentReg;

    await initializeQuizSession(studentName, studentReg);
});

async function initializeQuizSession(name, regNo) {
    const loadingView = document.getElementById('quiz-loading-view');
    const errorView = document.getElementById('quiz-error-view');
    const activeView = document.getElementById('quiz-active-view');

    try {
        const res = await apiRequest('/api/quiz/start', {
            method: 'POST',
            body: { name, register_number: regNo }
        });

        attemptId = res.attempt._id;
        questions = res.questions || [];
        userAnswers = res.attempt.answers || {};

        if (questions.length === 0) {
            throw new Error('No questions have been configured for this quiz.');
        }

        if (res.settings && res.settings.quiz_title) {
            document.getElementById('quiz-brand-title').textContent = res.settings.quiz_title;
        }

        // Initialize question timers
        questions.forEach(q => {
            const limit = parseInt(q.time_limit) || 30;
            questionSecondsLeft[q._id] = limit;
            questionExpired[q._id] = false;
        });

        // Initialize overall quiz duration
        const totalDurationMins = parseInt(res.settings?.total_duration) || 15;
        calculateOverallRemainingTime(res.attempt.start_time, totalDurationMins);

        loadingView.style.display = 'none';
        activeView.style.display = 'grid';

        // Render question palette & first question
        renderPalette();
        renderQuestion(currentIndex);
        startQuestionTimer();
        startOverallTimer();

    } catch (err) {
        loadingView.style.display = 'none';
        errorView.style.display = 'block';
        document.getElementById('quiz-error-desc').textContent = err.message || 'Unable to launch quiz.';
    }
}

function calculateOverallRemainingTime(startTimeStr, totalMins) {
    try {
        const startTime = new Date(startTimeStr).getTime();
        const now = Date.now();
        const elapsedSecs = Math.floor((now - startTime) / 1000);
        const totalSecs = totalMins * 60;
        overallSecondsRemaining = Math.max(0, totalSecs - elapsedSecs);
    } catch {
        overallSecondsRemaining = totalMins * 60;
    }
}


// ==========================================
// RENDER ACTIVE QUESTION
// ==========================================

function renderQuestion(index) {
    if (index < 0 || index >= questions.length) return;

    currentIndex = index;
    const q = questions[currentIndex];
    const isExpired = !!questionExpired[q._id];

    // Counter & Marks
    document.getElementById('q-counter').textContent = `Question ${currentIndex + 1} of ${questions.length}`;
    document.getElementById('q-marks-badge').textContent = `${q.marks || 1} Points`;

    // Question Text
    document.getElementById('question-text').textContent = q.question_text;

    // Render 4 Options
    const optionsContainer = document.getElementById('options-container');
    const opts = q.options || {};
    const selected = userAnswers[q._id];

    const letters = ['A', 'B', 'C', 'D'];
    optionsContainer.innerHTML = letters.map(letter => {
        const text = opts[letter] || '';
        const isSelected = selected === letter;
        const disabledClass = isExpired ? 'disabled' : '';

        return `
            <div class="option-card ${isSelected ? 'selected' : ''} ${disabledClass}" 
                 onclick="selectOption('${letter}')" 
                 id="option-${letter}">
                <div class="option-letter">${letter}</div>
                <div class="option-text">${escapeHtml(text)}</div>
            </div>
        `;
    }).join('');

    // Prev / Next button states
    document.getElementById('prev-btn').disabled = (currentIndex === 0);
    const nextBtn = document.getElementById('next-btn');
    if (currentIndex === questions.length - 1) {
        nextBtn.style.display = 'none';
    } else {
        nextBtn.style.display = 'inline-flex';
    }

    // Update Palette active indicator
    updatePaletteActiveState();
    updateAnsweredRatio();
    updateQuestionTimerDisplay();
}


// ==========================================
// OPTION SELECTION & AUTOSAVE
// ==========================================

async function selectOption(letter) {
    const q = questions[currentIndex];
    if (!q || questionExpired[q._id]) return;

    // Update local state
    userAnswers[q._id] = letter;

    // Update UI highlights
    ['A', 'B', 'C', 'D'].forEach(l => {
        const el = document.getElementById(`option-${l}`);
        if (el) {
            if (l === letter) el.classList.add('selected');
            else el.classList.remove('selected');
        }
    });

    // Update palette
    updatePaletteActiveState();
    updateAnsweredRatio();

    // Autosave to backend asynchronously
    try {
        await apiRequest('/api/quiz/save-answer', {
            method: 'POST',
            body: {
                attempt_id: attemptId,
                question_id: q._id,
                selected_option: letter
            }
        });
    } catch (err) {
        console.warn('Autosave warning:', err);
    }
}

async function clearCurrentSelection() {
    const q = questions[currentIndex];
    if (!q || questionExpired[q._id]) return;

    delete userAnswers[q._id];

    ['A', 'B', 'C', 'D'].forEach(l => {
        const el = document.getElementById(`option-${l}`);
        if (el) el.classList.remove('selected');
    });

    updatePaletteActiveState();
    updateAnsweredRatio();

    try {
        await apiRequest('/api/quiz/save-answer', {
            method: 'POST',
            body: {
                attempt_id: attemptId,
                question_id: q._id,
                selected_option: null
            }
        });
    } catch (err) {
        console.warn('Clear autosave warning:', err);
    }
}


// ==========================================
// INDIVIDUAL QUESTION TIMER
// ==========================================

function startQuestionTimer() {
    clearInterval(questionTimerInterval);
    updateQuestionTimerDisplay();

    questionTimerInterval = setInterval(() => {
        const q = questions[currentIndex];
        if (!q) return;

        let sec = questionSecondsLeft[q._id];
        if (sec > 0) {
            sec--;
            questionSecondsLeft[q._id] = sec;
            updateQuestionTimerDisplay();

            if (sec === 0) {
                handleQuestionTimerExpired(q._id);
            }
        }
    }, 1000);
}

function updateQuestionTimerDisplay() {
    const q = questions[currentIndex];
    if (!q) return;

    const sec = questionSecondsLeft[q._id] ?? 0;
    const badge = document.getElementById('question-timer-badge');
    const secDisplay = document.getElementById('q-timer-seconds');

    secDisplay.textContent = sec;

    if (sec <= 5) {
        badge.className = 'q-timer-badge danger';
    } else if (sec <= 10) {
        badge.className = 'q-timer-badge warning';
    } else {
        badge.className = 'q-timer-badge';
    }
}

function handleQuestionTimerExpired(questionId) {
    questionExpired[questionId] = true;
    showToast(`Time expired for Question ${currentIndex + 1}! Moving to next.`, 'warning', 2500);

    // Disable options for this question
    document.querySelectorAll('.option-card').forEach(el => el.classList.add('disabled'));

    // Update palette
    updatePaletteActiveState();

    // Auto-advance to next question if not at end
    setTimeout(() => {
        if (currentIndex < questions.length - 1) {
            navigateNext();
        } else {
            // Reached last question and expired
            openSubmitModal();
        }
    }, 800);
}


// ==========================================
// OVERALL QUIZ DURATION TIMER
// ==========================================

function startOverallTimer() {
    clearInterval(overallTimerInterval);
    updateOverallTimerDisplay();

    overallTimerInterval = setInterval(() => {
        if (overallSecondsRemaining > 0) {
            overallSecondsRemaining--;
            updateOverallTimerDisplay();

            if (overallSecondsRemaining === 0) {
                clearInterval(overallTimerInterval);
                clearInterval(questionTimerInterval);
                showToast('Total quiz duration expired! Auto-submitting answers...', 'warning', 4000);
                setTimeout(() => {
                    executeFinalSubmission(true);
                }, 1000);
            }
        }
    }, 1000);
}

function updateOverallTimerDisplay() {
    const mins = Math.floor(overallSecondsRemaining / 60);
    const secs = overallSecondsRemaining % 60;
    const formatted = `${String(mins).padStart(2, '0')}:${String(secs).padStart(2, '0')}`;
    const display = document.getElementById('overall-timer-display');
    if (display) display.textContent = formatted;
}


// ==========================================
// NAVIGATION & PALETTE
// ==========================================

function navigateNext() {
    if (currentIndex < questions.length - 1) {
        renderQuestion(currentIndex + 1);
        startQuestionTimer();
    }
}

function navigatePrev() {
    if (currentIndex > 0) {
        renderQuestion(currentIndex - 1);
        startQuestionTimer();
    }
}

function jumpToQuestion(index) {
    if (index >= 0 && index < questions.length) {
        renderQuestion(index);
        startQuestionTimer();
    }
}

function renderPalette() {
    const grid = document.getElementById('palette-grid');
    grid.innerHTML = questions.map((q, idx) => {
        return `
            <button class="palette-btn" id="palette-btn-${idx}" onclick="jumpToQuestion(${idx})">
                ${idx + 1}
            </button>
        `;
    }).join('');
}

function updatePaletteActiveState() {
    questions.forEach((q, idx) => {
        const btn = document.getElementById(`palette-btn-${idx}`);
        if (!btn) return;

        btn.className = 'palette-btn';

        if (questionExpired[q._id]) {
            btn.classList.add('locked');
        } else if (userAnswers[q._id]) {
            btn.classList.add('answered');
        }

        if (idx === currentIndex) {
            btn.classList.add('current');
        }
    });
}

function updateAnsweredRatio() {
    const answeredCount = Object.keys(userAnswers).filter(k => !!userAnswers[k]).length;
    document.getElementById('answered-ratio').textContent = `${answeredCount} / ${questions.length} Answered`;
}


// ==========================================
// FINAL SUBMISSION
// ==========================================

function openSubmitModal() {
    const answeredCount = Object.keys(userAnswers).filter(k => !!userAnswers[k]).length;
    const unansweredCount = questions.length - answeredCount;

    document.getElementById('modal-answered-count').textContent = answeredCount;
    document.getElementById('modal-unanswered-count').textContent = unansweredCount;
    document.getElementById('modal-total-count').textContent = questions.length;

    document.getElementById('submit-confirm-modal').classList.add('active');
}

function closeSubmitModal() {
    document.getElementById('submit-confirm-modal').classList.remove('active');
}

async function executeFinalSubmission(isAutoSubmit = false) {
    if (isSubmitting) return;
    isSubmitting = true;

    clearInterval(questionTimerInterval);
    clearInterval(overallTimerInterval);

    const submitBtn = document.getElementById('final-submit-btn');
    if (submitBtn) {
        submitBtn.disabled = true;
        submitBtn.textContent = 'Evaluating Score...';
    }

    try {
        const res = await apiRequest('/api/quiz/submit', {
            method: 'POST',
            body: {
                attempt_id: attemptId,
                is_auto_submit: isAutoSubmit
            }
        });

        // Store result for result page
        sessionStorage.setItem('quiz_result_summary', JSON.stringify(res.data));
        sessionStorage.setItem('quiz_completed_attempt_id', attemptId);

        // Redirect to Result Page
        window.location.href = `result.html?attempt_id=${attemptId}`;
    } catch (err) {
        isSubmitting = false;
        showToast('Submission error: ' + (err.message || 'Server error'), 'error');
        if (submitBtn) {
            submitBtn.disabled = false;
            submitBtn.textContent = 'Confirm & Submit';
        }
    }
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
