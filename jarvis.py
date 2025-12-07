from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse, HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from datetime import datetime, timedelta
import subprocess, json, os, logging, time, sys, signal, atexit
import threading
from pathlib import Path
from collections import defaultdict

from tools import json_manager
from tools.smart_json_dispatcher import orchestrate_write
from system_guard import validate_action, ContractViolation

app = FastAPI()
BASE_DIR = os.path.abspath(os.path.dirname(__file__))

# 🔧 Engine Management
engine_processes = []
ENGINE_REGISTRY_PATH = os.path.join(BASE_DIR, "data/engine_registry.json")

def start_engines():
    """Start all engines as subprocesses when server starts"""
    global engine_processes
    
    if not os.path.exists(ENGINE_REGISTRY_PATH):
        logging.warning(f"⚠️  Engine registry not found at {ENGINE_REGISTRY_PATH}")
        return
    
    # Ensure logs directory exists
    logs_dir = os.path.join(BASE_DIR, "logs")
    os.makedirs(logs_dir, exist_ok=True)
    
    try:
        with open(ENGINE_REGISTRY_PATH, 'r') as f:
            registry = json.load(f)
        
        engines = registry.get('engines', [])
        
        for engine_file in engines:
            engine_path = os.path.join(BASE_DIR, "tools", engine_file)
            
            if not os.path.exists(engine_path):
                logging.warning(f"⚠️  Engine not found: {engine_path}")
                continue
            
            try:
                log_path = os.path.join(logs_dir, f"{engine_file}.log")
                log_file = open(log_path, 'a')
                
                # Write startup marker
                log_file.write(f"\n{'='*60}\n")
                log_file.write(f"Started: {datetime.now().isoformat()}\n")
                log_file.write(f"{'='*60}\n\n")
                log_file.flush()
                
                proc = subprocess.Popen(
                    [sys.executable, engine_path, "run_engine"],
                    cwd=BASE_DIR,
                    stdout=log_file,
                    stderr=log_file,
                    start_new_session=False
                )
                engine_processes.append({
                    'name': engine_file,
                    'process': proc,
                    'pid': proc.pid,
                    'log_file': log_file
                })
                logging.info(f"✅ Started {engine_file} (PID: {proc.pid})")
            except Exception as e:
                logging.error(f"❌ Failed to start {engine_file}: {e}")
        
        logging.info(f"🚀 Started {len(engine_processes)} engine(s)")
        
    except Exception as e:
        logging.error(f"❌ Failed to load engine registry: {e}")


def stop_engines():
    """Stop all engines when server shuts down"""
    global engine_processes
    
    if not engine_processes:
        return
    
    logging.info("🛑 Stopping engines...")
    
    for engine in engine_processes:
        try:
            proc = engine['process']
            name = engine['name']
            
            # Graceful shutdown
            proc.terminate()
            
            try:
                proc.wait(timeout=5)
                logging.info(f"✅ Stopped {name}")
            except subprocess.TimeoutExpired:
                # Force kill if not responding
                proc.kill()
                proc.wait()
                logging.warning(f"⚠️  Force killed {name}")
                
        except Exception as e:
            logging.error(f"❌ Error stopping {engine['name']}: {e}")
    
    engine_processes = []
    logging.info("✅ All engines stopped")


def handle_shutdown(signum, frame):
    """Handle shutdown signals"""
    logging.info(f"Received signal {signum}, shutting down...")
    stop_engines()
    sys.exit(0)


# Register shutdown handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)
atexit.register(stop_engines)


@app.on_event("startup")
async def startup_event():
    """Start engines when FastAPI server starts"""
    logging.info("🚀 Starting OrchestrateOS...")
    start_engines()


@app.on_event("shutdown")
async def shutdown_event():
    """Stop engines when FastAPI server shuts down"""
    stop_engines()


# 🩺 Engine Health Check
@app.get("/health/engines")
def engine_health():
    """Check status of all engines"""
    status = []
    
    for engine in engine_processes:
        proc = engine['process']
        name = engine['name']
        pid = engine['pid']
        
        # Check if still running
        if proc.poll() is None:
            status.append({
                'name': name,
                'pid': pid,
                'status': 'running'
            })
        else:
            status.append({
                'name': name,
                'pid': pid,
                'status': 'dead',
                'exit_code': proc.returncode
            })
    
    running_count = sum(1 for e in status if e['status'] == 'running')
    
    return {
        'total_engines': len(status),
        'running': running_count,
        'engines': status,
        'health': 'healthy' if running_count == len(status) else 'degraded'
    }


# 🚦 Rate limiting state (in-memory)
rate_limit_state = defaultdict(list)
RATE_LIMITS = {
    "/execute_task": {"requests": 60, "window_seconds": 60},
    "/get_supported_actions": {"requests": 10, "window_seconds": 60}
}

# 🔒 System paths
SYSTEM_REGISTRY = os.path.join(BASE_DIR, "system_settings.ndjson")
WORKING_MEMORY_PATH = os.path.join(BASE_DIR, "data/working_memory.json")
EXEC_HUB_PATH = os.path.join(BASE_DIR, "execution_hub.py")
DASHBOARD_INDEX_PATH = os.path.join(BASE_DIR, "data/dashboard_index.json")

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

# 📦 Static mounts
app.mount(
    "/semantic_memory",
    StaticFiles(directory=os.path.join(BASE_DIR, "semantic_memory")),
    name="semantic_memory"
)

app.mount(
    "/landing_page_template_thumbnails",
    StaticFiles(directory=os.path.join(BASE_DIR, "landing_page_template_thumbnails")),
    name="landing_page_template_thumbnails"
)

# 🚦 Rate limiting middleware
def check_rate_limit(endpoint: str, client_id: str = "default"):
    """Check if request should be rate limited"""
    if endpoint not in RATE_LIMITS:
        return True

    config = RATE_LIMITS[endpoint]
    now = time.time()
    window_start = now - config["window_seconds"]

    key = f"{endpoint}:{client_id}"
    rate_limit_state[key] = [ts for ts in rate_limit_state[key] if ts > window_start]

    if len(rate_limit_state[key]) >= config["requests"]:
        return False

    rate_limit_state[key].append(now)
    return True


# 🛠 Run a tool action via subprocess
def run_script(tool_name, action, params):
    command = [
        sys.executable, EXEC_HUB_PATH, "execute_task", "--params", json.dumps({
            "tool_name": tool_name,
            "action": action,
            "params": params
        })
    ]
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=90)
        return json.loads(result.stdout.strip())
    except Exception as e:
        return {"error": "Execution failed", "details": str(e)}


# 🎯 Execute a tool via HTTP POST
@app.post("/execute_task")
async def execute_task(request: Request):
    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit("/execute_task", client_id):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Limit: 60 req/min per client.",
                "retry_after": 60
            }
        )

    try:
        request_data = await request.json()
        tool_name = request_data.get("tool_name")
        action_name = request_data.get("action")
        params = request_data.get("params", {})

        if not tool_name or not action_name:
            raise HTTPException(status_code=400, detail="Missing tool_name or action.")

        if tool_name == "system_control" and action_name == "load_orchestrate_os":
            result = subprocess.run(
                [sys.executable, EXEC_HUB_PATH, "load_orchestrate_os"],
                capture_output=True,
                text=True,
                timeout=10
            )
            return json.loads(result.stdout.strip())

        if tool_name == "json_manager" and action_name == "orchestrate_write":
            return orchestrate_write(**params)

        params = validate_action(tool_name, action_name, params)
        result = run_script(tool_name, action_name, params)

        if "error" in result:
            raise HTTPException(status_code=500, detail=result)

        return result

    except ContractViolation as e:
        return JSONResponse(status_code=400, content={"error": str(e)})
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": "Execution failed",
            "details": str(e)
        })


# 🚀 Load dashboard data dynamically from dashboard_index.json
def load_dashboard_data():
    """Load dashboard using config-driven approach"""
    try:
        with open(DASHBOARD_INDEX_PATH, 'r', encoding='utf-8') as f:
            dashboard_config = json.load(f)
        
        dashboard_data = {}
        
        for item in dashboard_config.get("dashboard_items", []):
            key = item.get("key")
            source_type = item.get("source")
            
            try:
                if source_type == "file":
                    filepath = os.path.join(BASE_DIR, item.get("file"))
                    with open(filepath, 'r', encoding='utf-8') as f:
                        data = json.load(f)
                        dashboard_data[key] = data
                        
                elif source_type == "tool_action":
                    tool_name = item.get("tool")
                    action = item.get("action")
                    params = item.get("params", {})
                    result = run_script(tool_name, action, params)
                    dashboard_data[key] = result
                    
            except Exception as e:
                dashboard_data[key] = {"error": f"Could not load {key}: {str(e)}"}
        
        formatted_output = format_dashboard_display(dashboard_data, dashboard_config)
        
        return {
            "status": "success", 
            "dashboard_data": formatted_output
        }
        
    except Exception as e:
        return {"error": f"Failed to load dashboard: {str(e)}"}


def format_dashboard_display(data, config):
    """Convert JSON data to formatted output based on config"""
    formatted = {}
    
    for item in config.get("dashboard_items", []):
        key = item.get("key")
        formatter = item.get("formatter")
        
        if key not in data:
            continue
            
        raw_data = data[key]
        
        if formatter == "intent_routes_table":
            formatted[key] = format_intent_routes(raw_data)
        elif formatter == "calendar_list":
            formatted[key] = format_calendar_events(raw_data)
        elif formatter == "thread_log_list":
            formatted[key] = format_thread_log(raw_data, item.get("limit", 5))
        elif formatter == "ideas_list":
            formatted[key] = format_ideas_reminders(raw_data, item.get("limit", 10))
        else:
            formatted[key] = raw_data
    
    return formatted


def format_intent_routes(data):
    """Format intent routes as table + full data"""
    if not isinstance(data, dict):
        return {"display_table": "No data", "entries": {}}
    
    routes_data = data.get("entries", {})
    intent_table = "| Icon | Intent | Description | Tool | Action |\n|------|--------|-------------|------|--------|\n"
    
    for key, route in routes_data.items():
        if isinstance(route, dict):
            icon = route.get("icon", "") or route.get("updates", {}).get("icon", "") or route.get("update", {}).get("icon", "") or "🔧"
            intent = route.get("intent", key)
            description = route.get("description", "")[:60]
            tool_name = route.get("tool_name", "")
            action = route.get("action", "")
            intent_table += f"| {icon} | {intent} | {description} | {tool_name} | {action} |\n"
    
    return {
        "display_table": intent_table,
        "entries": routes_data
    }


def format_calendar_events(data):
    """Format calendar events as list with participants"""
    events = []

    if isinstance(data, dict):
        if "events" in data:
            events = data["events"]
        elif "data" in data:
            events = data["data"]
    elif isinstance(data, list):
        events = data

    if events:
        cal_list = "📅 **Calendar Events:**\n\n"
        for event in events[:5]:
            title = event.get("title", "No title")
            when = event.get("when", {})
            start_time = when.get("start_time", when.get("start", ""))
            if isinstance(start_time, (int, float)):
                start_time = datetime.fromtimestamp(start_time).strftime("%m/%d %H:%M")

            participants = event.get("participants", [])
            user_email = "srinirao"

            other_participants = [
                p for p in participants
                if p.get("email") != user_email
            ]

            participant_names = []
            for p in other_participants:
                name = p.get("name") or p.get("email", "")
                if name:
                    participant_names.append(name)

            if participant_names:
                participants_str = " + ".join(participant_names)
                cal_list += f"• **{start_time}**: {title} (with {participants_str})\n"
            else:
                cal_list += f"• **{start_time}**: {title}\n"

        return cal_list
    else:
        return "📅 **Calendar Events:** No upcoming events"


def format_thread_log(data, limit=5):
    """Format thread log as list"""
    if not isinstance(data, dict):
        return "📋 **Thread Log:** No entries"
    
    entries_data = data.get("entries", data)
    if entries_data:
        thread_list = "📋 **Thread Log:**\n\n"
        for key, entry in list(entries_data.items())[-limit:]:
            status = entry.get("status", "unknown").upper()
            goal = entry.get("context_goal", key)[:60]
            thread_list += f"• **{status}**: {goal}\n"
        return thread_list
    else:
        return "📋 **Thread Log:** No entries"


def format_ideas_reminders(data, limit=10):
    """Format ideas and reminders as list"""
    if not isinstance(data, dict):
        return "💡 **Ideas & Reminders:** No entries"
    
    entries_data = data.get("entries", data)
    if entries_data:
        ideas_list = "💡 **Ideas & Reminders:**\n\n"
        for key, item in list(entries_data.items())[-limit:]:
            if isinstance(item, dict):
                item_type = item.get("type", "idea")
                title = item.get("title", item.get("content", key))[:60]
                ideas_list += f"• **{item_type.title()}**: {title}\n"
            else:
                ideas_list += f"• **Idea**: {str(item)[:60]}\n"
        return ideas_list
    else:
        return "💡 **Ideas & Reminders:** No entries"


@app.get("/get_supported_actions")
def get_supported_actions(request: Request, offset: int = 0, limit: int = 50):
    """Return actions in chunks - auto-paginate"""
    client_id = request.client.host if request.client else "unknown"
    if not check_rate_limit("/get_supported_actions", client_id):
        return JSONResponse(
            status_code=429,
            content={
                "error": "Rate limit exceeded",
                "message": "Too many requests. Limit: 10 req/min per client.",
                "retry_after": 60
            }
        )

    try:
        with open(SYSTEM_REGISTRY, "r") as f:
            entries = [json.loads(line.strip()) for line in f if line.strip()]
        
        lean_actions = []
        for entry in entries:
            if entry.get("action") == "__tool__":
                continue
            
            lean_entry = {
                "tool": entry.get("tool"),
                "action": entry.get("action"),
                "params": entry.get("params", []),
                "description": entry.get("description", "")[:100]
            }
            lean_actions.append(lean_entry)
        
        total = len(lean_actions)
        paginated = lean_actions[offset:offset+limit]
        
        return {
            "status": "success",
            "supported_actions": paginated,
            "pagination": {
                "total": total,
                "offset": offset,
                "limit": limit,
                "returned": len(paginated),
                "has_more": (offset + limit) < total,
                "next_offset": offset + limit if (offset + limit) < total else None
            }
        }
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/get_dashboard_file/{file_key}")
def get_dashboard_file(file_key: str):
    """Load specific dashboard files when needed or full dashboard"""
    
    if file_key == "full_dashboard":
        dashboard = load_dashboard_data()
        return dashboard
    
    file_map = {
        "phrase_promotions": "data/phrase_insight_promotions.json",
        "runtime_contract": "orchestrate_runtime_contract.json", 
        "tool_build_protocol": "data/tool_build_protocol.json",
        "podcast_prep_rules": "podcast_prep_guidelines.json",
        "thread_log_full": "data/thread_log.json",
        "ideas_and_reminders_full": "data/ideas_reminders.json"
    }
    
    if file_key not in file_map:
        raise HTTPException(status_code=404, detail=f"File key '{file_key}' not found")
    
    try:
        filepath = file_map[file_key]
        abs_path = os.path.join(BASE_DIR, filepath)
        
        with open(abs_path, 'r', encoding='utf-8') as f:
            data = json.load(f)
            
        return {
            "status": "success",
            "file_key": file_key,
            "data": data
        }
        
    except Exception as e:
        return JSONResponse(status_code=500, content={
            "error": f"Could not load {file_key}",
            "details": str(e)
        })


@app.post("/load_memory")
def load_memory():
    """Build real-time contract cache WITHOUT bloated examples"""
    try:
        memory_path = os.path.join(BASE_DIR, "data/working_memory.json")
        working_memory = {}
        if os.path.exists(memory_path):
            with open(memory_path, "r") as f:
                working_memory = json.load(f)
        
        corrections_path = os.path.join(BASE_DIR, "data/param_corrections.json")
        with open(corrections_path, "r") as f:
            param_corrections = json.load(f)
        
        with open(SYSTEM_REGISTRY, "r") as f:
            registry_entries = [json.loads(line.strip()) for line in f if line.strip()]
        
        contract_cache = {}
        for entry in registry_entries:
            if entry.get("action") != "__tool__":
                tool_action = f"{entry['tool']}.{entry['action']}"
                contract_cache[tool_action] = {
                    "required_params": entry.get("params", []),
                    "description": entry.get("description", "")[:100]
                }
        
        return {
            "status": "success",
            "working_memory": working_memory,
            "contract_cache": contract_cache,
            "param_corrections": param_corrections,
            "loaded_contracts": len(contract_cache),
            "memory_entries": len(working_memory),
            "refresh_timestamp": datetime.now().isoformat()
        }
        
    except Exception as e:
        return {"error": f"Failed to build contract cache: {str(e)}"}


@app.get("/")
def root():
    return {"status": "Jarvis core is online."}


@app.get("/health/queue_processor")
def queue_processor_health():
    """Health check for claude_execution_engine"""
    try:
        import psutil

        running = False
        pid = None
        uptime_seconds = None

        for proc in psutil.process_iter(['pid', 'name', 'cmdline', 'create_time']):
            try:
                cmdline = proc.info.get('cmdline', [])
                if cmdline and 'claude_execution_engine.py' in ' '.join(cmdline):
                    running = True
                    pid = proc.info['pid']
                    create_time = proc.info['create_time']
                    uptime_seconds = int(time.time() - create_time)
                    break
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue

        queue_file = os.path.join(BASE_DIR, "data/claude_task_queue.json")
        task_stats = {"queued": 0, "in_progress": 0, "completed": 0, "error": 0}

        if os.path.exists(queue_file):
            try:
                with open(queue_file, 'r') as f:
                    queue_data = json.load(f)
                    tasks = queue_data.get("tasks", {})
                    for task_id, task_data in tasks.items():
                        if isinstance(task_data, dict):
                            status = task_data.get("status", "queued")
                            if status in task_stats:
                                task_stats[status] += 1
            except Exception:
                pass

        exec_log_file = os.path.join(BASE_DIR, "data/execution_log.json")
        recent_errors = 0
        last_execution_time = None

        if os.path.exists(exec_log_file):
            try:
                with open(exec_log_file, 'r') as f:
                    exec_log = json.load(f)
                    if isinstance(exec_log, list) and len(exec_log) > 0:
                        cutoff = (datetime.now() - timedelta(hours=24)).isoformat()
                        for entry in exec_log:
                            if isinstance(entry, dict):
                                timestamp = entry.get("timestamp", "")
                                if timestamp > cutoff:
                                    if entry.get("status") == "error":
                                        recent_errors += 1

                        last_entry = exec_log[-1]
                        last_execution_time = last_entry.get("timestamp")
            except Exception:
                pass

        lockfile = os.path.join(BASE_DIR, "data/execute_queue.lock")
        lockfile_exists = os.path.exists(lockfile)

        return {
            "status": "running" if running else "stopped",
            "running": running,
            "pid": pid,
            "uptime_seconds": uptime_seconds,
            "task_stats": task_stats,
            "recent_errors_24h": recent_errors,
            "last_execution_time": last_execution_time,
            "lockfile_present": lockfile_exists,
            "health": "healthy" if running and not lockfile_exists else "degraded" if running else "critical"
        }

    except ImportError:
        return {
            "status": "error",
            "message": "psutil module not installed",
            "health": "unknown"
        }
    except Exception as e:
        return {
            "status": "error",
            "message": str(e),
            "health": "unknown"
        }


# === Lead Capture ===
class LeadCapture(BaseModel):
    name: str
    email: str

LEADS_FILE = f"{BASE_DIR}/data/orchestrate_leads.json"
PDF_PATH = f"{BASE_DIR}/semantic_memory/docs/the-hidden-neuroscience-of-ai-companion-toys.pdf"

@app.post("/ai-toys/submit")
async def ai_toys_submit(lead: LeadCapture):
    try:
        if os.path.exists(LEADS_FILE):
            with open(LEADS_FILE, 'r') as f:
                leads = json.load(f)
        else:
            leads = {"leads": []}

        leads["leads"].append({
            "name": lead.name,
            "email": lead.email,
            "source": "ai-toys",
            "timestamp": datetime.now().isoformat()
        })

        os.makedirs(os.path.dirname(LEADS_FILE), exist_ok=True)
        with open(LEADS_FILE, 'w') as f:
            json.dump(leads, f, indent=2)

        return {"status": "success"}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/ai-toys/download", response_class=HTMLResponse)
async def ai_toys_download_page():
    html = """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Download Your PDF</title>
        <style>
            body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
            h1 { font-size: 28px; margin-bottom: 20px; }
            p { color: #666; margin-bottom: 30px; }
            a { display: inline-block; padding: 12px 24px; background: #000; color: #fff; text-decoration: none; border-radius: 6px; font-size: 16px; }
            a:hover { background: #333; }
        </style>
    </head>
    <body>
        <h1>✅ Thank You!</h1>
        <p>Click below to download your PDF</p>
        <a href="/ai-toys/pdf" download>Download PDF</a>
    </body>
    </html>
    """
    return HTMLResponse(content=html)

@app.get("/ai-toys/pdf")
async def ai_toys_pdf():
    if not os.path.exists(PDF_PATH):
        raise HTTPException(status_code=404, detail="PDF not found")
    return FileResponse(PDF_PATH, media_type="application/pdf", filename="the-hidden-neuroscience-of-ai-companion-toys.pdf")

@app.get("/unsubscribe")
async def unsubscribe(email: str):
    """Handle unsubscribe requests from email links"""
    try:
        result = run_script("newsletter_tool", "unsubscribe_contact", {"email": email})
        
        if result.get("status") == "success":
            html = """
<!DOCTYPE html>
<html>
<head>
    <title>Unsubscribed</title>
    <style>
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; text-align: center; }
        h1 { font-size: 28px; margin-bottom: 20px; }
        p { color: #666; margin-bottom: 30px; }
    </style>
</head>
<body>
    <h1>✓ You've Been Unsubscribed</h1>
    <p>You won't receive any more emails from us.</p>
</body>
</html>
"""
            return HTMLResponse(content=html)
        else:
            raise HTTPException(status_code=400, detail=result.get("message", "Failed to unsubscribe"))
            
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# === Beta Signup ===
class BetaSignup(BaseModel):
    full_name: str
    email: str
    use_case: str
    excited_tools: str  # Comma-separated string from form
    ai_experience: str
    why_early_access: str
    gpt_plus: str = ""
    claude_sub: str = ""

BETA_FILE = f"{BASE_DIR}/data/orchestrate_private_beta.json"

@app.get("/beta/signup", response_class=HTMLResponse)
async def beta_signup_page():
    """Serve the beta signup form"""
    html_path = os.path.join(BASE_DIR, "semantic_memory/html/beta-signup.html")
    with open(html_path, 'r') as f:
        return HTMLResponse(content=f.read())

@app.post("/beta/signup")
async def beta_signup_submit(signup: BetaSignup):
    """Handle beta signup form submission"""
    try:
        # Load existing data
        if os.path.exists(BETA_FILE):
            with open(BETA_FILE, 'r') as f:
                data = json.load(f)
        else:
            data = {"entries": {}}

        # Check for duplicate email
        if signup.email in data["entries"]:
            return {"status": "error", "message": "This email is already registered for beta access."}

        # Parse comma-separated tools from form - store as-is, no emoji bullshit
        tools = [t.strip() for t in signup.excited_tools.split(",") if t.strip()]

        new_entry = {
            "name": signup.full_name,
            "email": signup.email,
            "status": "pending",
            "os": "MacOS",
            "tools": tools,
            "gpt_user": signup.gpt_plus.lower() == "yes" if signup.gpt_plus else False,
            "claude_user": signup.claude_sub.lower() == "yes" if signup.claude_sub else False,
            "feedback_opt_in": True,
            "use_case": signup.use_case,
            "why_early_access": signup.why_early_access,
            "ai_experience": signup.ai_experience,
            "signup_timestamp": datetime.now().isoformat()
        }

        # Use email as key
        data["entries"][signup.email] = new_entry

        # Save
        with open(BETA_FILE, 'w') as f:
            json.dump(data, f, indent=4)

        logging.info(f"New beta signup: {signup.email}")
        return {"status": "success", "message": "Application received!"}

    except Exception as e:
        logging.error(f"Beta signup error: {e}")
        return {"status": "error", "message": str(e)}

@app.get("/beta/thanks", response_class=HTMLResponse)
async def beta_thanks_page():
    """Serve the thank you page"""
    html_path = os.path.join(BASE_DIR, "semantic_memory/html/beta-thanks.html")
    with open(html_path, 'r') as f:
        return HTMLResponse(content=f.read())


@app.post("/webhook/sendgrid")
async def sendgrid_webhook(request: Request):
    """Handle SendGrid webhook events for open/click tracking"""
    try:
        events = await request.json()
        
        stats_file = os.path.join(BASE_DIR, "data/email_stats.json")
        if os.path.exists(stats_file):
            with open(stats_file, "r") as f:
                stats = json.load(f)
        else:
            stats = {"broadcasts": [], "total_sent": 0}
        
        for event in events:
            event_type = event.get("event")
            broadcast_id = event.get("broadcast_id")
            
            if not broadcast_id:
                continue
            
            for broadcast in stats["broadcasts"]:
                if broadcast["broadcast_id"] == broadcast_id:
                    if event_type == "open":
                        broadcast["opens"] = broadcast.get("opens", 0) + 1
                    elif event_type == "click":
                        broadcast["clicks"] = broadcast.get("clicks", 0) + 1
                    break
        
        with open(stats_file, "w") as f:
            json.dump(stats, f, indent=2)
        
        return {"status": "success"}
        
    except Exception as e:
        logging.error(f"SendGrid webhook error: {e}")
        return {"status": "error", "message": str(e)}