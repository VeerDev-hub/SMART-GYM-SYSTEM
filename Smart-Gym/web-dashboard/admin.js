const BACKEND_URL = `http://${window.location.hostname}:8080`;

// --- AUTH PROTECTION ---
const token = localStorage.getItem('gymAdminToken');
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

// --- DATA FETCHING ---
async function fetchAdminData() {
    try {
        const response = await fetch(`${BACKEND_URL}/dashboard/admin/dashboard`, {
            headers: getHeaders()
        });
        
        if (response.status === 401 || response.status === 403) {
            logout();
            return;
        }

        const data = await response.json();
        updateUI(data);
    } catch (error) {
        console.error("Failed to fetch admin data:", error);
    }
}

function updateUI(data) {
    // Stats
    document.getElementById('stat-total-members').innerText = data.stats.member_count;
    document.getElementById('stat-active-now').innerText = data.stats.active_memberships;
    document.getElementById('stat-logs').innerText = data.recent_access_logs.length;
    document.getElementById('stat-machines').innerText = data.stats.active_sessions;

    // Member Directory
    const memberList = document.getElementById('member-list');
    memberList.innerHTML = data.members.map(m => `
        <div class="list-item">
            <div>
                <div style="font-weight: 600;">${m.full_name}</div>
                <div class="text-sm text-muted">RFID: ${m.rfid_uid || 'None'}</div>
            </div>
            <div style="display: flex; align-items: center; gap: 12px;">
                <span class="badge ${m.membership_status === 'active' ? 'badge-success' : 'badge-neutral'}">
                    ${m.membership_status}
                </span>
                <button class="btn btn-danger" style="padding: 6px 10px; font-size: 0.8rem;" onclick="confirmDelete(${m.id}, '${m.full_name}')">Delete</button>
            </div>
        </div>
    `).join('');

    // Access Logs
    const logList = document.getElementById('access-logs');
    logList.innerHTML = data.recent_access_logs.map(log => `
        <div class="list-item" style="border-left: 3px solid ${log.granted ? 'var(--success)' : 'var(--danger)'};">
            <div>
                <div style="font-weight: 600;">${log.member_name}</div>
                <div class="text-sm text-muted">${log.reason}</div>
            </div>
            <div style="text-align: right;">
                <div class="badge ${log.granted ? 'badge-success' : 'badge-danger'}">${log.granted ? 'GRANTED' : 'DENIED'}</div>
                <div class="text-sm text-muted" style="margin-top: 4px;">${new Date(log.created_at + (log.created_at.endsWith('Z') ? '' : 'Z')).toLocaleTimeString()}</div>
            </div>
        </div>
    `).join('');

    // Active Sessions
    const sessionsDiv = document.getElementById('active-sessions-table');
    if (data.active_sessions.length === 0) {
        sessionsDiv.innerHTML = '<div style="padding: 20px; color: var(--text-muted); text-align: center;">No active sessions on machines.</div>';
    } else {
        sessionsDiv.innerHTML = `
            <table style="width: 100%; border-collapse: collapse; text-align: left;">
                <thead>
                    <tr style="border-bottom: 1px solid var(--border); color: var(--text-muted); font-size: 0.85rem;">
                        <th style="padding: 12px;">Member</th>
                        <th style="padding: 12px;">Machine</th>
                        <th style="padding: 12px;">Started</th>
                        <th style="padding: 12px; text-align: right;">Reps</th>
                    </tr>
                </thead>
                <tbody>
                    ${data.active_sessions.map(s => `
                        <tr style="border-bottom: 1px solid var(--border);">
                            <td style="padding: 12px; font-weight: 600;">${s.member_name}</td>
                            <td style="padding: 12px;" class="text-muted">${s.machine_name}</td>
                            <td style="padding: 12px;" class="text-muted">${new Date(s.started_at + (s.started_at.endsWith('Z') ? '' : 'Z')).toLocaleTimeString()}</td>
                            <td style="padding: 12px; text-align: right; color: var(--accent); font-weight: 700; font-size: 1.1rem;">${s.total_reps}</td>
                        </tr>
                    `).join('')}
                </tbody>
            </table>
        `;
    }
}

// --- MEMBER ACTIONS ---
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

    try {
        const response = await fetch(`${BACKEND_URL}/members`, {
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
        alert("Failed to add member.");
    }
}

async function confirmDelete(id, name) {
    if (confirm(`Are you sure you want to delete ${name}? This will remove all their history.`)) {
        try {
            const response = await fetch(`${BACKEND_URL}/members/${id}`, {
                method: 'DELETE',
                headers: getHeaders()
            });
            if (response.ok) fetchAdminData();
        } catch (error) {
            alert("Delete failed.");
        }
    }
}

async function handleManualEntrance() {
    const rfidInput = document.getElementById("manual-entrance-rfid");
    const uid = rfidInput.value.trim().toUpperCase();
    if (!uid) {
        alert("Please enter a valid HEX code.");
        return;
    }
    
    try {
        const response = await fetch(`${BACKEND_URL}/entry-log`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ rfid_uid: uid })
        });
        
        if (response.ok) {
            rfidInput.value = "";
            fetchAdminData();
        } else {
            alert("Entrance log failed. Invalid RFID?");
        }
    } catch (e) {
        console.error(e);
        alert("Network error logging entrance.");
    }
}

// Initial fetch and poll
fetchAdminData();
setInterval(fetchAdminData, 2000);
