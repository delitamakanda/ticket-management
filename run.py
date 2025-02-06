from app import create_app
import threading

app = create_app()

if __name__ == '__main__':
    from app.tasks import run_scheduler
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    
    app.run(debug=True)
