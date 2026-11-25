/**
 * Online Quiz Management System - API Configuration & Utilities
 */

const CONFIG = {
    // Default Backend URL: auto-detects localhost or uses stored/fallback Render URL
    DEFAULT_API_URL: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1'
        ? (window.location.port === '5000' ? '' : 'http://127.0.0.1:5000')
        : (localStorage.getItem('QUIZ_API_URL') || 'https://online-quiz-backend.onrender.com'),
        
    getApiUrl() {
        return localStorage.getItem('QUIZ_API_URL') || this.DEFAULT_API_URL;
    },
    
    setApiUrl(url) {
        if (!url) {
            localStorage.removeItem('QUIZ_API_URL');
        } else {
            let cleanUrl = url.trim().replace(/\/+$/, '');
            localStorage.setItem('QUIZ_API_URL', cleanUrl);
        }
    }
};

/**
 * Robust API helper with token management and friendly error handling
 */
async function apiRequest(endpoint, options = {}) {
    const baseUrl = CONFIG.getApiUrl();
    const url = endpoint.startsWith('http') ? endpoint : `${baseUrl}${endpoint.startsWith('/') ? '' : '/'}${endpoint}`;
    
    const headers = {
        'Content-Type': 'application/json',
        ...(options.headers || {})
    };

    // Attach Admin Token if available
    const adminToken = localStorage.getItem('admin_token');
    if (adminToken && !headers['Authorization']) {
        headers['Authorization'] = `Bearer ${adminToken}`;
    }

    const config = {
        method: options.method || 'GET',
        headers: headers,
        ...(options.body ? { body: JSON.stringify(options.body) } : {})
    };

    try {
        const response = await fetch(url, config);
        const data = await response.json().catch(() => ({
            status: 'error',
            message: `Server returned HTTP ${response.status}`
        }));

        if (!response.ok) {
            // Handle Unauthorized Admin
            if (response.status === 401 && window.location.pathname.includes('admin.html')) {
                localStorage.removeItem('admin_token');
                localStorage.removeItem('admin_user');
            }
            throw new Error(data.message || `Request failed with status ${response.status}`);
        }

        return data;
    } catch (err) {
        console.error(`API Error [${endpoint}]:`, err);
        throw err;
    }
}

/**
 * Toast Notification system
 */
function showToast(message, type = 'info', duration = 3500) {
    let container = document.getElementById('toast-container');
    if (!container) {
        container = document.createElement('div');
        container.id = 'toast-container';
        container.className = 'toast-container';
        document.body.appendChild(container);
    }

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    
    const iconMap = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };
    
    toast.innerHTML = `
        <span class="toast-icon">${iconMap[type] || 'ℹ'}</span>
        <div class="toast-message">${message}</div>
        <button class="toast-close" onclick="this.parentElement.remove()">&times;</button>
    `;

    container.appendChild(toast);
    
    setTimeout(() => {
        toast.classList.add('show');
    }, 10);

    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, duration);
}

// Global Theme Manager (Dark / Light)
function initTheme() {
    const saved = localStorage.getItem('theme') || 'dark';
    document.documentElement.setAttribute('data-theme', saved);
}

function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') || 'dark';
    const next = current === 'dark' ? 'light' : 'dark';
    document.documentElement.setAttribute('data-theme', next);
    localStorage.setItem('theme', next);
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        themeBtn.innerHTML = next === 'dark' ? '🌙' : '☀️';
    }
}

document.addEventListener('DOMContentLoaded', () => {
    initTheme();
    const themeBtn = document.getElementById('theme-toggle-btn');
    if (themeBtn) {
        const current = document.documentElement.getAttribute('data-theme') || 'dark';
        themeBtn.innerHTML = current === 'dark' ? '🌙' : '☀️';
        themeBtn.addEventListener('click', toggleTheme);
    }
});
