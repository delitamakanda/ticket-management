import schedule
import time
from .logger import clean_old_logs


def scheduled_tasks():
    schedule.every().day.at("00:00").do(clean_old_logs, days=30)
    
    while True:
        schedule.run_pending()
        time.sleep(60)
