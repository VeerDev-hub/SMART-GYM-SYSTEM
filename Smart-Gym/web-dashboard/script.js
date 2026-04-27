/**
 * Smart Gym Intelligence Dashboard - Frontend Controller V2.0
 * Handles real-time telemetry, AI vision feedback, and session management.
 */

// --- Configuration & State ---
// The BACKEND_URL dynamically resolves based on the browser's current address
const BACKEND_URL = `http://${window.location.hostname}:8080`;

const CONFIG = {
    BACKEND_URL: BACKEND_URL,
    POLL_INTERVAL: 250,
    CHART_POINTS: 20,
    ROM_CALIBRATION: { max: 72, min: 65 }
};

window.addEventListener('error', function(e) {
    const errorBanner = document.getElementById('global-error-banner');
    const errorMessage = document.getElementById('error-message');
    if (errorBanner && errorMessage) {
        errorBanner.style.display = 'flex';
        errorMessage.innerText = "JS Error: " + e.message;
    }
});

let state = {
    chart: null,
    lastRepCount: 0,
    lastRepTime: Date.now(),
    currentExercise: null,
    isOffline: false,
    isPreparing: false,
    auth: JSON.parse(localStorage.getItem('smartGymAutoLogin') || '{}')
};

// --- Initialization ---
document.addEventListener('DOMContentLoaded', () => {
    initChart();
    startPolling();
    attachEventListeners();
});

function attachEventListeners() {
    document.getElementById('tap-button').addEventListener('click', handleRfidTap);
    document.getElementById('start-exercise-button').addEventListener('click', handleStartExercise);
    document.getElementById('reset-machine-button').addEventListener('click', handleResetMachine);
}

// --- API Layer ---
async function apiFetch(endpoint, options = {}) {
    try {
        const response = await fetch(`${CONFIG.BACKEND_URL}${endpoint}`, {
            ...options,
            headers: {
                'Content-Type': 'application/json',
                ...options.headers
            }
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        state.isOffline = false;
        return await response.json();
    } catch (err) {
        state.isOffline = true;
        console.error(`API Error [${endpoint}]:`, err.message);
        return null;
    }
}

// --- Core Logic ---
async function updateDashboard() {
    try {
        const data = await apiFetch('/dashboard/live');
        if (!data) {
            updateOfflineUI();
            return;
        }

        const { current, feeds, history } = data;

        handleSessionState(current);
        
        updateHeader(current);
        updateRepHero(current);
        updateAICoach(current, feeds);
        updateROMTracker(current);
        updateStats(current);
        updateMemberCard(current);
        
        if (Date.now() - state.lastRepTime > 2000) {
            updateHistory(history);
            updateChart(feeds);
            state.lastRepTime = Date.now();
        }
    } catch (err) {
        const errorBanner = document.getElementById('global-error-banner');
        const errorMessage = document.getElementById('error-message');
        if (errorBanner && errorMessage) {
            errorBanner.style.display = 'flex';
            errorMessage.innerText = "Loop Error: " + err.message + " | Stack: " + err.stack;
        }
    }
}

function handleSessionState(current) {
    // Detect RFID change and handle auto-login
    if (current.auto_login_ready && current.rfid_uid !== state.auth.rfidUid) {
        performAutoLogin(current.rfid_uid);
    }

    // Detect reset
    if (current.exercise_status === 'awaiting_rfid' && state.auth.rfidUid) {
        clearLocalSession();
    }

    // Rest tracking
    if (current.rep_count > state.lastRepCount) {
        state.lastRepCount = current.rep_count;
        state.lastRepTime = Date.now();
    }
}

// --- UI Updaters ---
function updateHeader(current) {
    const nameEl = document.getElementById('strip-name');
    const exerciseEl = document.getElementById('strip-exercise');
    const timerEl = document.getElementById('session-timer');
    const statusText = document.getElementById('strip-status-text');

    nameEl.innerText = current.member_name || 'Ready for Workout';
    exerciseEl.innerText = current.exercise_type ? current.exercise_type.replace('_', ' ') : 'Please select an exercise';

    // Status Indicator
    statusText.innerText = current.is_offline ? 'Offline' : 'Live Sync';

    // Timer
    if (current.exercise_status === 'tracking' && current.updated_at) {
        const start = new Date(current.updated_at).getTime();
        const elapsed = Math.floor((Date.now() - start) / 1000);
        const mins = Math.floor(elapsed / 60).toString().padStart(2, '0');
        const secs = (elapsed % 60).toString().padStart(2, '0');
        timerEl.innerText = `${mins}:${secs}`;
    } else {
        timerEl.innerText = '00:00';
    }
}

function updateRepHero(current) {
    if (state.isPreparing) return; // Prevent polling from overwriting countdown

    const display = document.getElementById('rep-display');
    const subtitle = document.getElementById('rep-subtitle');

    const count = current.rep_count || 0;
    if (display.innerText !== count.toString()) {
        display.innerText = count;
        display.style.animation = 'none';
        display.offsetHeight; // trigger reflow
        display.style.animation = 'pulse 0.3s ease-out';
    }

    if (current.exercise_status === 'awaiting_rfid') {
        subtitle.innerText = 'Tap your RFID card or log in manually to begin';
    } else if (current.exercise_status === 'awaiting_exercise') {
        subtitle.innerText = 'Select an exercise to start your set';
    } else {
        subtitle.innerText = `Keep it up, ${current.member_name.split(' ')[0]}! You're doing great.`;
    }
}

function updateAICoach(current, feeds) {
    const title = document.getElementById('ai-status-title');
    const feedback = document.getElementById('ai-feedback-text');
    const card = document.getElementById('coach-display-card');
    const dot = document.getElementById('quality-indicator');
    const label = document.getElementById('quality-label');

    // Handle Error States
    const errorBanner = document.getElementById('global-error-banner');
    if (current.ai_status === 'Access Denied') {
        errorBanner.style.display = 'flex';
        document.getElementById('error-message').innerText = current.feedback_text;
        card.style.borderColor = 'var(--danger)';
        title.innerText = "Action Required";
        feedback.innerText = "Please log in at the terminal first.";
        return;
    } else {
        errorBanner.style.display = 'none';
        card.style.borderColor = 'var(--border-light)';
    }

    // Default status
    dot.className = 'quality-dot';

    title.innerText = current.ai_status || "Let's get started";
    feedback.innerText = current.feedback_text || "Position yourself correctly on the machine. I'll provide real-time feedback on your form.";

    const stateId = current.ai_state || 0;
    if (stateId === 0) {
        dot.classList.add('quality-good');
        label.innerText = "Excellent Form";
        if (current.exercise_status === 'tracking') card.style.borderColor = 'var(--success)';
    } else if (stateId >= 4) {
        dot.classList.add('quality-bad');
        label.innerText = "Needs Adjustment";
    } else {
        dot.classList.add('quality-warn');
        label.innerText = "Almost There";
    }
}

function updateROMTracker(current) {
    const fill = document.getElementById('rom-bar-fill');
    const marker = document.getElementById('rom-marker');

    if (!current.current_distance || current.exercise_status !== 'tracking') {
        fill.style.width = '0%';
        return;
    }

    const { max, min } = CONFIG.ROM_CALIBRATION;
    let percent = ((max - current.current_distance) / (max - min)) * 100;
    percent = Math.max(0, Math.min(100, percent));

    fill.style.width = `${percent}%`;
}

function updateStats(current) {
    const formVal = document.getElementById('qs-form');
    const fatigueVal = document.getElementById('qs-fatigue');

    if (current.exercise_status === 'tracking') {
        formVal.innerText = current.ai_state === 0 ? "98%" : "72%";
        formVal.style.color = current.ai_state === 0 ? "var(--success)" : "var(--warning)";
        fatigueVal.innerText = current.rep_count > 10 ? "High" : "Low";
    } else {
        formVal.innerText = "--";
        formVal.style.color = "var(--text-muted)";
        fatigueVal.innerText = "--";
    }
}

function updateMemberCard(current) {
    const profile = current.member_profile || state.auth.member;
    const nameEl = document.getElementById('member-name');
    const userEl = document.getElementById('member-username');
    const planEl = document.getElementById('member-plan');
    const visitsEl = document.getElementById('member-visits');
    const loginBadge = document.getElementById('login-state');
    const avatar = document.getElementById('member-avatar-large');
    const avatarSmall = document.getElementById('member-avatar');

    if (current.rfid_uid) {
        nameEl.innerText = current.member_name;
        userEl.innerText = "Authenticated Member";
        planEl.innerText = profile?.membership_plan || "Active Plan";
        visitsEl.innerText = profile?.total_visits || "0";
        loginBadge.innerText = "Logged In";
        loginBadge.className = "badge badge-success";
        avatar.innerText = current.member_name.charAt(0);
        avatar.style.background = "var(--accent-primary)";
        avatarSmall.innerText = current.member_name.charAt(0);
    } else {
        nameEl.innerText = "Welcome";
        userEl.innerText = "Please log in to track progress";
        planEl.innerText = "--";
        visitsEl.innerText = "--";
        loginBadge.innerText = "Guest";
        loginBadge.className = "badge badge-neutral";
        avatar.innerText = "?";
        avatar.style.background = "var(--bg-input)";
        avatarSmall.innerText = "?";
    }
}

function updateHistory(history) {
    const list = document.getElementById('machine-history');
    if (!history || history.length === 0) {
        list.innerHTML = '<div style="padding: 32px; text-align: center; color: var(--text-muted); font-size: 0.9rem;">No workouts recorded recently.</div>';
        return;
    }

    list.innerHTML = history.map(item => `
        <div class="list-item" style="padding: 16px; border-radius: var(--radius-sm); border: 1px solid var(--border-light); margin-bottom: 8px;">
            <div>
                <strong style="color: var(--text-main); font-size: 0.95rem;">${item.member_name}</strong><br>
                <span style="color: var(--text-muted); font-size: 0.8rem;">${item.machine_name || 'Chest Press'}</span>
            </div>
            <div style="text-align: right;">
                <span style="color: var(--accent-primary); font-weight: 800; font-size: 1.1rem;">${item.reps} Reps</span><br>
                <span style="color: var(--text-muted); font-size: 0.75rem;">${new Date(item.started_at).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })}</span>
            </div>
        </div>
    `).join('');
}

// --- Chart Logic ---
function initChart() {
    try {
        if (typeof Chart === 'undefined') {
            console.warn("Chart.js failed to load. Skipping chart initialization.");
            return;
        }
        const ctx = document.getElementById('motionChart').getContext('2d');
        state.chart = new Chart(ctx, {
            type: 'line',
            data: {
                labels: Array(CONFIG.CHART_POINTS).fill(''),
                datasets: [{
                    label: 'Form Accuracy (0 = Perfect)',
                    data: Array(CONFIG.CHART_POINTS).fill(0),
                    borderColor: '#6c5ce7',
                    backgroundColor: 'rgba(108, 92, 231, 0.1)',
                    borderWidth: 3,
                    fill: true,
                    tension: 0.4,
                    pointRadius: 0
                }]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                animation: { duration: 0 },
                plugins: { legend: { display: false } },
                scales: {
                    x: { display: false },
                    y: {
                        min: 0, max: 5,
                        grid: { color: 'rgba(255,255,255,0.05)' },
                        ticks: { color: '#5a6375', stepSize: 1 }
                    }
                }
            }
        });
    } catch (e) {
        console.error("Chart initialization failed:", e);
    }
}

function updateChart(feeds) {
    if (!state.chart || !feeds) return;
    const latest = feeds.slice(-CONFIG.CHART_POINTS).map(f => f.field4 || 0);

    // Pad if not enough data
    while (latest.length < CONFIG.CHART_POINTS) latest.unshift(0);

    state.chart.data.datasets[0].data = latest;
    state.chart.update('none');
}

// --- Action Handlers ---
async function handleRfidTap() {
    const input = document.getElementById('rfid-input');
    const uid = input.value.trim();
    if (!uid) return;

    const res = await apiFetch('/machine/tap', {
        method: 'POST',
        body: JSON.stringify({
            rfid_uid: uid,
            machine_name: "Chest Press",
            station_id: "STATION_01"
        })
    });

    if (res) input.value = '';
}

async function handleStartExercise() {
    if (state.isPreparing) return;
    
    const exercise = document.getElementById('exercise-select').value;
    const display = document.getElementById('rep-display');
    const subtitle = document.getElementById('rep-subtitle');
    
    state.isPreparing = true;
    let count = 3;
    
    display.style.color = "var(--warning)";
    display.innerText = count;
    subtitle.innerText = "Get ready to start...";
    
    const countdownInterval = setInterval(async () => {
        count--;
        if (count > 0) {
            display.innerText = count;
            // trigger reflow for animation
            display.style.animation = 'none';
            display.offsetHeight;
            display.style.animation = 'pulse 0.3s ease-out';
        } else {
            clearInterval(countdownInterval);
            display.innerText = "GO!";
            display.style.color = "";
            state.isPreparing = false;
            
            await apiFetch('/machine/select-exercise', {
                method: 'POST',
                body: JSON.stringify({
                    exercise_type: exercise,
                    machine_name: "Chest Press",
                    station_id: "STATION_01"
                })
            });
        }
    }, 1000);
}

async function handleResetMachine() {
    await apiFetch('/machine/reset', { method: 'POST' });
    clearLocalSession();
}

// --- Auth & Session Helpers ---
async function performAutoLogin(rfid) {
    try {
        const res = await apiFetch('/auth/rfid-login', {
            method: 'POST',
            body: JSON.stringify({ rfid_uid: rfid })
        });
        if (res) {
            state.auth = { rfidUid: rfid, token: res.access_token, member: res.member };
            localStorage.setItem('smartGymAutoLogin', JSON.stringify(state.auth));
        }
    } catch (e) {
        console.warn("Auto-login failed:", e.message);
    }
}

function clearLocalSession() {
    state.auth = {};
    localStorage.removeItem('smartGymAutoLogin');
    state.lastRepCount = 0;
}

function updateOfflineUI() {
    const statusText = document.getElementById('strip-status-text');
    const nameEl = document.getElementById('strip-name');
    if (statusText) {
        statusText.innerText = "Offline - Retrying...";
        statusText.style.color = "var(--danger)";
    }
    if (nameEl) {
        nameEl.innerText = "Connection Failed";
    }
}

function startPolling() {
    setInterval(updateDashboard, CONFIG.POLL_INTERVAL);
}
