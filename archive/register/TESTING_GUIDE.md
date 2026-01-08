# Testing Guide - AWS-Styled UI

This guide will help you test the new AWS-styled Agent Registry Admin UI.

## Prerequisites

Before testing, ensure you have:
- Python 3.10 or higher
- CouchDB running (for storing agents/tasks)
- Neo4j running (for graph visualization)
- Chroma DB (for embeddings - optional)

## Quick Start

### Option 1: Test with Full Backend (Recommended)

1. **Navigate to the register directory:**
   ```bash
   cd /Users/roberto/Documents/vecgraph-main/register
   ```

2. **Activate the virtual environment:**
   ```bash
   source .venv/bin/activate
   ```

3. **Check if dependencies are installed:**
   ```bash
   python -c "import fastapi, uvicorn, couchdb; print('Dependencies OK')"
   ```

   If you get an error, install dependencies:
   ```bash
   pip install -r pyproject.toml
   # or if using uv:
   uv pip install -e .
   ```

4. **Start the backend server:**
   ```bash
   python main.py
   ```

   You should see output like:
   ```
   INFO:     Started server process
   INFO:     Waiting for application startup.
   INFO:     Application startup complete.
   INFO:     Uvicorn running on http://0.0.0.0:8080
   ```

5. **Open your browser:**
   ```
   http://localhost:8080
   ```

6. **Login with demo credentials:**
   - Username: `admin`
   - Password: `Psalm121@`

### Option 2: Test UI Only (Static Preview)

If you just want to see the UI design without backend functionality:

1. **Open the HTML file directly in your browser:**
   ```bash
   open /Users/roberto/Documents/vecgraph-main/register/frontend/index.html
   ```

   Or drag the file into your browser.

2. **Note:** Some features won't work without the backend (login, data fetching), but you can see the AWS-styled design.

### Option 3: Simple HTTP Server

If you want to test the UI with a simple server:

```bash
cd /Users/roberto/Documents/vecgraph-main/register/frontend
python3 -m http.server 8000
```

Then open: http://localhost:8000

## What to Test

### 1. Login Screen
- [ ] AWS-style login card with orange button
- [ ] Dark gradient background (#232f3e to #1b2631)
- [ ] Input fields with blue focus states
- [ ] Error messages display in red
- [ ] Responsive layout

### 2. Dashboard Header
- [ ] Dark AWS header (#232f3e)
- [ ] Orange logo badge (#ff9900)
- [ ] User label and sign out button
- [ ] Consistent spacing

### 3. System Health Section
- [ ] White container with subtle shadow
- [ ] Dark code block for JSON output
- [ ] Refresh button (secondary style)
- [ ] Clean typography

### 4. Quick Actions (Create Agent/Task)
- [ ] Side-by-side cards on larger screens
- [ ] Stacked on mobile
- [ ] Orange submit buttons
- [ ] Form inputs with proper styling
- [ ] Success/error messages

### 5. Data Tables (Agents & Tasks)
- [ ] Clean AWS-style tables
- [ ] Light gray headers
- [ ] Row hover effects
- [ ] Responsive overflow
- [ ] Badges for roles (blue for agents, green for tasks)
- [ ] Monospace font for IDs

### 6. Graph Visualization
- [ ] Light background (#fafafa)
- [ ] Blue nodes for Agents
- [ ] Green nodes for Tasks
- [ ] Draggable nodes
- [ ] Zoom/pan functionality
- [ ] Clean borders

### 7. Responsive Design
- [ ] Test on desktop (1920px, 1440px, 1024px)
- [ ] Test on tablet (768px)
- [ ] Test on mobile (375px, 414px)
- [ ] Grid layouts adapt properly
- [ ] Navigation stays functional

## Troubleshooting

### Backend won't start
**Check logs:**
```bash
tail -f /Users/roberto/Documents/vecgraph-main/register/logs/shortid.log
```

**Common issues:**
- CouchDB not running: Start CouchDB service
- Neo4j not running: Start Neo4j service
- Port 8080 already in use: Change PORT in config/.env

### UI loads but no data appears
- Check browser console (F12) for errors
- Verify backend is running and accessible
- Check that backend endpoints are responding:
  ```bash
  curl http://localhost:8080/healthz
  ```

### Login doesn't work
- Ensure backend is running
- Check browser console for CORS errors
- Verify credentials: `admin` / `Psalm121@`
- Check that config/.env has the correct ADMIN_PASSWORD

## Features to Verify

### Visual Features
- ✅ AWS orange (#ec7211) on primary buttons
- ✅ AWS blue (#0972d3) on focus states
- ✅ AWS dark blue (#232f3e) on header
- ✅ Light gray (#f2f3f3) background
- ✅ White containers with subtle shadows
- ✅ Clean typography (Amazon Ember-like fonts)

### Functional Features
- ✅ Session management (login/logout)
- ✅ Create agents with metadata
- ✅ Create tasks linked to agents
- ✅ View agents table from CouchDB
- ✅ View tasks table from CouchDB
- ✅ Interactive graph from Neo4j
- ✅ System health monitoring
- ✅ Refresh buttons for all sections

## Browser Compatibility

Tested and recommended browsers:
- ✅ Chrome 90+
- ✅ Firefox 88+
- ✅ Safari 14+
- ✅ Edge 90+

## Next Steps

After testing, you can:
1. Customize colors in the `<style>` section
2. Add more AWS components
3. Enhance the graph visualization
4. Add filtering/searching to tables
5. Implement pagination

## Need Help?

Check these files:
- UI: `/Users/roberto/Documents/vecgraph-main/register/frontend/index.html`
- Backend: `/Users/roberto/Documents/vecgraph-main/register/main.py`
- Config: `/Users/roberto/Documents/vecgraph-main/register/config/.env`
- Logs: `/Users/roberto/Documents/vecgraph-main/register/logs/shortid.log`
