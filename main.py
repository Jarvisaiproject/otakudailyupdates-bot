import sys
import os
import argparse
import uvicorn

# Reconfigure stdout/stderr for Windows UTF-8 compatibility
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')

from contextlib import asynccontextmanager
from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel

from config import config
from database.memory import MemoryDB
from services.agent_controller import AutonomousAgentController
from services.scheduler_service import SchedulerService

# Global instances
controller = AutonomousAgentController()
scheduler_service = SchedulerService()

def _keep_alive_pinger():
    """
    Background thread that periodically pings the server URL every 8 minutes
    to prevent Render.com Free Web Services from going to sleep.
    """
    import time
    import requests
    server_url = os.getenv("RENDER_EXTERNAL_URL", "https://otakudailyupdates-bot.onrender.com")
    time.sleep(30) # Initial delay
    while True:
        try:
            res = requests.get(f"{server_url}/api/logs", timeout=10)
            MemoryDB.log_event("INFO", "KeepAlive", f"Self keep-alive ping status: HTTP {res.status_code}")
        except Exception as e:
            pass
        time.sleep(480) # Ping every 8 minutes (Render sleeps after 15m)

@asynccontextmanager
async def lifespan(app: FastAPI):
    import threading
    scheduler_service.start()
    pinger_thread = threading.Thread(target=_keep_alive_pinger, daemon=True)
    pinger_thread.start()
    MemoryDB.log_event("INFO", "Main", "Keep-Alive Pinger Thread started (8-min interval).")
    yield
    scheduler_service.stop()

app = FastAPI(title="OtakuDailyUpdates Autonomous Blogging Agent", lifespan=lifespan)


# Set up templates
templates = Jinja2Templates(directory=os.path.join(os.path.dirname(__file__), "templates"))

class SlotTriggerRequest(BaseModel):
    slot_key: str

@app.get("/", response_class=HTMLResponse)
def dashboard(request: Request):
    posts = MemoryDB.get_recent_posts(limit=50)
    logs = MemoryDB.get_recent_logs(limit=100)
    social_posts = MemoryDB.get_recent_social_posts(limit=50)
    return templates.TemplateResponse(
        request,
        "index.html",
        context={
            "posts": posts,
            "logs": logs,
            "social_posts": social_posts,
            "dry_run": config.DRY_RUN
        }
    )

@app.get("/api/logs")
def get_logs():
    return MemoryDB.get_recent_logs(limit=50)

@app.get("/api/posts")
def get_posts():
    return MemoryDB.get_recent_posts(limit=50)

@app.get("/api/social")
def get_social_posts():
    return MemoryDB.get_recent_social_posts(limit=50)

@app.get("/api/wp-history")
def get_wp_history():
    """
    Fetches all live published posts directly from WordPress REST API.
    """
    import requests
    import html
    try:
        res = requests.get(f"{config.WP_URL}/wp-json/wp/v2/posts?per_page=100", timeout=12)
        if res.status_code == 200:
            raw_posts = res.json()
            wp_posts = []
            for p in raw_posts:
                wp_posts.append({
                    "id": p.get("id"),
                    "title": html.unescape(p.get("title", {}).get("rendered", "")),
                    "link": p.get("link"),
                    "date": p.get("date", "").replace("T", " "),
                    "slug": p.get("slug"),
                    "status": p.get("status")
                })
            return {"status": "success", "count": len(wp_posts), "posts": wp_posts}
    except Exception as e:
        return {"status": "error", "message": str(e), "posts": []}
    return {"status": "error", "posts": []}

@app.post("/api/run-slot")
def trigger_slot_api(req: SlotTriggerRequest):
    try:
        result = controller.run_slot_cycle(req.slot_key)
        return JSONResponse(content=result if isinstance(result, dict) else {"status": "success", "data": str(result)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})

@app.post("/api/run-cleaner")
def trigger_cleaner_api():
    try:
        from services.wp_cleaner_agent import WPDuplicateCleanerAgent
        cleaner = WPDuplicateCleanerAgent()
        res = cleaner.scan_and_clean_duplicates()
        return JSONResponse(content=res if isinstance(res, dict) else {"status": "success", "data": str(res)})
    except Exception as e:
        return JSONResponse(status_code=500, content={"status": "error", "message": str(e)})



def main():
    parser = argparse.ArgumentParser(description="OtakuDailyUpdates Autonomous AI Blogging Agent")
    parser.add_argument("--run-slot", type=str, help="Run a specific slot by time key (e.g. 08:00, 18:00, 20:00)")
    parser.add_argument("--run-all-slots", action="store_true", help="Run a full cycle of all 8 daily slots")
    parser.add_argument("--schedule", action="store_true", help="Start background scheduler service")
    parser.add_argument("--serve", action="store_true", help="Start FastAPI web dashboard server")
    parser.add_argument("--port", type=int, default=int(os.getenv("PORT", 8000)), help="Web server port (default 8000)")
    parser.add_argument("--dry-run", action="store_true", help="Enforce dry run mode")

    args = parser.parse_args()

    if args.dry_run:
        config.DRY_RUN = True

    if args.run_slot:
        print(f"[*] Triggering single slot cycle: {args.run_slot}")
        res = controller.run_slot_cycle(args.run_slot)
        print(f"[+] Result: {res}")
    elif args.run_all_slots:
        print("[*] Running full 8-slot daily cycle...")
        for time_key in config.SLOTS.keys():
            print(f"\n---> Executing Slot: {time_key}")
            res = controller.run_slot_cycle(time_key)
            print(f"[+] Slot {time_key} Result: {res}")
    elif args.serve:
        print(f"[*] Starting Web Dashboard on http://localhost:{args.port}")
        uvicorn.run(app, host="0.0.0.0", port=args.port)
    elif args.schedule:
        print("[*] Starting Scheduler service. Press Ctrl+C to exit.")
        scheduler_service.start()
        try:
            import time
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            scheduler_service.stop()
    else:
        print("[*] Running default dry-run test slot (08:00 AM Anime News #1)...")
        res = controller.run_slot_cycle("08:00")
        print(f"[+] Slot Output: {res}")

if __name__ == "__main__":
    main()
