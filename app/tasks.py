import schedule
import time

from run import app
from .logger import clean_old_logs

def schedule_clean_old_logs():
    with app.app_context():
        clean_old_logs()  # Clean old logs every 30 days

schedule.every().day.at("00:00").do(schedule_clean_old_logs, days=30)

def run_scheduler():
    while True:
        schedule.run_pending()
        time.sleep(1)
        