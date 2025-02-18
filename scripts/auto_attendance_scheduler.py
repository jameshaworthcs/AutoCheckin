import asyncio
from datetime import datetime, timedelta
from api.utils import debug_log
from scripts.attendance_scheduler import fetch_all_users_attendance

# Scheduler configuration
INITIAL_DELAY_SECONDS = 5
RUN_INITIAL_CYCLE = False


async def start_attendance_scheduler() -> None:
    """Run the attendance fetch scheduler continuously using asyncio.

    Fetches attendance data every hour, but the actual fetch operation
    only runs if 24 hours have passed since the last run.
    """
    debug_log("Attendance fetch scheduler is now running")
    await asyncio.sleep(INITIAL_DELAY_SECONDS)

    if RUN_INITIAL_CYCLE:
        debug_log("Running initial attendance fetch cycle")
        try:
            fetch_all_users_attendance()
        except Exception as e:
            debug_log(f"Error in initial attendance fetch cycle: {str(e)}")

    now = datetime.now()
    next_hour = (now + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
    initial_delay = (next_hour - now).total_seconds()

    debug_log(f"Next attendance fetch scheduled for: {next_hour.isoformat()}")
    await asyncio.sleep(initial_delay)

    while True:
        try:
            debug_log("Running attendance fetch cycle")
            fetch_all_users_attendance()
        except Exception as e:
            debug_log(f"Error in attendance fetch scheduler: {str(e)}")

        next_run = datetime.now() + timedelta(hours=1)
        debug_log(f"Next attendance fetch scheduled for: {next_run.isoformat()}")
        await asyncio.sleep(3600)


async def initialize_scheduler() -> None:
    """Initialize and start the attendance fetch scheduler."""
    debug_log("Initializing attendance fetch scheduler")
    await start_attendance_scheduler()


if __name__ == "__main__":
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        loop.run_until_complete(initialize_scheduler())
    except KeyboardInterrupt:
        debug_log("Attendance scheduler stopped by user")
    finally:
        loop.close()
