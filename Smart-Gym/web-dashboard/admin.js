/**
 * GymOS HQ Admin Controller V3.0
 */

// The BACKEND_URL dynamically resolves based on the browser's current address
const BACKEND_URL = `http://${window.location.hostname}:8080`;

const CONFIG = {
    BACKEND_URL: `${BACKEND_URL}/dashboard`,
    BASE_API_URL: BACKEND_URL,
    POLL_INTERVAL: 3000
};

const token = localStorage.getItem('gymAdminToken');

// --- Auth Protection ---
if (!token && !window.location.href.includes('admin-login.html')) {
    window.location.href = "admin-login.html";
}

function getHeaders() {
    return {
        'Content-Type': 'application/json',
        'Authorization': `Bearer ${token}`
    };
}

function logout() {
    localStorage.removeItem('gymAdminToken');
    window.location.href = "admin-login.html";
}

// --- Data Fetching ---
async function fetchAdminData() {
    try {
        const response = await fetch(`${CONFIG.BACKEND_URL}/admin/dashboard`, {
            headers: getHeaders()
        });
        
        if (response.status === 401 || response.status === 403) {
            logout();
            return;
        }

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();
        updateUI(data);
    } catch (error) {
        console.error("Admin Terminal Error:", error);
        // Show network issue in UI
        const stats = document.getElementById('admin-stats');
        if (stats) stats.style.opacity = "0.5";
    }
}

function updateUI(data) {
    document.getElementById('admin-stats').style.opacity = "1";

    // Update Intelligence Matrix
    document.getElementById('stat-total-members').innerText = data.stats.member_count;
    document.getElementById('stat-active-now').innerText = data.stats.active_sessions;
    document.getElementById('stat-logs').innerText = data.recent_access_logs.length;
    document.getElementById('stat-machines').innerText = data.stats.active_sessions;

    // Personnel Directory
    const memberList = document.getElementById('member-list');
    memberList.innerHTML = data.members.map(m => `
        <div class="list-item">
            <div>
                <div style="font-weight: 700; font-size: 1rem; color: var(--text-main);">${m.full_name}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">
                    RFID: <span style="font-family: monospace;">${m.rfid_uid || 'None'}</span> • ${m.membership_plan}
                </div>
            </div>
            <div style="display: flex; align-items: center; gap: 16px;">
                <span class="badge ${m.membership_status === 'active' ? 'badge-success' : 'badge-danger'}">
                    ${m.membership_status}
                </span>
                <button class="btn btn-danger" style="padding: 6px 12px; font-size: 0.75rem;" onclick="confirmDelete(${m.id}, '${m.full_name}')">Delete</button>
            </div>
        </div>
    `).join('');

    // Security Perimeter Logs
    const logList = document.getElementById('access-logs');
    logList.innerHTML = data.recent_access_logs.map(log => `
        <div class="list-item" style="border-left: 3px solid ${log.granted ? 'var(--success)' : 'var(--danger)'};">
            <div style="padding-left: 12px;">
                <div style="font-weight: 700; font-size: 0.9rem;">${log.member_name}</div>
                <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 4px;">${log.reason}</div>
            </div>
            <div style="text-align: right;">
                <div class="badge ${log.granted ? 'badge-success' : 'badge-danger'}" style="font-size: 0.65rem;">${log.granted ? 'Granted' : 'Denied'}</div>
                <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 8px; font-family: monospace;">${formatTime(log.created_at)}</div>
            </div>
        </div>
    `).join('');

    // IoT Node Status
    const sessionsDiv = document.getElementById('active-sessions-table');
    if (data.active_sessions.length === 0) {
        sessionsDiv.innerHTML = '<div style="padding: 40px; color: var(--text-muted); text-align: center;">No machines are currently in use.</div>';
    } else {
        sessionsDiv.innerHTML = `
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--border-light); color: var(--text-muted); font-size: 0.75rem; text-transform: uppercase; font-weight: 600;">
                        <th style="padding: 16px 8px;">Member</th>
                        <th style="padding: 16px 8px;">Machine</th>
                        <th style="padding: 16px 8px;">Started At</th>
                        <th style="padding: 16px 8px; text-align: right;">Reps</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.active_sessions.map(s => `
                        <tr style="border-bottom: 1px solid var(--border-light); transition: 0.2s;">
                            <td style="padding: 16px 8px; font-weight: 700;">${s.member_name}</td>
                            <td style="padding: 16px 8px; font-size: 0.85rem; color: var(--text-muted);">${s.machine_name}</td>
                            <td style="padding: 16px 8px; font-size: 0.85rem; color: var(--text-muted); font-family: monospace;">${formatTime(s.started_at)}</td>
                            <td style="padding: 16px 8px; text-align: right; color: var(--accent-primary); font-family: 'Outfit'; font-weight: 800; font-size: 1.2rem;">${s.total_reps}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }
}

function formatTime(iso) {
    if (!iso) return "--:--";
    const d = new Date(iso + (iso.endsWith('Z') ? '' : 'Z'));
    return d.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

// --- Personnel Actions ---
function showAddModal() { document.getElementById('add-modal').style.display = 'flex'; }
function hideAddModal() { document.getElementById('add-modal').style.display = 'none'; }

async function addMember() {
    const payload = {
        full_name: document.getElementById('new-name').value,
        email: document.getElementById('new-email').value,
        rfid_uid: document.getElementById('new-rfid').value,
        username: document.getElementById('new-user').value,
        password: document.getElementById('new-pass').value,
        membership_status: "active",
        membership_plan: "Monthly"
    };

    if (!payload.full_name || !payload.rfid_uid) {
        alert("Please provide both Name and RFID.");
        return;
    }

    try {
        const response = await fetch(`${CONFIG.BASE_API_URL}/members`, {
            method: 'POST',
            headers: getHeaders(),
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const err = await response.json();
            alert(`Error: ${err.detail}`);
            return;
        }

        hideAddModal();
        fetchAdminData();
    } catch (error) {
        alert("Network error. Please try again.");
    }
}

async function confirmDelete(id, name) {
    if (confirm(`Are you sure you want to remove ${name}?`)) {
        try {
            const response = await fetch(`${CONFIG.BASE_API_URL}/members/${id}`, {
                method: 'DELETE',
                headers: getHeaders()
            });
            if (response.ok) fetchAdminData();
        } catch (error) {
            alert("Failed to delete member.");
        }
    }
}

async function handleManualEntrance() {
    const rfidInput = document.getElementById("manual-entrance-rfid");
    const uid = rfidInput.value.trim().toUpperCase();
    if (!uid) return;
    
    try {
        const response = await fetch(`${CONFIG.BASE_API_URL}/entry-log`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rfid_uid: uid })
        });
        
        if (response.ok) {
            rfidInput.value = "";
            fetchAdminData();
        } else {
            alert("Access Denied for UID " + uid);
        }
    } catch (e) {
        alert("Network error.");
    }
}

// Initial Sync & Polling
fetchAdminData();
setInterval(fetchAdminData, CONFIG.POLL_INTERVAL);
