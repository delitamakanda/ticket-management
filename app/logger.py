from flask import request
from .models import AuthenticationLog, db

def log_auth_event(user, event):
    logger = AuthenticationLog(
        user_id=user.id if user else None,
        username=user.username if user else request.json.get('username'),
        event=event,
        ip_address=request.remote_addr,
        user_agent=request.headers.get('User-Agent'),
    )
    db.session.add(logger)
    db.session.commit()