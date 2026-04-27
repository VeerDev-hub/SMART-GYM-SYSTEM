// web-dashboard/script.js
// Smart Gym Intelligence Dashboard — Frontend Controller

let myChart = null;
let lastRepTime = Date.now();
let lastRepCount = 0;

const BACKEND_URL = `http://${window.location.hostname}:8080`;
const LOCAL_FALLBACK_URL = "./live_state.json";
const AUTO_LOGIN_KEY = "smartGymAutoLogin";
const POLL_INTERVAL_MS = 250;

let autoLoginState = {
  rfidUid: "",
  token: "",
  member: null,
  dashboard: null,
};

// Restore cached auto-login from localStorage
try {
  const saved = JSON.parse(localStorage.getItem(AUTO_LOGIN_KEY) || "{}");
  autoLoginState = { ...autoLoginState, ...saved };
} catch (error) {
  console.warn("Auto-login cache unavailable:", error);
}

// ──────────────────────────────────────────────
//  Network helpers
// ──────────────────────────────────────────────

async function fetchDashboardData() {
  try {
    const res = await fetch(`${BACKEND_URL}/dashboard/live`, {
      cache: "no-store",
      headers: { "Cache-Control": "no-cache" },
    });
    if (!res.ok) throw new Error(`HTTP ${res.status}`);
    setConnectionStatus(true);
    return await res.json();
  } catch (error) {
    console.warn("Backend fetch failed, trying local fallback:", error.message);
    setConnectionStatus(false);
    try {
      const fallback = await fetch(`${LOCAL_FALLBACK_URL}?t=${Date.now()}`, { cache: "no-store" });
      if (!fallback.ok) throw new Error(`Fallback HTTP ${fallback.status}`);
      return await fallback.json();
    } catch (fallbackError) {
      console.error("All data sources offline:", fallbackError.message);
      return null;
    }
  }
}

async function postJson(path, payload) {
  const res = await fetch(`${BACKEND_URL}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    throw new Error(body.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

function setConnectionStatus(online) {
  const el = document.getElementById("last-update");
  if (!el) return;
  if (!online) {
    el.innerText = "Backend offline — using local cache";
    el.style.color = "var(--warning)";
  } else {
    el.style.color = "";
  }
}

// ──────────────────────────────────────────────
//  Auto-login via RFID
// ──────────────────────────────────────────────

function saveAutoLoginState() {
  localStorage.setItem(AUTO_LOGIN_KEY, JSON.stringify(autoLoginState));
}

async function fetchMemberDashboard(token) {
  const res = await fetch(`${BACKEND_URL}/user/dashboard`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!res.ok) throw new Error(`Dashboard HTTP ${res.status}`);
  return res.json();
}

async function autoLoginFromRfid(current) {
  if (!current || !current.auto_login_ready || !current.rfid_uid) return;

  // Already logged in for this card
  if (autoLoginState.rfidUid === current.rfid_uid && autoLoginState.token) {
    if (!autoLoginState.dashboard) {
      try {
        autoLoginState.dashboard = await fetchMemberDashboard(autoLoginState.token);
        saveAutoLoginState();
      } catch (error) {
        console.error("Cached member dashboard fetch failed:", error);
      }
    }
    return;
  }

  // New RFID card — perform login
  const login = await postJson("/auth/rfid-login", { rfid_uid: current.rfid_uid });
  autoLoginState.rfidUid = current.rfid_uid;
  autoLoginState.token = login.access_token;
  autoLoginState.member = login.member;
  autoLoginState.dashboard = null;

  try {
    autoLoginState.dashboard = await fetchMemberDashboard(login.access_token);
  } catch (error) {
    console.error("Member dashboard fetch failed after RFID login:", error);
  }
  saveAutoLoginState();
}

// ──────────────────────────────────────────────
//  Rest Optimizer
// ──────────────────────────────────────────────

function runRestOptimizer(currentReps) {
  const restText = document.getElementById("rest-advice");
  if (!restText) return;

  if (currentReps > lastRepCount) {
    lastRepTime = Date.now();
    lastRepCount = currentReps;
    restText.innerText = "Set in progress... Keep going!";
    restText.style.color = "var(--accent-light)";
  } else if (currentReps === 0 && lastRepCount > 0) {
    const secondsSinceLastRep = Math.floor((Date.now() - lastRepTime) / 1000);
    if (secondsSinceLastRep < 60) {
      restText.innerText = `Resting: ${secondsSinceLastRep}s (Target: 60-90s)`;
      restText.style.color = "var(--warning)";
    } else {
      restText.innerText = "Recovery optimal. Ready for next set!";
      restText.style.color = "var(--good)";
    }
  }
}

// ──────────────────────────────────────────────
//  AI Coach display
// ──────────────────────────────────────────────

function updateAICoach(current, mFeeds) {
  if (!current) return;
  const latest = mFeeds && mFeeds.length ? mFeeds[mFeeds.length - 1] : null;
  const stateId = latest ? parseInt(latest.field4) : current.ai_state || 0;

  const titleEl = document.getElementById("ai-status-title");
  const textEl = document.getElementById("ai-feedback-text");
  const boxEl = document.querySelector(".coach-display");

  // Handle Reset State for text
  if (current.exercise_status === "awaiting_exercise" || current.exercise_status === "awaiting_rfid") {
    titleEl.innerText = "Ready to Start";
    textEl.innerText = "Position yourself in front of the camera and start your set.";
    boxEl.classList.remove("state-good", "state-warn", "state-danger");
    updateQualityIndicator(0, "Ready");
    return;
  }

  // Reset state classes
  boxEl.classList.remove("state-good", "state-warn", "state-danger");

  const feedbackMap = {
    0: { t: "Perfect Form", d: "Excellent control. Maintain this tempo.", c: "state-good" },
    1: { t: "Asymmetry", d: "Balance your grip. One side is lagging during the press.", c: "state-warn" },
    2: { t: "Posture Alert", d: "Keep your back flat against the pad and brace your core.", c: "state-warn" },
    3: { t: "Half-Rep", d: "Increase range of motion. Finish the full chest press arc.", c: "state-warn" },
    4: { t: "Weight Jerking", d: "Too much momentum! Slow down and control both directions.", c: "state-danger" },
    5: { t: "Wrong Exercise", d: "Only one hand is lifting. Use both hands together for proper form.", c: "state-danger" },
  };

  const config = feedbackMap[stateId] || feedbackMap[0];
  titleEl.innerText = current.ai_status || config.t;
  textEl.innerText = current.feedback_text || config.d;
  if (config.c) boxEl.classList.add(config.c);

  // Update Quality Dot
  updateQualityIndicator(stateId, current.ai_status);
}

function updateQualityIndicator(stateId, status) {
  const dot = document.getElementById("quality-indicator");
  const label = document.getElementById("quality-label");
  if (!dot || !label) return;

  dot.classList.remove("quality-good", "quality-warn", "quality-bad");

  if (stateId === 0) {
    dot.classList.add("quality-good");
    label.innerText = "Good Form";
  } else if (stateId === 4 || stateId === 5) {
    dot.classList.add("quality-bad");
    label.innerText = "Fix Form";
  } else {
    dot.classList.add("quality-warn");
    label.innerText = "Adjusting...";
  }
}

let lastPercentage = 0;

function updateGuidance(current) {
  const romFill = document.getElementById("rom-bar-fill");
  const romMarker = document.getElementById("rom-marker");
  if (!romFill || !romMarker) return;

  // Handle RESET state
  if (!current.current_distance || current.exercise_status === "awaiting_exercise" || current.exercise_status === "completed") {
    romFill.style.width = "0%";
    romMarker.style.left = "0%";
    lastPercentage = 0;
    return;
  }

  // Calibrate ROM: 72cm (start) to 65cm (full extension)
  const maxDist = 72.0;
  const minDist = 65.0;
  const range = maxDist - minDist;

  let targetPercentage = ((maxDist - current.current_distance) / range) * 100;
  targetPercentage = Math.max(0, Math.min(100, targetPercentage));

  // Smoothing (Lerp): Move 40% of the way to target each frame
  const smoothed = lastPercentage + (targetPercentage - lastPercentage) * 0.4;
  lastPercentage = smoothed;

  romFill.style.width = `${smoothed}%`;
  romMarker.style.left = `${smoothed}%`;

  if (smoothed > 90) {
    romFill.style.boxShadow = "0 0 15px var(--good)";
  } else {
    romFill.style.boxShadow = "0 0 10px var(--accent-glow)";
  }
}

// ──────────────────────────────────────────────
//  Chart.js — Form Analysis
// ──────────────────────────────────────────────

function updateChart(mFeeds) {
  const canvas = document.getElementById("motionChart");
  if (!canvas || !mFeeds || mFeeds.length === 0) return;
  const ctx = canvas.getContext("2d");

  const visionData = mFeeds.slice(-20);
  const labels = visionData.map((f) => {
    const timePart = f.created_at.split("T")[1];
    return timePart ? timePart.split(".")[0] : "";
  });
  const formIds = visionData.map((f) => parseInt(f.field4));

  if (myChart) myChart.destroy();

  myChart = new Chart(ctx, {
    type: "line",
    data: {
      labels: labels,
      datasets: [
        {
          label: "Form Error ID (0 = Perfect)",
          data: formIds,
          borderColor: "#a29bfe",
          backgroundColor: "rgba(108, 92, 231, 0.08)",
          fill: true,
          tension: 0.45,
          pointRadius: 3,
          pointBackgroundColor: "#a29bfe",
          pointBorderColor: "#a29bfe",
          borderWidth: 2,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: {
          labels: {
            color: "#8a94a6",
            font: { family: "Inter", size: 12 },
          },
        },
      },
      scales: {
        x: {
          ticks: { color: "#5a6375", font: { size: 10 } },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
        y: {
          min: 0,
          max: 5,
          ticks: { stepSize: 1, color: "#5a6375", font: { size: 11 } },
          grid: { color: "rgba(255,255,255,0.04)" },
        },
      },
    },
  });
}

// ──────────────────────────────────────────────
//  Session History table
// ──────────────────────────────────────────────

function updateHistory(history) {
  const historyEl = document.getElementById("machine-history");
  if (!historyEl) return;

  if (!history || history.length === 0) {
    historyEl.innerHTML = `<p style="text-align:center; color:var(--text-muted);">Awaiting session data...</p>`;
    return;
  }

  historyEl.innerHTML = history
    .map(
      (item) => `
    <div class="history-row">
      <strong>${item.member_name}</strong>
      <span>${new Date(item.started_at).toLocaleString()}</span>
      <span>Reps: ${item.reps ?? 0}</span>
      <span>Fatigue: ${item.fatigue_level || "Pending"}</span>
      <span>Form: ${item.form_score != null ? Number(item.form_score).toFixed(1) : "Pending"}</span>
    </div>`
    )
    .join("");
}

// ──────────────────────────────────────────────
//  Machine State display
// ──────────────────────────────────────────────

function updateMachineState(current) {
  const sessionStatus = document.getElementById("session-status");
  const exerciseStatus = document.getElementById("exercise-status");
  const rfidInput = document.getElementById("rfid-input");

  if (sessionStatus) {
    const raw = current.exercise_status || "awaiting_rfid";
    sessionStatus.innerText = raw.replaceAll("_", " ");
  }
  if (exerciseStatus) {
    exerciseStatus.innerText = current.exercise_type
      ? current.exercise_type.replaceAll("_", " ")
      : "Not selected";
  }
  if (rfidInput && current.rfid_uid && current.exercise_status !== "awaiting_rfid") {
    rfidInput.value = current.rfid_uid;
  }
}

// ──────────────────────────────────────────────
//  Member Profile Card
// ──────────────────────────────────────────────

function updateMemberCard(current) {
  const profile = current.member_profile || autoLoginState.member;
  const dashboard = autoLoginState.dashboard;

  document.getElementById("login-state").innerText = current.auto_login_ready
    ? "Signed in via RFID"
    : "Waiting for RFID";

  document.getElementById("member-name").innerText = profile?.full_name || "Awaiting Tap...";
  document.getElementById("member-username").innerText = profile?.username || "-";
  document.getElementById("member-plan").innerText =
    dashboard?.member?.membership_plan || profile?.membership_plan || "-";
  document.getElementById("member-status").innerText =
    dashboard?.member?.membership_status || profile?.membership_status || "-";
  document.getElementById("member-visits").innerText =
    dashboard?.summary?.total_visits ?? "-";
  document.getElementById("member-last-entry").innerText = dashboard?.summary?.last_entry_time
    ? new Date(dashboard.summary.last_entry_time).toLocaleString()
    : "-";
}

// ──────────────────────────────────────────────
//  Action handlers
// ──────────────────────────────────────────────

async function handleTapRfid() {
  const rfidInput = document.getElementById("rfid-input");
  const uid = rfidInput.value.trim().toUpperCase();
  if (!uid) {
    alert("Enter or tap an RFID UID first.");
    return;
  }

  try {
    await postJson("/machine/tap", {
      rfid_uid: uid,
      machine_name: "Chest Press",
      station_id: "CHEST_PRESS_01",
    });
    await loadDashboard();
  } catch (error) {
    alert(`RFID tap failed: ${error.message}`);
  }
}

async function handleSelectExercise() {
  const exercise = document.getElementById("exercise-select").value;
  try {
    await postJson("/machine/select-exercise", {
      exercise_type: exercise,
      machine_name: "Chest Press",
      station_id: "CHEST_PRESS_01",
    });
    await loadDashboard();
  } catch (error) {
    alert(`Exercise selection failed: ${error.message}`);
  }
}

async function handleResetMachine() {
  try {
    await postJson("/machine/reset", {});
    document.getElementById("rfid-input").value = "";
    autoLoginState = { rfidUid: "", token: "", member: null, dashboard: null };
    saveAutoLoginState();
    lastRepCount = 0;
    await loadDashboard();
  } catch (error) {
    alert(`Machine reset failed: ${error.message}`);
  }
}

// ──────────────────────────────────────────────
//  Main polling loop
// ──────────────────────────────────────────────

async function loadDashboard() {
  const data = await fetchDashboardData();
  if (!data) return;

  // Clear cached login if machine was reset
  if (
    !data.current.auto_login_ready &&
    data.current.exercise_status === "awaiting_rfid" &&
    autoLoginState.rfidUid
  ) {
    autoLoginState = { rfidUid: "", token: "", member: null, dashboard: null };
    saveAutoLoginState();
  }

  // Attempt RFID auto-login
  try {
    await autoLoginFromRfid(data.current);
  } catch (error) {
    console.error("RFID auto-login failed:", error);
  }

  // Update header
  document.getElementById("user-display").innerText = data.current.user_id || "Awaiting Tap...";
  document.getElementById("rep-display").innerText = data.current.rep_count ?? 0;

  const updatedAt = data.current.updated_at;
  if (updatedAt) {
    document.getElementById("last-update").innerText = new Date(updatedAt).toLocaleTimeString();
  }

  const errorBanner = document.getElementById("global-error-banner");
  if (errorBanner) {
    if (data.current.ai_status === "Access Denied") {
        errorBanner.style.display = "flex";
        document.getElementById("error-message").innerText = data.current.feedback_text || "Access Denied: Tap at entrance first.";
    } else {
        errorBanner.style.display = "none";
    }
  }

  // Update all dashboard sections
  updateAICoach(data.current, data.feeds);
  updateGuidance(data.current);
  updateChart(data.feeds);
  runRestOptimizer(data.current.rep_count);
  updateHistory(data.history);
  updateMachineState(data.current);
  updateMemberCard(data.current);
}

// ──────────────────────────────────────────────
//  Event listeners & bootstrap
// ──────────────────────────────────────────────

document.getElementById("tap-button").addEventListener("click", handleTapRfid);
document.getElementById("start-exercise-button").addEventListener("click", handleSelectExercise);
document.getElementById("reset-machine-button").addEventListener("click", handleResetMachine);

setInterval(loadDashboard, POLL_INTERVAL_MS);
loadDashboard();
