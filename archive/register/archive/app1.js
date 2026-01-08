const API_BASE = window.API_BASE || "http://localhost:5432";

/* Widgets */
const widgetTotalAgents = document.getElementById("widgetTotalAgents");
const widgetTotalTasks = document.getElementById("widgetTotalTasks");

/* Layout */
const loginSection = document.getElementById("loginSection");
const dashboardSection = document.getElementById("dashboardSection");
const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const userLabel = document.getElementById("userLabel");
const logoutBtn = document.getElementById("logoutBtn");

/* Health */
const healthOutput = document.getElementById("healthOutput");
const healthOverall = document.getElementById("healthOverall");
const healthCouch = document.getElementById("healthCouch");
const healthChroma = document.getElementById("healthChroma");
const healthNeo4j = document.getElementById("healthNeo4j");
const healthEmbed = document.getElementById("healthEmbed");

/* Details panel */
const nodeDetailsPanel = document.getElementById("nodeDetails");
const nodeDetailsTitle = document.getElementById("nodeDetailsTitle");
const nodeDetailsType = document.getElementById("nodeDetailsType");
const nodeDetailsId = document.getElementById("nodeDetailsId");
const nodeDetailsRole = document.getElementById("nodeDetailsRole");
const nodeDetailsGoal = document.getElementById("nodeDetailsGoal");
const nodeDetailsDescription = document.getElementById("nodeDetailsDescription");
const nodeDetailsStep = document.getElementById("nodeDetailsStep");
const nodeDetailsMeta = document.getElementById("nodeDetailsMeta");
const nodeDetailsClose = document.getElementById("nodeDetailsClose");

/* Forms + tables */
const refreshHealthBtn = document.getElementById("refreshHealthBtn");
const createAgentForm = document.getElementById("createAgentForm");
const createAgentResult = document.getElementById("createAgentResult");
const createTaskForm = document.getElementById("createTaskForm");
const createTaskResult = document.getElementById("createTaskResult");
const refreshAgentsBtn = document.getElementById("refreshAgentsBtn");
const agentsTableBody = document.getElementById("agentsTableBody");
const refreshTasksBtn = document.getElementById("refreshTasksBtn");
const tasksTableBody = document.getElementById("tasksTableBody");
const refreshGraphBtn = document.getElementById("refreshGraphBtn");
const graphContainer = document.getElementById("graph");

/* AUTH UI LOGIC */
function showLogin() {
  loginSection.classList.remove("hidden");
  dashboardSection.classList.add("hidden");
  logoutBtn.classList.add("hidden");
  userLabel.classList.add("hidden");
  loginError.classList.add("hidden");
  loginError.textContent = "";
}

function showDashboard(username) {
  loginSection.classList.add("hidden");
  dashboardSection.classList.remove("hidden");
  logoutBtn.classList.remove("hidden");
  userLabel.classList.remove("hidden");
  userLabel.textContent = "Logged in as " + username;

  fetchHealth();
  fetchAgents();
  fetchTasks();
  fetchGraph();
}

async function checkSession() {
  const token = localStorage.getItem("token");
  if (!token) {
    showLogin();
    return;
  }

  try {
    const res = await fetch(API_BASE + "/auth/me", {
      headers: {
        "Authorization": "Bearer " + token
      }
    });

    if (!res.ok) {
      showLogin();
      return;
    }

    const data = await res.json();
    showDashboard(data.username);

  } catch (e) {
    console.error(e);
    showLogin();
  }
}

/* LOGIN */
loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.classList.add("hidden");

  const formData = new FormData(loginForm);
  const username = formData.get("username") || "";
  const password = formData.get("password") || "";

  try {
    const res = await fetch(API_BASE + "/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      loginError.textContent = "Invalid credentials.";
      loginError.classList.remove("hidden");
      return;
    }

    const data = await res.json();
    localStorage.setItem("token", data.access_token);
    showDashboard(username);

  } catch (err) {
    console.error(err);
    loginError.textContent = "Login failed.";
    loginError.classList.remove("hidden");
  }
});

/* LOGOUT */
logoutBtn.addEventListener("click", () => {
  localStorage.removeItem("token");
  showLogin();
});

/* HEALTH LOGIC (public) */
function updateStatusPill(el, isUp) {
  if (!el) return;

  const spans = el.querySelectorAll("span");
  const dot = spans[0];
  const text = spans[1];

  if (isUp) {
    el.style.backgroundColor = "rgba(16,185,129,0.15)";
    el.style.color = "#6ee7b7";
    dot.style.backgroundColor = "#22c55e";
    text.textContent = "Up";
  } else {
    el.style.backgroundColor = "rgba(248,113,113,0.15)";
    el.style.color = "#fecaca";
    dot.style.backgroundColor = "#f97373";
    text.textContent = "Down";
  }
}

async function fetchHealth() {
  if (healthOutput) healthOutput.textContent = "Loading...";

  try {
    const res = await fetch(API_BASE + "/healthz");
    const data = await res.json();

    if (healthOutput) {
      healthOutput.textContent = JSON.stringify(data, null, 2);
    }

    updateStatusPill(healthCouch, !!data.couchdb);
    updateStatusPill(healthChroma, !!data.chroma);
    updateStatusPill(healthNeo4j, !!data.neo4j);
    updateStatusPill(healthEmbed, !!data.embedding_model);

    const spans = healthOverall.querySelectorAll("span");
    const dot = spans[0];
    const text = spans[1];

    const all = data.couchdb && data.chroma && data.neo4j && data.embedding_model;
    const any = data.couchdb || data.chroma || data.neo4j || data.embedding_model;

    if (all) {
      healthOverall.style.backgroundColor = "rgba(16,185,129,0.15)";
      healthOverall.style.color = "#6ee7b7";
      dot.style.backgroundColor = "#22c55e";
      text.textContent = "Overall status: All green";
    } else if (any) {
      healthOverall.style.backgroundColor = "rgba(245,158,11,0.15)";
      healthOverall.style.color = "#facc15";
      dot.style.backgroundColor = "#f59e0b";
      text.textContent = "Overall status: Degraded";
    } else {
      healthOverall.style.backgroundColor = "rgba(248,113,113,0.15)";
      healthOverall.style.color = "#fecaca";
      dot.style.backgroundColor = "#f97373";
      text.textContent = "Overall status: Down";
    }
  } catch (e) {
    console.error(e);
    if (healthOutput) {
      healthOutput.textContent = "Failed to load health info.";
    }
  }
}

refreshHealthBtn.addEventListener("click", fetchHealth);

/* AGENTS */
async function fetchAgents() {
  agentsTableBody.innerHTML = "";

  try {
    const res = await fetch(API_BASE + "/ui/couch/agents?limit=100", {
      headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
    });

    if (!res.ok) {
      agentsTableBody.innerHTML =
        "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Failed to load agents.</td></tr>";
      return;
    }

    const data = await res.json();

    widgetTotalAgents.textContent = data.items?.length || 0;

    if (!data.items || data.items.length === 0) {
      agentsTableBody.innerHTML =
        "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>No agents yet.</td></tr>";
      return;
    }

    for (const doc of data.items) {
      const metadata = doc.metadata || {};
      const tr = document.createElement("tr");

      tr.innerHTML = `
        <td class="px-3 py-2 font-mono text-[11px]">${doc.id || doc._id}</td>
        <td class="px-3 py-2">${metadata.role || ""}</td>
        <td class="px-3 py-2">${metadata.goal || ""}</td>
        <td class="px-3 py-2 max-w-xs truncate" title="${metadata.description || ""}">
          ${metadata.description || ""}
        </td>
        <td class="px-3 py-2 text-slate-400 text-[11px]">${doc.created_at || doc._id}</td>
      `;

      agentsTableBody.appendChild(tr);
    }
  } catch (e) {
    console.error(e);
    agentsTableBody.innerHTML =
      "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Error loading agents.</td></tr>";
  }
}

refreshAgentsBtn.addEventListener("click", fetchAgents);

/* TASKS */
async function fetchTasks() {
  tasksTableBody.innerHTML = "";

  try {
    const res = await fetch(API_BASE + "/ui/couch/tasks?limit=100", {
      headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
    });

    if (!res.ok) {
      tasksTableBody.innerHTML =
        "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Failed to load tasks.</td></tr>";
      return;
    }

    const data = await res.json();

    widgetTotalTasks.textContent = data.items?.length || 0;

    if (!data.items || data.items.length === 0) {
      tasksTableBody.innerHTML =
        "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>No tasks yet.</td></tr>";
      return;
    }

    for (const doc of data.items) {
      const metadata = doc.metadata || {};
      const tr = document.createElement("tr");

      tr.innerHTML = `
        <td class="px-3 py-2 font-mono text-[11px]">${doc.id || doc._id}</td>
        <td class="px-3 py-2 font-mono text-[11px]">${doc.agent_id || ""}</td>
        <td class="px-3 py-2">${metadata.role || ""}</td>
        <td class="px-3 py-2 max-w-xs truncate" title="${metadata.goal || ""}">
          ${metadata.goal || ""}
        </td>
        <td class="px-3 py-2 text-slate-400 text-[11px]">${doc.created_at || doc._id}</td>
      `;

      tasksTableBody.appendChild(tr);
    }
  } catch (e) {
    console.error(e);
    tasksTableBody.innerHTML =
      "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Error loading tasks.</td></tr>";
  }
}

refreshTasksBtn.addEventListener("click", fetchTasks);

/* GRAPH */
async function fetchGraph() {
  if (!graphContainer) return;
  graphContainer.innerHTML = "Loading graph...";

  try {
    const res = await fetch(API_BASE + "/ui/graph?limit=200", {
      headers: { "Authorization": "Bearer " + localStorage.getItem("token") }
    });

    if (!res.ok) {
      graphContainer.innerHTML =
        "<div class='text-red-400 text-xs p-4'>Failed to load graph.</div>";
      return;
    }

    const data = await res.json();
    renderGraph(data);

  } catch (e) {
    graphContainer.innerHTML =
      "<div class='text-red-400 text-xs p-4'>Error loading graph.</div>";
  }
}

refreshGraphBtn.addEventListener("click", fetchGraph);

/* Node Details Close */
if (nodeDetailsClose && nodeDetailsPanel) {
  nodeDetailsClose.addEventListener("click", () => {
    nodeDetailsPanel.classList.add("hidden");
  });
}

/* INIT */
checkSession();
