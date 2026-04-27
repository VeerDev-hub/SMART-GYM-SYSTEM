        const BACKEND_URL = `http://${window.location.hostname}:8080`;

// --- AUTH PROTECTION ---
const userToken = localStorage.getItem('gymUserToken');
if (!userToken) {
    window.location.href = "user-login.html";
}

function userLogout() {
    localStorage.removeItem('gymUserToken');
    localStorage.removeItem('gymMemberId');
    window.location.href = "user-login.html";
}

async function fetchUserHistory() {
    try {
        const response = await fetch(`${BACKEND_URL}/dashboard/user/dashboard`, {
            headers: { 'Authorization': `Bearer ${userToken}` }
        });
        
        if (response.status === 401) {
            userLogout();
            return;
        }

        const data = await response.json();
        updateUserUI(data);
    } catch (error) {
        console.error("Failed to fetch user history:", error);
    }
}

function updateUserUI(data) {
    // Header
    document.getElementById('user-name-title').innerText = data.member.full_name;
    
    // Stats Summary
    document.getElementById('total-visits').innerText = data.summary.total_visits;
    document.getElementById('total-reps').innerText = data.sessions.reduce((acc, s) => acc + s.total_reps, 0);
    
    const avgScore = data.sessions.length > 0 
        ? Math.round(data.sessions.reduce((acc, s) => acc + (s.form_score || 0), 0) / data.sessions.length)
        : 0;
    document.getElementById('avg-form').innerText = `${avgScore}%`;
    document.getElementById('member-status').innerText = data.member.membership_status.toUpperCase();

    // History List
    const historyList = document.getElementById('history-list');
    if (data.sessions.length === 0) {
        historyList.innerHTML = `
            <div style="padding: 40px; text-align: center; color: var(--text-muted); border: 1px dashed var(--border); border-radius: var(--radius-lg);">
                <div style="font-size: 2rem; margin-bottom: 8px;">🏋️</div>
                <div style="font-weight: 600; color: var(--text-main);">No workouts recorded yet</div>
                <div>Time to hit the gym and start your first session!</div>
            </div>`;
        return;
    }

    historyList.innerHTML = data.sessions.map(s => `
        <div class="metric-card" style="display: flex; flex-direction: row; justify-content: space-between; align-items: center; padding: 20px; margin-bottom: 10px;">
            <div>
                <h3 style="font-size: 1.1rem; font-weight: 700; margin-bottom: 4px;">${s.machine_name.replaceAll('_', ' ').toUpperCase()}</h3>
                <div class="text-sm text-muted" style="margin-bottom: 12px;">
                    ${new Date(s.started_at + (s.started_at.endsWith('Z') ? '' : 'Z')).toLocaleString([], { weekday: 'short', year: 'numeric', month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit' })}
                </div>
                <span class="badge ${s.fatigue_level === 'High' ? 'badge-danger' : 'badge-success'}">
                    ${s.fatigue_level || 'Normal'} Fatigue
                </span>
            </div>
            
            <div style="display: flex; gap: 32px; text-align: center;">
                <div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: var(--accent);">${s.total_reps}</div>
                    <div class="text-sm text-muted" style="font-weight: 600; text-transform: uppercase;">Reps</div>
                </div>
                <div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: var(--accent);">${s.form_score || 0}%</div>
                    <div class="text-sm text-muted" style="font-weight: 600; text-transform: uppercase;">Form</div>
                </div>
                <div>
                    <div style="font-size: 1.5rem; font-weight: 800; color: var(--accent);">${Math.round(s.duration_ms / 60000)}m</div>
                    <div class="text-sm text-muted" style="font-weight: 600; text-transform: uppercase;">Time</div>
                </div>
            </div>
        </div>
    `).join('');
}

// Initial fetch
fetchUserHistory();
