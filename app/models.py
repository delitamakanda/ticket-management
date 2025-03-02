import random
import string

import pyotp
from . import db
from datetime import datetime, timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from flask import current_app
from itsdangerous import URLSafeTimedSerializer

class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, index=True)
    email = db.Column(db.String(120), unique=True, index=True)
    password_hash = db.Column(db.String(128))
    role = db.Column(db.String(20), default='consumer') # consumer, engineer, admin
    otp_secret = db.Column(db.String(16), default=pyotp.random_base32())
    fallback_otp_secret = db.Column(db.String(6), nullable=True)
    failed_attempts = db.Column(db.Integer, default=0)
    locked_until = db.Column(db.DateTime, nullable=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
    
    def get_reset_token(self, expires_sec=3600):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        return serializer.dumps(self.email, salt=current_app.config['SECRET_KEY'])
    
    def get_otp_code(self):
        totp = pyotp.TOTP(self.otp_secret)
        return totp.now()
    
    def get_qrcode_uri(self):
        totp = pyotp.TOTP(self.otp_secret)
        return totp.provisioning_uri(self.username, issuer_name='Ticketing System')
    
    def generate_fallback_otp(self):
        self.fallback_otp_secret = ''.join(random.choices(string.digits, k=6))
        db.session.commit()
        return self.fallback_otp_secret
    
    def is_locked(self):
        return self.locked_until and self.locked_until > datetime.now()
    
    def lock(self, minutes=15):
        self.locked_until = datetime.now() + timedelta(minutes=minutes)
        self.failed_attempts = 0
        db.session.commit()
    
    def unlock(self):
        self.locked_until = None
        self.failed_attempts = 0
        db.session.commit()

    @staticmethod
    def verify_reset_token(token, expires_sec=3600):
        serializer = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
        email = serializer.loads(token, salt=current_app.config['SECRET_KEY'], max_age=expires_sec)
        return User.query.filter_by(email=email).first()
    
    def __repr__(self):
        return f'<User {self.username}>'
    
    def serialize(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'role': self.role,
        }


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(100), nullable=False)
    description = db.Column(db.Text, nullable=False)
    status = db.Column(db.String(20), default='open') # open, closed, in_progress
    priority = db.Column(db.String(20), default='medium') # low, medium, high
    created_at = db.Column(db.DateTime, default=db.func.current_timestamp())
    
    def __repr__(self):
        return f'<Ticket {self.id}: {self.title}>'
    
    def serialize(self):
        return {
            'id': self.id,
            'title': self.title,
            'description': self.description,
            'status': self.status,
            'priority': self.priority,
            'created_at': self.created_at.isoformat()
        }
    
class AuthenticationLog(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=True)
    username = db.Column(db.String(64), nullable=True)
    event = db.Column(db.String(20), nullable=False)
    ip_address = db.Column(db.String(45), nullable=True)
    user_agent = db.Column(db.String(255), nullable=True)
    timestamp = db.Column(db.DateTime, default=datetime.now())
    user = db.relationship('User', backref=db.backref('authentication_logs', lazy=True))
    
    def __repr__(self):
        return f'<AuthenticationLog {self.id}: {self.event} by {self.username}>'
    
    def serialize(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username': self.username,
            'event': self.event,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'timestamp': self.timestamp.isoformat()
        }
    
    
class PushNotification(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'), nullable=False)
    endpoint = db.Column(db.String(255), nullable=False)
    p256dh = db.Column(db.String(255), nullable=False)
    auth = db.Column(db.String(255), nullable=False)
    
    def __repr__(self):
        return f'<PushNotification {self.id}: {self.endpoint}>'
    
    def serialize(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'endpoint': self.endpoint,
            'p256dh': self.p256dh,
            'auth': self.auth
        }
    