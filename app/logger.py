from flask import request, render_template
from .models import AuthenticationLog, db, User
from .mailer import send_email
from datetime import datetime, timedelta

def log_auth_event(user, event):
    ip_address = request.remote_addr
    user_agent = request.headers.get('User-Agent')
    
    logger = AuthenticationLog(
        user_id=user.id if user else None,
        username=user.username if user else request.json.get('username'),
        event=event,
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.session.add(logger)
    db.session.commit()
    
    if event in ['LOGIN_FAILURE', 'ACCOUNT_LOCKED'] and is_suspicious_login(user, ip_address):
        notify_admin_if_suspicious_login(user, ip_address, user_agent)
    
    
def is_suspicious_login(user, current_ip):
    if not user:
        return False
    recent_logs = AuthenticationLog.query.filter(AuthenticationLog.user_id == user.id, AuthenticationLog.event == 'LOGIN_SUCCESS').order_by(AuthenticationLog.timestamp.desc()).limit(5).all()
    previous_ips = [log.ip_address for log in recent_logs]
    
    return current_ip in previous_ips

def notify_admin_if_suspicious_login(user, ip_address, user_agent):
    admin_users = User.query.filter_by(role='admin').all()
    admin_emails = [user.email for user in admin_users]
    
    subject = 'Suspicious Login Attempt'
    body = render_template('suspicious_login_notification.html', username=user.username, ip_address=ip_address, user_agent=user_agent)
    
    for email in admin_emails:
        send_email(subject, email, body)
        
def clean_old_logs(days=30):
    expiration_date = datetime.now() - timedelta(days=days)
    old_logs = AuthenticationLog.query.filter(AuthenticationLog.timestamp < expiration_date).all()
    db.session.commit()
    print(f'Deleted {len(old_logs)} old authentication logs')
