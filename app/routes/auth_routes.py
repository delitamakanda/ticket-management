import json

from flask import Blueprint, request, jsonify, render_template, url_for, send_file, current_app
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from ..models import db, User, PushNotification, Ticket
from .. import limiter
from ..mailer import send_email
from ..utils.qr_utils import generate_qrcode
from ..logger import log_auth_event
from ..utils.rate_limit_utils import rate_limit_per_role
from ..utils.ai_utils import generate_ticket_suggestion
from ..utils.utils import role_required
from ..utils.chatbot import generate_chatbot_response
from flask_cors import cross_origin
from pywebpush import webpush, WebPushException
from .. import socketio

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/subscribe', methods=['POST'])
@jwt_required()
@cross_origin()
def subscribe():
    """
    Subscribe to push notifications
    ---
    responses:
        200:
            description: Subscription successful
    """
    data = request.get_json()
    user_id = get_jwt_identity()["id"]
    
    if not data or not data.get('endpoint') or not data.get('keys'):
        return jsonify({'error': 'Missing endpoint or keys'}), 400
    
    push_notification = PushNotification.query.filter_by(endpoint=data['endpoint']).first()
    if not push_notification:
        push_notification = PushNotification(
            user_id=user_id,
            endpoint=data['endpoint'],
            p256h=data['keys']['p256dh'],
            auth=data['keys']['auth']
        )
        db.session.add(push_notification)
    else:
        push_notification.p256h = data['keys']['p256dh']
        push_notification.auth = data['keys']['auth']
    db.session.commit()
    
    return jsonify({'message': 'Subscription successful'}), 200


def send_notification(user_id, title, message):
    push_notification = PushNotification.query.filter_by(user_id=user_id).first()
    
    payload = {"title": title, "body": message}
    
    for push in push_notification:
        try:
            webpush(
                subscription_info={
                    "endpoint": push.endpoint,
                    "keys": {
                        "p256dh": push.p256h,
                        "auth": push.auth
                    }
                },
                data=json.dumps(payload),
                vapid_private_key=current_app.config['VAPID_PRIVATE_KEY'],
                vapid_claims={
                    "sub": current_app.config['VAPID_CLAIM_EMAIL']
                },
                ttl=10800  # 3 hours
            )
        except WebPushException as e:
            print(f"Failed to send notification to {push.endpoint}: {e}")


@socketio.on('ticket_updated')
def ticket_updated_event(ticket_data):
    ticket_id = ticket_data.get('ticket_id')
    ticket = Ticket.query.get(ticket_id)
    
    if ticket:
        send_notification(ticket.user_id, f'Ticket Updated: {ticket.title}',
                          f'Your ticket {ticket.title} has been updated to {ticket.status}.')


@auth_bp.route('/register', methods=['POST'])
@jwt_required()
@limiter.limit(rate_limit_per_role)
@role_required(['admin'])
def register():
    """
    Register a new user
    ---
    responses:
        201:
            description: User registered successfully

    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password') or not data.get(
            'role'):
        return jsonify({'error': 'Missing username, email, or password or role'}), 400
    if User.query.filter_by(username=data['username']).first() or User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Username or email already taken'}), 409
    
    if data['role'] not in ['consumer', 'engineer', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    
    # Generate QR code
    qrcode_uri = user.get_qrcode_uri()
    qrcode_img = generate_qrcode(qrcode_uri)
    
    send_file(qrcode_img, mimetype='image/png')
    
    # Send email confirmation
    subject = 'Registration Confirmation'
    body = render_template('email_confirmation.html', username=data['username'], role=data['role'])
    send_email(subject, data['email'], body)
    
    return jsonify({'message': 'User registered successfully'}), 201


@auth_bp.route('/login', methods=['POST'])
@limiter.limit(rate_limit_per_role)
def login():
    """
    Authenticate user and generate access and refresh tokens
    ---
    responses:
        200:
            description: Access and refresh tokens generated successfully

    """
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    if user and user.is_locked():
        log_auth_event(user, 'LOGIN_ATTEMPT_LOCKED')
        return jsonify({'error': 'Account is locked'}), 403
    
    if not user or not user.check_password(data['password']):
        if user:
            user.failed_attempts += 1
            if user.failed_attempts >= 3:
                user.lock()
                log_auth_event(user, 'ACCOUNT_LOCKED')
                subject = 'Account Locked'
                body = render_template('account_locked.html', username=user.username)
                send_email(subject, user.email, body)
                return jsonify({'error': 'Too many failed login attempts'}), 403
            db.session.commit()
            log_auth_event(user, 'LOGIN_FAILURE')
        else:
            log_auth_event(None, 'LOGIN_FAILURE_UNKNOWN_USER')
        return jsonify({'error': 'Invalid username or password'}), 401
    
    user.failed_attempts = 0
    db.session.commit()
    
    log_auth_event(user, 'LOGIN_SUCCESS')
    return jsonify({'message': 'Login successful'}), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    """
    Refresh access and refresh tokens
    ---
    responses:
        200:
            description: Access and refresh tokens generated successfully
    
    """
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id)
    return jsonify({'access_token': new_access_token}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    """
    Get user information
    ---
    responses:
        200:
            description: User information retrieved successfully
    """
    user_id = get_jwt_identity()
    return jsonify({'message': f'{user_id}'}), 200


@auth_bp.route('/password_reset_request', methods=['POST'])
@limiter.limit("10 per hour")
def password_reset_request():
    """
    Send password reset email to the provided email address
    ---
    responses:
        200:
            description: Password reset email sent successfully
    """
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({'error': 'Missing email'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    token = user.get_reset_token()
    reset_url = url_for('auth.reset_password', token=token, _external=True)
    
    # send email with reset link
    subject = 'Password Reset Request'
    body = render_template('password_reset_notification.html', username=user.username, reset_url=reset_url)
    send_email(subject, user.email, body)
    
    return jsonify({'message': 'Password reset email sent'}), 200


@auth_bp.route('/reset_password/<token>', methods=['POST'])
@limiter.limit("5 per minute")
def password_reset(token):
    """
    Verify and reset password using the provided token
    ---
    responses:
        200:
            description: Password reset successfully
    
    """
    user = User.verify_reset_token(token)
    if not user:
        return jsonify({'error': 'Invalid token'}), 401
    
    data = request.get_json()
    if not data or not data.get('password'):
        return jsonify({'error': 'Missing password'}), 400
    
    user.set_password(data['password'])
    db.session.commit()
    return jsonify({'message': 'Password reset successfully'}), 200


@auth_bp.route('/verify_otp', methods=['POST'])
@limiter.limit("5 per minute")
def verify_otp():
    """
    Verify OTP code and generate access and refresh tokens
    ---
    responses:
        200:
            description: Access and refresh tokens generated successfully
    """
    data = request.get_json()
    if not data or not data.get('otp_code'):
        return jsonify({'error': 'Missing OTP code'}), 400
    
    user_id = get_jwt_identity()
    user = User.query.get(user_id)
    if not user or not user.check_otp_code(data['otp_code']):
        return jsonify({'error': 'Invalid OTP code'}), 401
    
    access_token = create_access_token(identity={'id': user.id, 'role': user.role})
    refresh_token = create_refresh_token(identity={'id': user.id, 'role': user.role})
    return jsonify({'access_token': access_token, 'refresh_token': refresh_token}), 200


@auth_bp.route('/request_fallback_otp', methods=['POST'])
@limiter.limit("5 per minute")
def request_fallback_otp():
    """
    Send fallback OTP code to the provided email address
    ---
    responses:
        200:
            description: Fallback OTP code sent successfully
            
    """
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({'error': 'Missing email'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    otp_code = user.get_fallback_otp_code()
    subject = 'Two-Factor Authentication Code'
    body = render_template('otp_email.html', otp_code=otp_code, username=user.username)
    send_email(subject, user.email, body)
    
    return jsonify({'message': 'Fallback OTP code sent'}), 200


@auth_bp.route('/verify_fallback_otp', methods=['POST'])
@limiter.limit("5 per minute")
def verify_fallback_otp():
    """
    Verify fallback OTP code and generate access and refresh tokens
    ---
    responses:
        200:
            description: Access and refresh tokens generated successfully
    """
    data = request.get_json()
    if not data or not data.get('otp_code') or not data.get('email'):
        return jsonify({'error': 'Missing OTP code or email'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        return jsonify({'error': 'User not found'}), 404
    
    if user.fallback_otp_code != data['otp_code']:
        return jsonify({'error': 'Invalid fallback OTP code'}), 401
    
    user.fallback_otp_code = None
    db.session.commit()
    
    access_token = create_access_token(identity={'id': user.id, 'role': user.role})
    refresh_token = create_refresh_token(identity={'id': user.id, 'role': user.role})
    return jsonify({'access_token': access_token, 'refresh_token': refresh_token}), 200


@auth_bp.route('/request_unlock', methods=['POST'])
@limiter.limit("5 per minute")
def request_unlock():
    """
    Send unlock request email to the provided email address
    ---
    responses:
        200:
            description: Unlock request sent successfully
    
        403:
            description: Account is not locked
    
    """
    data = request.get_json()
    if not data or not data.get('email'):
        return jsonify({'error': 'Missing email'}), 400
    
    user = User.query.filter_by(email=data['email']).first()
    if not user:
        log_auth_event(user, 'UNLOCK_REQUEST_UNKNOWN_USER')
        return jsonify({'error': 'User not found'}), 404
    if not user.is_locked():
        return jsonify({'error': 'Account is not locked'}), 403
    unlock_url = url_for('auth.unlock_account', email=user.email, _external=True)
    subject = 'Account Unlock Request'
    body = render_template('unlock_account_notification.html', username=user.username, unlock_url=unlock_url)
    send_email(subject, user.email, body)
    log_auth_event(user, 'UNLOCK_REQUEST_SENT')
    return jsonify({'message': 'Unlock request sent'}), 200


@auth_bp.route('/unlock_account', methods=['POST'])
@limiter.limit(rate_limit_per_role)
def unlock_account():
    """
    Verify and unlock the account using the provided email address
    ---
    responses:
        200:
            description: Account unlocked successfully
        400:
            description: Invalid unlock code or email
    """
    email = request.args.get('email')
    if not email:
        return jsonify({'error': 'Missing email'}), 400
    
    user = User.query.filter_by(email=email).first()
    if not user:
        log_auth_event(user, 'UNLOCK_FAILURE_UNKNOWN_USER')
        return jsonify({'error': 'User not found'}), 404
    user.unlock()
    log_auth_event(user, 'ACCOUNT_UNLOCKED')
    return jsonify({'message': 'Account unlocked successfully'}), 200


@auth_bp.route('/ai_generate_ticket', methods=['POST'])
@jwt_required()
@limiter.limit(rate_limit_per_role)
def ai_generate_ticket():
    """
    Generate a ticket using AI-powered suggestion
    ---
    responses:
        200:
            description: Ticket suggestion generated successfully
    """
    data = request.get_json()
    if not data or not data.get('issue_summary'):
        return jsonify({'error': 'Missing issue summary'}), 400
    
    title, priority, status, description = generate_ticket_suggestion(data['issue_summary'])
    return jsonify({'title': title, 'priority': priority, 'status': status, 'description': description}), 200


@auth_bp.route('/chatbot', methods=['POST'])
@jwt_required()
@limiter.limit(rate_limit_per_role)
def chatbot():
    """
    Generate a response from a chatbot using the provided message
    ---
    responses:
        200:
            description: Chatbot response generated successfully
    """
    data = request.get_json()
    if not data or not data.get('message'):
        return jsonify({'error': 'Missing message'}), 400
    
    response = generate_chatbot_response(data['message'])
    return jsonify({'response': response}), 200
