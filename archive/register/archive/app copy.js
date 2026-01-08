const API_BASE = window.API_BASE || "http://localhost:5432";

const loginSection = document.getElementById("loginSection");
const dashboardSection = document.getElementById("dashboardSection");
const loginForm = document.getElementById("loginForm");
const loginError = document.getElementById("loginError");
const userLabel = document.getElementById("userLabel");
const logoutBtn = document.getElementById("logoutBtn");

const widgetTotalAgents = document.getElementById("widgetTotalAgents");
const widgetTotalTasks = document.getElementById("widgetTotalTasks");

const healthOutput = document.getElementById("healthOutput");
const healthOverall = document.getElementById("healthOverall");
const healthCouch = document.getElementById("healthCouch");
const healthChroma = document.getElementById("healthChroma");
const healthNeo4j = document.getElementById("healthNeo4j");
const healthEmbed = document.getElementById("healthEmbed");

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
  try {
    const res = await fetch(API_BASE + "/auth/me", {
      method: "GET",
      credentials: "include",
    });
    if (res.ok) {
      const data = await res.json();
      showDashboard(data.username);
    } else {
      showLogin();
    }
  } catch (e) {
    console.error(e);
    showLogin();
  }
}

loginForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  loginError.classList.add("hidden");
  loginError.textContent = "";

  const formData = new FormData(loginForm);
  const username = formData.get("username") || "";
  const password = formData.get("password") || "";

  try {
    const res = await fetch(API_BASE + "/auth/login", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify({ username, password }),
    });

    if (!res.ok) {
      loginError.textContent = "Invalid credentials.";
      loginError.classList.remove("hidden");
      return;
    }

    const data = await res.json();
    showDashboard(data.username);
  } catch (err) {
    console.error(err);
    loginError.textContent = "Login failed. See console for details.";
    loginError.classList.remove("hidden");
  }
});

logoutBtn.addEventListener("click", async () => {
  try {
    await fetch(API_BASE + "/auth/logout", {
      method: "POST",
      credentials: "include",
    });
  } catch (e) {
    console.error(e);
  }
  showLogin();
});


function updateStatusPill(el, isUp) {
  if (!el) return;

  // Expect structure: outer span → [dot span, text span]
  const spans = el.querySelectorAll("span");
  const dot = spans[0];
  const textSpan = spans[1];

  if (isUp) {
    el.style.backgroundColor = "rgba(16,185,129,0.15)"; // emerald bg
    el.style.color = "#6ee7b7";
    if (dot) dot.style.backgroundColor = "#22c55e";
    if (textSpan) textSpan.textContent = "Up";
  } else {
    el.style.backgroundColor = "rgba(248,113,113,0.15)"; // red bg
    el.style.color = "#fecaca";
    if (dot) dot.style.backgroundColor = "#f97373";
    if (textSpan) textSpan.textContent = "Down";
  }
}


async function fetchHealth() {
  if (healthOutput) {
    healthOutput.textContent = "Loading...";
  }

  try {
    const res = await fetch(API_BASE + "/healthz", {
      method: "GET",
      credentials: "include",
    });
    const data = await res.json();

    // Raw JSON (debug)
    if (healthOutput) {
      healthOutput.textContent = JSON.stringify(data, null, 2);
    }

    const couchUp = !!data.couchdb;
    const chromaUp = !!data.chroma;
    const neo4jUp = !!data.neo4j;
    const embedUp = !!data.embedding_model;

    // Per-service pills
    updateStatusPill(healthCouch, couchUp);
    updateStatusPill(healthChroma, chromaUp);
    updateStatusPill(healthNeo4j, neo4jUp);
    updateStatusPill(healthEmbed, embedUp);

    // Overall pill
    if (healthOverall) {
      const spans = healthOverall.querySelectorAll("span");
      const dot = spans[0];
      const textSpan = spans[1];

      const allTrue = couchUp && chromaUp && neo4jUp && embedUp;
      const anyTrue = couchUp || chromaUp || neo4jUp || embedUp;

      if (allTrue) {
        healthOverall.style.backgroundColor = "rgba(16,185,129,0.15)";
        healthOverall.style.color = "#6ee7b7";
        if (dot) dot.style.backgroundColor = "#22c55e";
        if (textSpan) textSpan.textContent = "Overall status: All green";
      } else if (anyTrue) {
        healthOverall.style.backgroundColor = "rgba(245,158,11,0.15)";
        healthOverall.style.color = "#facc15";
        if (dot) dot.style.backgroundColor = "#f59e0b";
        if (textSpan) textSpan.textContent = "Overall status: Degraded";
      } else {
        healthOverall.style.backgroundColor = "rgba(248,113,113,0.15)";
        healthOverall.style.color = "#fecaca";
        if (dot) dot.style.backgroundColor = "#f97373";
        if (textSpan) textSpan.textContent = "Overall status: Down";
      }
    }
  } catch (e) {
    console.error(e);
    if (healthOutput) {
      healthOutput.textContent = "Failed to load health info.";
    }

    // Mark everything as down on error
    updateStatusPill(healthCouch, false);
    updateStatusPill(healthChroma, false);
    updateStatusPill(healthNeo4j, false);
    updateStatusPill(healthEmbed, false);

    if (healthOverall) {
      const spans = healthOverall.querySelectorAll("span");
      const dot = spans[0];
      const textSpan = spans[1];
      healthOverall.style.backgroundColor = "rgba(248,113,113,0.15)";
      healthOverall.style.color = "#fecaca";
      if (dot) dot.style.backgroundColor = "#f97373";
      if (textSpan) textSpan.textContent = "Overall status: Down";
    }
  }
}


refreshHealthBtn.addEventListener("click", fetchHealth);

async function fetchAgents() {

  agentsTableBody.innerHTML = "";
  try {
    const res = await fetch(API_BASE + "/ui/couch/agents?limit=100", {
      method: "GET",
      credentials: "include",
    });
    if (!res.ok) {
      agentsTableBody.innerHTML =
        "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Failed to load agents.</td></tr>";
      return;
    }
    const data = await res.json();

    // Update widget
    if (widgetTotalAgents) {
      widgetTotalAgents.textContent = data.items?.length || 0;
    }

    if (!data.items || data.items.length === 0) {
      agentsTableBody.innerHTML =
        "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>No agents yet.</td></tr>";
      return;
    }
    for (const doc of data.items) {
      const tr = document.createElement("tr");
      const metadata = doc.metadata || {};
      const createdAt = doc.created_at || doc._id || "";
      const idVal = (doc.id || doc._id || "").toString();
      const role = (metadata.role || "").toString();
      const goal = (metadata.goal || "").toString();
      const description = (metadata.description || "").toString();
      tr.innerHTML = `
        <td class="px-3 py-2 font-mono text-[11px] text-slate-200">${idVal}</td>
        <td class="px-3 py-2 text-slate-200">${role}</td>
        <td class="px-3 py-2 text-slate-200">${goal}</td>
        <td class="px-3 py-2 text-slate-200 max-w-xs truncate" title="${description}">${description}</td>
        <td class="px-3 py-2 text-slate-400 text-[11px]">${createdAt}</td>
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

async function fetchTasks() {


  tasksTableBody.innerHTML = "";
  try {
    const res = await fetch(API_BASE + "/ui/couch/tasks?limit=100", {
      method: "GET",
      credentials: "include",
    });
    if (!res.ok) {
      tasksTableBody.innerHTML =
        "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>Failed to load tasks.</td></tr>";
      return;
    }
    const data = await res.json();

    // Update widget
    if (widgetTotalTasks) {
      widgetTotalTasks.textContent = data.items?.length || 0;
    }


    if (!data.items || data.items.length === 0) {
      tasksTableBody.innerHTML =
        "<tr><td colspan='5' class='px-3 py-3 text-center text-slate-400'>No tasks yet.</td></tr>";
      return;
    }
    for (const doc of data.items) {
      const tr = document.createElement("tr");
      const metadata = doc.metadata || {};
      const createdAt = doc.created_at || doc._id || "";
      const idVal = (doc.id || doc._id || "").toString();
      const agentId = (doc.agent_id || "").toString();
      const role = (metadata.role || "").toString();
      const goal = (metadata.goal || "").toString();
      tr.innerHTML = `
        <td class="px-3 py-2 font-mono text-[11px] text-slate-200">${idVal}</td>
        <td class="px-3 py-2 font-mono text-[11px] text-slate-300">${agentId}</td>
        <td class="px-3 py-2 text-slate-200">${role}</td>
        <td class="px-3 py-2 text-slate-200 max-w-xs truncate" title="${goal}">${goal}</td>
        <td class="px-3 py-2 text-slate-400 text-[11px]">${createdAt}</td>
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

function showNodeDetails(node) {
  if (!nodeDetailsPanel) return;

  const meta = node.metadata || node.properties || {};
  const safeId = (node.shortid || node.id || "").toString();

  nodeDetailsTitle.textContent = `${node.label} details`;
  nodeDetailsType.textContent = node.label || "";
  nodeDetailsId.textContent = safeId;
  nodeDetailsRole.textContent = meta.role || node.role || "";
  nodeDetailsGoal.textContent = meta.goal || node.goal || "";
  nodeDetailsDescription.textContent = meta.description || node.description || node.preview || "";
  nodeDetailsStep.textContent =
    typeof node.step_index === "number" ? String(node.step_index) : "";

  // Pretty-print metadata/properties
  let metaObject = meta;
  if (!Object.keys(metaObject).length && node.properties) {
    metaObject = node.properties;
  }
  nodeDetailsMeta.textContent = JSON.stringify(metaObject, null, 2);

  nodeDetailsPanel.classList.remove("hidden");
}

if (nodeDetailsClose && nodeDetailsPanel) {
  nodeDetailsClose.addEventListener("click", () => {
    nodeDetailsPanel.classList.add("hidden");
  });
}

async function fetchGraph() {
  if (!graphContainer) return;
  graphContainer.innerHTML = "";
  const loading = document.createElement("div");
  loading.className =
    "w-full h-full flex items-center justify-center text-xs text-slate-400";
  loading.textContent = "Loading graph from Neo4j...";
  graphContainer.appendChild(loading);

  try {
    const res = await fetch(API_BASE + "/ui/graph?limit=200", {
      method: "GET",
      credentials: "include",
    });
    if (!res.ok) {
      graphContainer.innerHTML =
        "<div class='w-full h-full flex items-center justify-center text-xs text-red-400'>Failed to load graph.</div>";
      return;
    }
    const data = await res.json();
    renderGraph(data);
  } catch (e) {
    console.error(e);
    graphContainer.innerHTML =
      "<div class='w-full h-full flex items-center justify-center text-xs text-red-400'>Error loading graph.</div>";
  }
}

function renderGraph(data) {
  if (!graphContainer) return;
  graphContainer.innerHTML = "";

  const nodes = (data && data.nodes) ? data.nodes.slice() : [];
  const links = (data && (data.edges || data.links)) ? data.edges || data.links : [];

  if (nodes.length === 0) {
    graphContainer.innerHTML =
      "<div class='w-full h-full flex items-center justify-center text-xs text-slate-400'>No nodes yet. Create some agents, tasks, and thoughts first.</div>";
    return;
  }

  const rect = graphContainer.getBoundingClientRect();
  const width = rect.width || 600;
  const height = rect.height || 320;

  const svg = d3.select(graphContainer)
    .append("svg")
    .attr("width", width)
    .attr("height", height);

  const g = svg.append("g");

  const zoom = d3.zoom()
    .scaleExtent([0.3, 3])
    .on("zoom", (event) => {
      g.attr("transform", event.transform);
    });

  svg.call(zoom);

  const link = g.append("g")
    .attr("stroke", "#64748b")
    .attr("stroke-opacity", 0.6)
    .selectAll("line")
    .data(links)
    .join("line")
    .attr("stroke-width", d => {
      if (d.type === "BELONGS_TO") return 1.5;
      if (d.type === "GENERATED_THOUGHT") return 1;
      if (d.type === "HAS_THOUGHT") return 1;
      return 1;
    })
    .attr("stroke-dasharray", d => {
      if (d.type === "GENERATED_THOUGHT" || d.type === "HAS_THOUGHT") return "2,2";
      return "0";
    });

  const node = g.append("g")
    .attr("stroke", "#0f172a")
    .attr("stroke-width", 1.5)
    .selectAll("circle")
    .data(nodes)
    .join("circle")
    .attr("r", d => {
      if (d.label === "Agent") return 10;
      if (d.label === "Task") return 7;
      return 5; // Thought
    })
    .attr("fill", d => {
      if (d.label === "Agent") return "#4f46e5";   // indigo
      if (d.label === "Task") return "#0ea5e9";    // sky
      return "#f97316";                            // thoughts: amber
    })
    .on("click", (event, d) => {
      event.stopPropagation();
      showNodeDetails(d);
    });

  const labels = g.append("g")
    .selectAll("text")
    .data(nodes)
    .join("text")
    .attr("font-size", 9)
    .attr("fill", "#e2e8f0")
    .attr("stroke", "none")
    .attr("text-anchor", "middle")
    .text(d => {
      if (d.label === "Agent") return d.shortid || "Agent";
      if (d.label === "Task") return d.shortid || "Task";
      if (d.label === "Thought") {
        if (typeof d.step_index === "number") return `th#${d.step_index}`;
        return (d.shortid || "Thought").slice(0, 6);
      }
      return d.shortid || "";
    });

  // Richer tooltips using metadata
  node.append("title")
    .text(d => {
      const meta = d.metadata || {};
      const lines = [];

      if (d.label === "Agent" || d.label === "Task") {
        lines.push(`${d.label}: ${d.shortid || d.id}`);
        if (meta.role || d.role) lines.push(`Role: ${meta.role || d.role}`);
        if (meta.goal || d.goal) lines.push(`Goal: ${meta.goal || d.goal}`);
        if (meta.description || d.description) {
          const desc = meta.description || d.description;
          lines.push(`Desc: ${desc.length > 80 ? desc.slice(0, 77) + "..." : desc}`);
        }
      } else if (d.label === "Thought") {
        lines.push(`Thought: ${d.shortid || d.id}`);
        if (typeof d.step_index === "number") lines.push(`Step: ${d.step_index}`);
        if (d.preview) lines.push(`Preview: ${d.preview}`);
      } else {
        lines.push(`${d.label || "Node"}: ${d.shortid || d.id}`);
      }

      return lines.join("\n");
    });

  const simulation = d3.forceSimulation(nodes)
    .force("link", d3.forceLink(links).id(d => d.id).distance(60))
    .force("charge", d3.forceManyBody().strength(-20)) 
    .force("center", d3.forceCenter(width / 2, height / 2))
    .force("collide", d3.forceCollide().radius(d => {
      if (d.label === "Agent") return 12;
      if (d.label === "Task") return 9;
      return 7; // Thought
    }));

  node.call(drag(simulation));

  simulation.on("tick", () => {
    link
      .attr("x1", d => d.source.x)
      .attr("y1", d => d.source.y)
      .attr("x2", d => d.target.x)
      .attr("y2", d => d.target.y);

    node
      .attr("cx", d => d.x)
      .attr("cy", d => d.y);

    labels
      .attr("x", d => d.x)
      .attr("y", d => d.y - 12);
  });

  function drag(simulation) {
    function dragstarted(event, d) {
      if (!event.active) simulation.alphaTarget(0.3).restart();
      d.fx = d.x;
      d.fy = d.y;
    }

    function dragged(event, d) {
      d.fx = event.x;
      d.fy = event.y;
    }

    function dragended(event, d) {
      if (!event.active) simulation.alphaTarget(0);
      // keep node pinned
    }

    return d3.drag()
      .on("start", dragstarted)
      .on("drag", dragged)
      .on("end", dragended);
  }
}


refreshGraphBtn.addEventListener("click", fetchGraph);

createAgentForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  createAgentResult.textContent = "";
  const formData = new FormData(createAgentForm);
  const metadata = {
    role: formData.get("role") || "",
    goal: formData.get("goal") || "",
    backstory: formData.get("backstory") || "",
    description: formData.get("description") || "",
  };

  try {
    const body = {
      method: "create_id",
      params: { metadata },
      id: "ui",
    };
    const res = await fetch(API_BASE + "/ui/agents", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    if (!res.ok) {
      createAgentResult.textContent = "Failed to create agent.";
      return;
    }
    const data = await res.json();
    const newId = (data.result && data.result.id) || "unknown";
    createAgentResult.textContent = "Created agent ID: " + newId;
    createAgentForm.reset();
    fetchAgents();
    fetchGraph();
  } catch (e) {
    console.error(e);
    createAgentResult.textContent = "Error creating agent.";
  }
});

createTaskForm.addEventListener("submit", async (e) => {
  e.preventDefault();
  createTaskResult.textContent = "";
  const formData = new FormData(createTaskForm);
  const agent_id = (formData.get("agent_id") || "").toString().trim();
  const metadata = {
    role: formData.get("role") || "",
    goal: formData.get("goal") || "",
    description: formData.get("description") || "",
  };

  if (!agent_id) {
    createTaskResult.textContent = "Agent ID is required.";
    return;
  }

  try {
    const body = {
      method: "create_id",
      params: { agent_id, metadata },
      id: "ui-task",
    };
    const res = await fetch(API_BASE + "/ui/tasks", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      credentials: "include",
      body: JSON.stringify(body),
    });
    const data = await res.json();
    if (!res.ok || data.error) {
      const message =
        (data.error && data.error.message) || "Failed to create task.";
      createTaskResult.textContent = message;
      return;
    }
    const newId = (data.result && data.result.id) || "unknown";
    createTaskResult.textContent = "Created task ID: " + newId;
    createTaskForm.reset();
    fetchTasks();
    fetchGraph();
  } catch (e) {
    console.error(e);
    createTaskResult.textContent = "Error creating task.";
  }
});

// init
checkSession();
