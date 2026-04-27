/**
 * GymOS User Journey Controller V3.0
 */

// The BACKEND_URL is automatically updated by run.py
        const BACKEND_URL = "http://10.44.152.238:8080";

const CONFIG = {
    BACKEND_URL: `${BACKEND_URL}/dashboard`
};

const token = localStorage.getItem('gymUserToken');

// --- Auth Protection ---
if (!token) {
    window.location.href = "user-login.html";
}

function userLogout() {
    localStorage.removeItem('gymUserToken');
    window.location.href = "user-login.html";
}

async function fetchUserData() {
    try {
        const response = await fetch(`${CONFIG.BACKEND_URL}/user/dashboard`, {
            headers: { 'Authorization': `Bearer ${token}` }
        });
        
        if (response.status === 401) {
            userLogout();
            return;
        }

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        renderDashboard(data);
    } catch (err) {
        console.error("Sync Error:", err);
    }
}

function renderDashboard(data) {
    const { member, summary, sessions } = data;

    // Personnel Data
    document.getElementById('user-name-title').innerText = member.full_name;
    document.getElementById('user-avatar-small').innerText = member.full_name.charAt(0);
    
    document.getElementById('total-visits').innerText = summary.total_visits;
    document.getElementById('member-status').innerText = member.membership_status;
    
    // Performance Metrics
    const lifetimeReps = sessions.reduce((acc, s) => acc + (s.total_reps || 0), 0);
    document.getElementById('total-reps').innerText = lifetimeReps;

    const formScores = sessions.filter(s => s.form_score != null).map(s => s.form_score);
    const avgForm = formScores.length > 0 
        ? Math.round(formScores.reduce((a, b) => a + b, 0) / formScores.length) + "%"
        : "N/A";
    document.getElementById('avg-form').innerText = avgForm;

    // Timeline Rendering
    const list = document.getElementById('history-list');
    if (sessions.length === 0) {
        list.innerHTML = '<div style="padding: 80px; text-align: center; color: var(--text-muted);">No workouts recorded yet. Time to hit the gym!</div>';
        return;
    }

    list.innerHTML = sessions.map(s => `
        <div class="list-item" style="padding: 32px;">
            <div style="flex: 1;">
                <div style="font-weight: 800; font-size: 1.25rem; color: var(--text-main); font-family: 'Outfit';">${s.machine_name.replace('_', ' ')}</div>
                <div style="font-size: 0.85rem; color: var(--text-muted); margin-top: 4px;">
                    ${new Date(s.started_at).toLocaleDateString()} at ${new Date(s.started_at).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'})}
                </div>
                ${s.insight ? `<div style="margin-top: 16px; color: var(--text-main); font-size: 0.9rem; background: var(--bg-input); padding: 16px; border-radius: var(--radius-sm); border-left: 3px solid var(--accent-primary); line-height: 1.5;">${s.insight}</div>` : ''}
            </div>
            <div style="text-align: right; min-width: 150px; display: flex; flex-direction: column; align-items: flex-end;">
                <div style="font-family: 'Outfit'; font-weight: 900; font-size: 2.5rem; color: var(--accent-primary); line-height: 1;">${s.total_reps}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted); text-transform: uppercase; font-weight: 700; letter-spacing: 0.5px; margin-top: 4px;">Total Reps</div>
                <div class="badge ${getFormClass(s.form_score)}" style="margin-top: 16px;">
                    Form Score: ${s.form_score ? s.form_score + '%' : 'N/A'}
                </div>
            </div>
        </div>
    `).join('');
}

function getFormClass(score) {
    if (!score) return 'badge-neutral';
    if (score >= 90) return 'badge-success';
    if (score >= 70) return 'badge-neutral'; // Neutral styling for okay form
    return 'badge-danger';
}

// Start Intelligence Sync
fetchUserData();
setInterval(fetchUserData, 10000);
