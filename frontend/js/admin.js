/**
 * Online Quiz Management System - Admin Dashboard Logic
 */

let allQuestions = [];
let allResults = [];
let currentSettings = null;

// ==========================================
// AUTHENTICATION & INITIALIZATION
// ==========================================

document.addEventListener('DOMContentLoaded', async () => {
    await checkAdminAuth();
});

async function checkAdminAuth() {
    const token = localStorage.getItem('admin_token');
    const loginView = document.getElementById('admin-login-view');
    const dashboardView = document.getElementById('admin-dashboard-view');
    const logoutBtn = document.getElementById('admin-logout-btn');
    const adminBadge = document.getElementById('admin-badge');
    const userDisplay = document.getElementById('admin-user-display');

    if (!token) {
        loginView.style.display = 'block';
        dashboardView.style.display = 'none';
        logoutBtn.style.display = 'none';
        adminBadge.style.display = 'none';
        return;
    }

    try {
        await apiRequest('/api/admin/verify');
        // Valid token
        loginView.style.display = 'none';
        dashboardView.style.display = 'block';
        logoutBtn.style.display = 'inline-flex';
        adminBadge.style.display = 'inline-flex';
        userDisplay.textContent = localStorage.getItem('admin_user') || 'Admin';

        // Load all dashboard content
        await loadAllDashboardData();
    } catch (err) {
        localStorage.removeItem('admin_token');
        localStorage.removeItem('admin_user');
        loginView.style.display = 'block';
        dashboardView.style.display = 'none';
        logoutBtn.style.display = 'none';
        adminBadge.style.display = 'none';
    }
}

async function handleAdminLogin(e) {
    e.preventDefault();
    const btn = document.getElementById('login-submit-btn');
    const usernameInput = document.getElementById('login-username').value.trim();
    const passwordInput = document.getElementById('login-password').value;

    btn.disabled = true;
    btn.innerHTML = '<span>Verifying...</span>';

    try {
        const res = await apiRequest('/api/admin/login', {
            method: 'POST',
            body: { username: usernameInput, password: passwordInput }
        });

        localStorage.setItem('admin_token', res.token);
        localStorage.setItem('admin_user', res.username);

        showToast('Login successful! Welcome back.', 'success');
        await checkAdminAuth();
    } catch (err) {
        showToast(err.message || 'Invalid username or password', 'error');
    } finally {
        btn.disabled = false;
        btn.innerHTML = '<span>Login to Dashboard</span> <span>→</span>';
    }
}

function logoutAdmin() {
    localStorage.removeItem('admin_token');
    localStorage.removeItem('admin_user');
    showToast('Logged out successfully', 'info');
    checkAdminAuth();
}


// ==========================================
// TABS SWITCHING
// ==========================================

function switchAdminTab(tabName) {
    const tabs = ['overview', 'questions', 'settings', 'results'];
    const tabBtns = document.querySelectorAll('.tab-btn');

    tabs.forEach((tab, idx) => {
        const content = document.getElementById(`tab-${tab}`);
        if (content) {
            if (tab === tabName) {
                content.classList.add('active');
                if (tabBtns[idx]) tabBtns[idx].classList.add('active');
            } else {
                content.classList.remove('active');
                if (tabBtns[idx]) tabBtns[idx].classList.remove('active');
            }
        }
    });

    if (tabName === 'questions') loadAdminQuestions();
    if (tabName === 'settings') loadAdminSettings();
    if (tabName === 'results') loadAdminResults();
}


// ==========================================
// DATA LOADING
// ==========================================

async function loadAllDashboardData() {
    try {
        await Promise.all([
            loadDashboardStats(),
            loadAdminQuestions(),
            loadAdminSettings(),
            loadAdminResults()
        ]);
    } catch (err) {
        console.error('Failed to load dashboard data:', err);
    }
}

async function loadDashboardStats() {
    try {
        const res = await apiRequest('/api/admin/dashboard');
        const stats = res.data;

        document.getElementById('stat-total-questions').textContent = stats.total_questions;
        document.getElementById('stat-total-students').textContent = stats.total_students;
        document.getElementById('stat-total-attempts').textContent = stats.total_quiz_attempts;
        document.getElementById('stat-avg-score').textContent = `${stats.average_percentage}%`;
        document.getElementById('overview-duration-display').textContent = `${stats.total_duration} Minutes`;

        // Update live status badge
        const badge = document.getElementById('quiz-live-status-badge');
        if (stats.quiz_status === 'active') {
            badge.className = 'badge badge-success';
            badge.textContent = 'Status: Active';
        } else if (stats.quiz_status === 'stopped') {
            badge.className = 'badge badge-warning';
            badge.textContent = 'Status: Stopped';
        } else {
            badge.className = 'badge badge-danger';
            badge.textContent = 'Status: Disabled';
        }
    } catch (err) {
        console.error('Stats load error:', err);
    }
}


// ==========================================
// QUESTION MANAGEMENT
// ==========================================

async function loadAdminQuestions() {
    try {
        const res = await apiRequest('/api/admin/questions');
        allQuestions = res.data || [];

        document.getElementById('tab-questions-count').textContent = allQuestions.length;
        
        let totalMarks = allQuestions.reduce((sum, q) => sum + (parseInt(q.marks) || 1), 0);
        const marksDisplay = document.getElementById('overview-total-marks');
        if (marksDisplay) marksDisplay.textContent = `${totalMarks} Marks`;

        renderQuestionsTable(allQuestions);
    } catch (err) {
        showToast('Error loading questions: ' + err.message, 'error');
    }
}

function renderQuestionsTable(questions) {
    const tbody = document.getElementById('questions-table-body');
    if (!questions || questions.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="7" style="text-align: center; color: var(--text-muted); padding: 3rem;">
                    No questions added yet. Click "+ Add Question" to get started!
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = questions.map((q, idx) => {
        const opts = q.options || {};
        const safeText = escapeHtml(q.question_text);
        const optsList = ['A', 'B', 'C', 'D'].map(letter => {
            const isCorrect = q.correct_answer === letter;
            return `<span style="font-size: 0.8rem; margin-right: 0.5rem; ${isCorrect ? 'color: var(--success); font-weight: 700;' : 'color: var(--text-secondary);'}">
                <strong>${letter}:</strong> ${escapeHtml(opts[letter] || '')}
            </span>`;
        }).join(' | ');

        return `
            <tr>
                <td><strong>${idx + 1}</strong></td>
                <td>
                    <div style="font-weight: 600; margin-bottom: 0.35rem;">${safeText}</div>
                    <div style="font-size: 0.82rem; color: var(--text-muted);">${optsList}</div>
                </td>
                <td><span class="badge badge-success">Option ${q.correct_answer}</span></td>
                <td><strong>${q.marks}</strong> pts</td>
                <td><span class="badge badge-primary">⏱️ ${q.time_limit}s</span></td>
                <td style="text-align: right;">
                    <button class="btn btn-secondary btn-sm" onclick="openEditQuestionModal('${q._id}')" title="Edit">
                        ✏️ Edit
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="handleDeleteQuestion('${q._id}')" title="Delete">
                        🗑️
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

function openAddQuestionModal() {
    document.getElementById('question-modal-title').textContent = 'Add New Question';
    document.getElementById('edit-question-id').value = '';
    document.getElementById('question-form').reset();
    document.getElementById('q-marks').value = 5;
    document.getElementById('q-timer').value = 30;
    document.getElementById('question-modal').classList.add('active');
}

function openEditQuestionModal(qId) {
    const q = allQuestions.find(item => item._id === qId);
    if (!q) return;

    document.getElementById('question-modal-title').textContent = 'Edit Question';
    document.getElementById('edit-question-id').value = q._id;
    document.getElementById('q-text').value = q.question_text || '';
    
    const opts = q.options || {};
    document.getElementById('opt-a').value = opts.A || '';
    document.getElementById('opt-b').value = opts.B || '';
    document.getElementById('opt-c').value = opts.C || '';
    document.getElementById('opt-d').value = opts.D || '';
    
    document.getElementById('correct-opt').value = q.correct_answer || 'A';
    document.getElementById('q-marks').value = q.marks || 5;
    document.getElementById('q-timer').value = q.time_limit || 30;

    document.getElementById('question-modal').classList.add('active');
}

function closeQuestionModal() {
    document.getElementById('question-modal').classList.remove('active');
}

async function handleSaveQuestion(e) {
    e.preventDefault();
    const qId = document.getElementById('edit-question-id').value;
    const saveBtn = document.getElementById('save-question-btn');

    const payload = {
        question_text: document.getElementById('q-text').value.trim(),
        options: {
            A: document.getElementById('opt-a').value.trim(),
            B: document.getElementById('opt-b').value.trim(),
            C: document.getElementById('opt-c').value.trim(),
            D: document.getElementById('opt-d').value.trim()
        },
        correct_answer: document.getElementById('correct-opt').value,
        marks: parseInt(document.getElementById('q-marks').value) || 1,
        time_limit: parseInt(document.getElementById('q-timer').value) || 30
    };

    saveBtn.disabled = true;
    saveBtn.textContent = 'Saving...';

    try {
        if (qId) {
            // Update
            await apiRequest(`/api/admin/questions/${qId}`, {
                method: 'PUT',
                body: payload
            });
            showToast('Question updated successfully', 'success');
        } else {
            // Create
            await apiRequest('/api/admin/questions', {
                method: 'POST',
                body: payload
            });
            showToast('New question added successfully', 'success');
        }

        closeQuestionModal();
        await loadAdminQuestions();
        await loadDashboardStats();
    } catch (err) {
        showToast(err.message || 'Failed to save question', 'error');
    } finally {
        saveBtn.disabled = false;
        saveBtn.textContent = 'Save Question';
    }
}

async function handleDeleteQuestion(qId) {
    if (!confirm('Are you sure you want to delete this question? This action cannot be undone.')) {
        return;
    }

    try {
        await apiRequest(`/api/admin/questions/${qId}`, { method: 'DELETE' });
        showToast('Question deleted successfully', 'success');
        await loadAdminQuestions();
        await loadDashboardStats();
    } catch (err) {
        showToast(err.message || 'Failed to delete question', 'error');
    }
}


// ==========================================
// QUIZ SETTINGS
// ==========================================

async function loadAdminSettings() {
    try {
        const res = await apiRequest('/api/admin/settings');
        currentSettings = res.data;

        document.getElementById('settings-title').value = currentSettings.quiz_title || '';
        document.getElementById('settings-status').value = currentSettings.quiz_status || 'active';
        document.getElementById('settings-duration').value = currentSettings.total_duration || 15;
        document.getElementById('settings-pass-percent').value = currentSettings.pass_percentage || 50;
        document.getElementById('settings-instructions').value = currentSettings.instructions || '';
    } catch (err) {
        showToast('Failed to load settings: ' + err.message, 'error');
    }
}

async function handleSaveSettings(e) {
    e.preventDefault();
    const payload = {
        quiz_title: document.getElementById('settings-title').value.trim(),
        quiz_status: document.getElementById('settings-status').value,
        total_duration: parseInt(document.getElementById('settings-duration').value) || 15,
        pass_percentage: parseInt(document.getElementById('settings-pass-percent').value) || 50,
        instructions: document.getElementById('settings-instructions').value.trim()
    };

    try {
        await apiRequest('/api/admin/settings', {
            method: 'POST',
            body: payload
        });
        showToast('Quiz settings saved successfully!', 'success');
        await loadDashboardStats();
    } catch (err) {
        showToast(err.message || 'Failed to save settings', 'error');
    }
}

async function quickUpdateQuizStatus(newStatus) {
    try {
        await apiRequest('/api/admin/settings', {
            method: 'POST',
            body: { quiz_status: newStatus }
        });
        showToast(`Quiz status changed to ${newStatus.toUpperCase()}`, 'success');
        await loadDashboardStats();
        if (currentSettings) {
            currentSettings.quiz_status = newStatus;
            document.getElementById('settings-status').value = newStatus;
        }
    } catch (err) {
        showToast(err.message || 'Failed to update status', 'error');
    }
}


// ==========================================
// RESULTS & STUDENT BREAKDOWN
// ==========================================

async function loadAdminResults() {
    try {
        const res = await apiRequest('/api/admin/results');
        allResults = res.data || [];

        document.getElementById('tab-results-count').textContent = allResults.length;
        renderResultsTable(allResults);
    } catch (err) {
        showToast('Failed to load results: ' + err.message, 'error');
    }
}

function filterResultsTable() {
    const q = (document.getElementById('results-search-input').value || '').trim().toLowerCase();
    if (!q) {
        renderResultsTable(allResults);
        return;
    }
    const filtered = allResults.filter(item => 
        (item.student_name || '').toLowerCase().includes(q) ||
        (item.register_number || '').toLowerCase().includes(q)
    );
    renderResultsTable(filtered);
}

function renderResultsTable(results) {
    const tbody = document.getElementById('results-table-body');
    if (!results || results.length === 0) {
        tbody.innerHTML = `
            <tr>
                <td colspan="11" style="text-align: center; color: var(--text-muted); padding: 3rem;">
                    No student submissions recorded yet.
                </td>
            </tr>
        `;
        return;
    }

    tbody.innerHTML = results.map(r => {
        const timeStr = r.submission_time ? new Date(r.submission_time).toLocaleString() : 'In Progress';
        const isPassed = (r.percentage || 0) >= 50;

        return `
            <tr>
                <td><strong>${escapeHtml(r.student_name || 'Anonymous')}</strong></td>
                <td><code style="font-weight: 700; color: var(--secondary);">${escapeHtml(r.register_number || '-')}</code></td>
                <td>${r.total_questions || '-'}</td>
                <td><span style="color: var(--success); font-weight: 700;">${r.correct_count ?? 0}</span></td>
                <td><span style="color: var(--danger); font-weight: 700;">${r.wrong_count ?? 0}</span></td>
                <td><span style="color: var(--warning); font-weight: 700;">${r.unanswered_count ?? 0}</span></td>
                <td><strong>${r.score ?? 0}</strong> / ${r.total_marks ?? 0}</td>
                <td>
                    <span class="badge ${isPassed ? 'badge-success' : 'badge-danger'}">
                        ${r.percentage ?? 0}%
                    </span>
                </td>
                <td>
                    <span class="badge ${r.status === 'completed' ? 'badge-success' : 'badge-warning'}">
                        ${r.status || 'in_progress'}
                    </span>
                </td>
                <td style="font-size: 0.8rem; color: var(--text-secondary);">${timeStr}</td>
                <td style="text-align: right;">
                    <button class="btn btn-secondary btn-sm" onclick="viewResultDetail('${r._id}')">
                        🔍 Inspect
                    </button>
                    <button class="btn btn-outline-danger btn-sm" onclick="handleDeleteResult('${r._id}')" title="Delete Attempt">
                        🗑️
                    </button>
                </td>
            </tr>
        `;
    }).join('');
}

async function viewResultDetail(attemptId) {
    try {
        const res = await apiRequest(`/api/admin/results/${attemptId}`);
        const attempt = res.data;

        const headerBox = document.getElementById('result-detail-header');
        headerBox.innerHTML = `
            <div style="display: flex; justify-content: space-between; flex-wrap: wrap; gap: 1rem; align-items: center;">
                <div>
                    <h3 style="font-size: 1.25rem; font-weight: 800; margin-bottom: 0.25rem;">${escapeHtml(attempt.student_name)}</h3>
                    <div style="font-size: 0.9rem; color: var(--text-secondary);">Register Number: <strong>${escapeHtml(attempt.register_number)}</strong></div>
                </div>
                <div style="text-align: right;">
                    <div style="font-size: 1.5rem; font-weight: 800; color: var(--primary);">${attempt.score} / ${attempt.total_marks} pts</div>
                    <span class="badge ${attempt.percentage >= 50 ? 'badge-success' : 'badge-danger'}">${attempt.percentage}% - ${attempt.percentage >= 50 ? 'Passed' : 'Failed'}</span>
                </div>
            </div>
            <div style="display: flex; gap: 1.5rem; margin-top: 1rem; font-size: 0.85rem; border-top: 1px solid var(--border-color); padding-top: 0.75rem;">
                <span>Total Qs: <strong>${attempt.total_questions}</strong></span>
                <span style="color: var(--success);">Correct: <strong>${attempt.correct_count}</strong></span>
                <span style="color: var(--danger);">Wrong: <strong>${attempt.wrong_count}</strong></span>
                <span style="color: var(--warning);">Unanswered: <strong>${attempt.unanswered_count}</strong></span>
            </div>
        `;

        const list = document.getElementById('result-detail-list');
        const details = attempt.detailed_results || [];

        if (details.length === 0) {
            list.innerHTML = `<div style="color: var(--text-muted);">No question details recorded for this attempt.</div>`;
        } else {
            list.innerHTML = details.map((d, i) => {
                let badge = '';
                if (!d.student_answer) {
                    badge = `<span class="badge badge-warning">Unanswered</span>`;
                } else if (d.is_correct) {
                    badge = `<span class="badge badge-success">✓ Correct (+${d.marks} pts)</span>`;
                } else {
                    badge = `<span class="badge badge-danger">✕ Incorrect (0 pts)</span>`;
                }

                return `
                    <div style="background: var(--bg-surface); border: 1px solid var(--border-color); border-radius: var(--radius-sm); padding: 1.15rem;">
                        <div style="display: flex; justify-content: space-between; align-items: start; margin-bottom: 0.65rem;">
                            <strong>Q${i + 1}: ${escapeHtml(d.question_text)}</strong>
                            ${badge}
                        </div>
                        <div style="font-size: 0.88rem; display: flex; flex-direction: column; gap: 0.35rem;">
                            <div>Student Answer: <strong style="${d.is_correct ? 'color: var(--success);' : 'color: var(--danger);'}">${d.student_answer ? `Option ${d.student_answer}` : 'None'}</strong></div>
                            <div>Correct Answer: <strong style="color: var(--success);">Option ${d.correct_answer}</strong></div>
                        </div>
                    </div>
                `;
            }).join('');
        }

        document.getElementById('result-detail-modal').classList.add('active');
    } catch (err) {
        showToast('Failed to load result breakdown: ' + err.message, 'error');
    }
}

function closeResultDetailModal() {
    document.getElementById('result-detail-modal').classList.remove('active');
}

async function handleDeleteResult(attemptId) {
    if (!confirm('Are you sure you want to delete this result? The student will be allowed to retake if quiz is active.')) {
        return;
    }
    try {
        await apiRequest(`/api/admin/results/${attemptId}`, { method: 'DELETE' });
        showToast('Attempt removed successfully', 'success');
        await loadAdminResults();
        await loadDashboardStats();
    } catch (err) {
        showToast(err.message || 'Failed to delete result', 'error');
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
