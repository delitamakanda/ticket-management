from app import create_app, socketio
import threading

app = create_app()

if __name__ == '__main__':
    from app.tasks import run_scheduler
    
    # Start the scheduler in a background thread
    scheduler_thread = threading.Thread(target=run_scheduler, daemon=True)
    scheduler_thread.start()
    socketio.run(app, host='0.0.0.0', port=5000, debug=True)  # Run the Flask app and SocketIO server in the same
    
    app.run(debug=True)
