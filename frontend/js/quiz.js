/**
 * Online Quiz Management System - Core Quiz Engine
 */

let attemptId = null;
let sessionToken = null;
let questions = [];
let currentIndex = 0;
let userAnswers = {};               // { [questionId]: 'A' }
let questionSecondsLeft = {};       // { [questionId]: number }
let questionExpired = {};           // { [questionId]: boolean }

let questionTimerInterval = null;
let overallTimerInterval = null;
let heartbeatInterval = null;
let overallSecondsRemaining = 900;  // 15 mins default
let isSubmitting = false;

// Anti-Cheating & Activity Monitoring State
let suspiciousCount = 0;
let lastSuspiciousEventTime = 0;
let hasEnteredFullscreen = false;
let isMonitoringActive = false;

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
        sessionToken = res.attempt.session_token || null;
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

        // Initialize overall quiz duration with authoritative server-side remaining time
        if (typeof res.settings?.server_remaining_seconds === 'number') {
            overallSecondsRemaining = Math.max(0, res.settings.server_remaining_seconds);
        } else {
            const totalDurationMins = parseInt(res.settings?.total_duration) || 15;
            calculateOverallRemainingTime(res.attempt.start_time, totalDurationMins);
        }

        loadingView.style.display = 'none';
        activeView.style.display = 'grid';

        // Render question palette & first question
        renderPalette();
        renderQuestion(currentIndex);
        startQuestionTimer();
        startOverallTimer();

        // Start Anti-Cheating Monitoring & Heartbeat
        initAntiCheatingMonitoring();
        startHeartbeat();

        // Request Fullscreen mode gently
        setTimeout(() => {
            requestFullScreenMode();
        }, 500);

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

    isMonitoringActive = false;
    clearInterval(questionTimerInterval);
    clearInterval(overallTimerInterval);
    clearInterval(heartbeatInterval);

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

// ==========================================
// ANTI-CHEATING MONITORING & HEARTBEAT ENGINE
// ==========================================

function startHeartbeat() {
    clearInterval(heartbeatInterval);
    heartbeatInterval = setInterval(async () => {
        if (!attemptId || isSubmitting) return;
        try {
            const res = await apiRequest('/api/quiz/heartbeat', {
                method: 'POST',
                body: {
                    attempt_id: attemptId,
                    session_token: sessionToken
                }
            });

            if (res.data?.is_terminated) {
                handleSessionTerminated(res.data?.message);
            }
        } catch (err) {
            console.warn('Heartbeat check error:', err);
        }
    }, 10000);
}

function handleSessionTerminated(message) {
    isMonitoringActive = false;
    clearInterval(questionTimerInterval);
    clearInterval(overallTimerInterval);
    clearInterval(heartbeatInterval);

    const modal = document.getElementById('session-terminated-modal');
    if (modal) {
        if (message) {
            const desc = document.getElementById('termination-message');
            if (desc) desc.textContent = message;
        }
        modal.classList.add('active');
    } else {
        alert(message || 'Your examination session has been terminated by the administrator.');
        window.location.href = 'index.html';
    }
}

function initAntiCheatingMonitoring() {
    isMonitoringActive = true;

    // 1. Tab Switching & Window Blur Detection
    document.addEventListener('visibilitychange', () => {
        if (!isMonitoringActive || isSubmitting) return;
        if (document.hidden) {
            handleSuspiciousEvent('TAB_SWITCH', 'Switched to another tab or minimized window');
        }
    });

    window.addEventListener('blur', () => {
        if (!isMonitoringActive || isSubmitting) return;
        handleSuspiciousEvent('WINDOW_BLUR', 'Window lost focus / clicked outside examination screen');
    });

    // 2. Fullscreen Exit Detection
    const handleFullscreenChange = () => {
        if (!isMonitoringActive || isSubmitting) return;
        const isFullscreen = !!(document.fullscreenElement || document.webkitFullscreenElement);
        if (!isFullscreen && hasEnteredFullscreen) {
            handleSuspiciousEvent('FULLSCREEN_EXIT', 'Exited fullscreen examination mode');
            const promptModal = document.getElementById('fullscreen-prompt-modal');
            if (promptModal) promptModal.classList.add('active');
        }
    };

    document.addEventListener('fullscreenchange', handleFullscreenChange);
    document.addEventListener('webkitfullscreenchange', handleFullscreenChange);

    // 3. Copy, Cut, Paste & Right Click Restrictions
    document.addEventListener('copy', (e) => {
        if (!isMonitoringActive || isSubmitting) return;
        e.preventDefault();
        handleSuspiciousEvent('COPY_ATTEMPT', 'Attempted to copy examination content');
        showToast('⚠️ Copying is restricted during the examination.', 'warning');
    });

    document.addEventListener('cut', (e) => {
        if (!isMonitoringActive || isSubmitting) return;
        e.preventDefault();
        handleSuspiciousEvent('CUT_ATTEMPT', 'Attempted to cut examination content');
    });

    document.addEventListener('paste', (e) => {
        if (!isMonitoringActive || isSubmitting) return;
        e.preventDefault();
        handleSuspiciousEvent('PASTE_ATTEMPT', 'Attempted to paste content into quiz');
    });

    document.addEventListener('contextmenu', (e) => {
        if (!isMonitoringActive || isSubmitting) return;
        e.preventDefault();
        handleSuspiciousEvent('RIGHT_CLICK', 'Attempted right-click context menu');
    });

    // 4. Developer Tools Shortcut Detection
    document.addEventListener('keydown', (e) => {
        if (!isMonitoringActive || isSubmitting) return;

        // F12 key
        if (e.key === 'F12' || e.keyCode === 123) {
            e.preventDefault();
            handleSuspiciousEvent('DEVELOPER_TOOLS_SHORTCUT', 'Pressed F12 (Developer Tools shortcut)');
            return;
        }

        // Ctrl+Shift+I / J / C or Cmd+Opt+I / J / C
        if ((e.ctrlKey || e.metaKey) && e.shiftKey && ['I', 'i', 'J', 'j', 'C', 'c'].includes(e.key)) {
            e.preventDefault();
            handleSuspiciousEvent('DEVELOPER_TOOLS_SHORTCUT', `Pressed shortcut (Ctrl+Shift+${e.key.toUpperCase()})`);
            return;
        }

        // Ctrl+U (View Source)
        if ((e.ctrlKey || e.metaKey) && (e.key === 'u' || e.key === 'U')) {
            e.preventDefault();
            handleSuspiciousEvent('DEVELOPER_TOOLS_SHORTCUT', 'Pressed Ctrl+U (View Source shortcut)');
            return;
        }
    });
}

function requestFullScreenMode() {
    const promptModal = document.getElementById('fullscreen-prompt-modal');
    if (promptModal) promptModal.classList.remove('active');

    const elem = document.documentElement;
    if (elem.requestFullscreen) {
        elem.requestFullscreen().then(() => {
            hasEnteredFullscreen = true;
        }).catch(() => {
            // Browser restricted or declined - don't falsely penalize
        });
    } else if (elem.webkitRequestFullscreen) {
        elem.webkitRequestFullscreen();
        hasEnteredFullscreen = true;
    }
}

async function handleSuspiciousEvent(eventType, description) {
    if (!isMonitoringActive || isSubmitting) return;

    const now = Date.now();
    // Throttle duplicate events within 1.5 seconds (e.g. blur followed immediately by visibilitychange)
    if (now - lastSuspiciousEventTime < 1500) return;
    lastSuspiciousEventTime = now;

    suspiciousCount++;

    // Asynchronously send activity log to Flask backend
    try {
        await apiRequest('/api/quiz/activity-log', {
            method: 'POST',
            body: {
                attempt_id: attemptId,
                event_type: eventType,
                event_description: description,
                event_count: suspiciousCount
            }
        });
    } catch (err) {
        console.warn('Activity log sync error:', err);
    }

    // Trigger Warning Modal for tab switches / blur / exits
    if (['TAB_SWITCH', 'WINDOW_BLUR', 'WINDOW_HIDDEN', 'FULLSCREEN_EXIT'].includes(eventType)) {
        showWarningModal(suspiciousCount);
    }
}

function showWarningModal(count) {
    const modal = document.getElementById('anti-cheat-warning-modal');
    const badge = document.getElementById('warning-badge-pill');
    const desc = document.getElementById('warning-desc');
    const countDisplay = document.getElementById('warning-count-display');

    if (!modal) return;
    if (countDisplay) countDisplay.textContent = count;

    if (count === 1) {
        if (badge) {
            badge.textContent = '⚠️ Warning Level 1';
            badge.style.background = 'rgba(245, 158, 11, 0.2)';
            badge.style.color = '#f59e0b';
        }
        if (desc) {
            desc.textContent = 'Warning! Leaving the examination screen has been recorded. Please remain on the quiz page until you complete the examination.';
        }
    } else if (count === 2) {
        if (badge) {
            badge.textContent = '⚠️ Warning Level 2';
            badge.style.background = 'rgba(239, 68, 68, 0.2)';
            badge.style.color = '#ef4444';
        }
        if (desc) {
            desc.textContent = 'Warning! Second violation recorded. Further tab switches will alert the examination administrator.';
        }
    } else {
        if (badge) {
            badge.textContent = '🚨 High-Risk Alert';
            badge.style.background = 'rgba(239, 68, 68, 0.35)';
            badge.style.color = '#ef4444';
        }
        if (desc) {
            desc.textContent = 'High-Risk Alert! Repeated screen exits have been logged and flagged on the administrator live monitoring panel.';
        }
    }

    modal.classList.add('active');
}

function acknowledgeWarning() {
    const modal = document.getElementById('anti-cheat-warning-modal');
    if (modal) modal.classList.remove('active');
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
