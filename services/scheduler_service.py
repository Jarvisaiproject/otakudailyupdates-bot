from apscheduler.schedulers.background import BackgroundScheduler
from config import config
from database.memory import MemoryDB
from services.agent_controller import AutonomousAgentController

class SchedulerService:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.controller = AutonomousAgentController()
        self.is_running = False

    def setup_schedule(self):
        for time_key, slot_info in config.SLOTS.items():
            hour, minute = map(int, time_key.split(":"))
            self.scheduler.add_job(
                func=self._execute_slot,
                trigger="cron",
                hour=hour,
                minute=minute,
                args=[time_key],
                id=f"job_slot_{time_key.replace(':', '_')}",
                replace_existing=True
            )
            MemoryDB.log_event("INFO", "Scheduler", f"Registered daily scheduled slot '{slot_info['name']}' at {time_key}")

    def _execute_slot(self, time_key: str):
        MemoryDB.log_event("INFO", "Scheduler", f"Cron triggered for slot {time_key}")
        try:
            self.controller.run_slot_cycle(time_key)
        except Exception as e:
            MemoryDB.log_event("ERROR", "Scheduler", f"Error executing scheduled slot {time_key}: {str(e)}")

    def start(self):
        if not self.is_running:
            self.setup_schedule()
            self.scheduler.start()
            self.is_running = True
            MemoryDB.log_event("INFO", "Scheduler", "APScheduler started successfully for all 8 daily publishing slots.")

    def stop(self):
        if self.is_running:
            self.scheduler.shutdown()
            self.is_running = False
            MemoryDB.log_event("INFO", "Scheduler", "APScheduler stopped.")
