import asyncio
import threading
from api.sonarr import fetch_sonarr_series

POLL_INTERVAL = 600

def polling_task():
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.run_until_complete(poll_loop())

async def poll_loop():
    while True:
        try:
            print("Polling Sonarr for new episodes...")
            shows = fetch_sonarr_series()
            # Placeholder: implement logic to process new episodes
        except Exception as e:
            print(f"Error polling Sonarr: {e}")
        await asyncio.sleep(POLL_INTERVAL)

def start_polling_loop():
    thread = threading.Thread(target=polling_task, daemon=True)
    thread.start()
