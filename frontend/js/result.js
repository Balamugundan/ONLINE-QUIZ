/**
 * Online Quiz Management System - Result Summary Logic
 */

document.addEventListener('DOMContentLoaded', async () => {
    const params = new URLSearchParams(window.location.search);
    const attemptId = params.get('attempt_id') || sessionStorage.getItem('quiz_completed_attempt_id');

    if (!attemptId) {
        showToast('No quiz attempt identified. Redirecting...', 'warning');
        setTimeout(() => { window.location.href = 'index.html'; }, 2000);
        return;
    }

    // Check cached summary first
    const cached = sessionStorage.getItem('quiz_result_summary');
    if (cached) {
        try {
            const data = JSON.parse(cached);
            if (data.attempt_id === attemptId) {
                renderResultData(data);
            }
        } catch {}
    }

    // Always fetch fresh authoritative result from Backend
    try {
        const res = await apiRequest(`/api/quiz/result/${attemptId}`);
        renderResultData(res.data);
    } catch (err) {
        if (!cached) {
            document.getElementById('result-loading').innerHTML = `
                <div style="color: var(--danger); font-size: 3rem;">⚠️</div>
                <h2>Unable to Load Quiz Result</h2>
                <p style="color: var(--text-secondary); margin-bottom: 1.5rem;">${err.message || 'Result record not found'}</p>
                <a href="index.html" class="btn btn-primary">Back to Home</a>
            `;
        }
    }
});

function renderResultData(result) {
    document.getElementById('result-loading').style.display = 'none';
    const card = document.getElementById('result-card');
    card.style.display = 'block';

    document.getElementById('res-student-name').textContent = result.student_name || 'Student';
    document.getElementById('res-student-reg').textContent = result.register_number || '-';

    document.getElementById('res-score').textContent = result.score ?? 0;
    document.getElementById('res-total-marks').textContent = `out of ${result.total_marks ?? 0} pts`;

    document.getElementById('res-total-q').textContent = result.total_questions ?? 0;
    document.getElementById('res-correct').textContent = result.correct_answers ?? 0;
    document.getElementById('res-wrong').textContent = result.wrong_answers ?? 0;
    document.getElementById('res-unanswered').textContent = result.unanswered_questions ?? 0;
    document.getElementById('res-percentage').textContent = `${result.percentage ?? 0}%`;

    // Performance Badge
    const pct = parseFloat(result.percentage) || 0;
    const badge = document.getElementById('res-performance-badge');
    const icon = document.getElementById('celebration-icon');
    const circle = document.getElementById('score-circle');

    if (pct >= 75) {
        badge.className = 'badge badge-success';
        badge.textContent = '🌟 Passed with Distinction';
        icon.textContent = '🏆';
        circle.style.borderColor = 'var(--success)';
        circle.style.boxShadow = '0 0 35px rgba(16, 185, 129, 0.4)';
    } else if (pct >= 50) {
        badge.className = 'badge badge-primary';
        badge.textContent = '✓ Successfully Passed';
        icon.textContent = '🎉';
        circle.style.borderColor = 'var(--primary)';
        circle.style.boxShadow = '0 0 35px rgba(99, 102, 241, 0.4)';
    } else {
        badge.className = 'badge badge-danger';
        badge.textContent = 'Needs Improvement';
        icon.textContent = '📚';
        circle.style.borderColor = 'var(--danger)';
        circle.style.boxShadow = '0 0 35px rgba(239, 68, 68, 0.4)';
    }

    // Submission Metadata
    const isAuto = result.status === 'auto_submitted';
    document.getElementById('res-submission-mode').textContent = isAuto ? 'Auto-Submitted (Timer Expired)' : 'Candidate Submitted';
    
    if (result.submission_time) {
        document.getElementById('res-submission-time').textContent = new Date(result.submission_time).toLocaleString();
    } else {
        document.getElementById('res-submission-time').textContent = 'Just now';
    }
}
