from flask import Blueprint, request, jsonify, render_template
from flask_jwt_extended import create_access_token, create_refresh_token, jwt_required, get_jwt_identity
from .models import db, User
from .utils import role_required
from . import limiter
from .mailer import send_email

auth_bp = Blueprint('auth', __name__)

@auth_bp.route('/register', methods=['POST'])
@jwt_required()
@limiter.limit("3 per minute")
@role_required(['admin'])
def register():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('email') or not data.get('password') or not data.get('role'):
        return jsonify({'error': 'Missing username, email, or password or role'}), 400
    if User.query.filter_by(username=data['username']).first() or User.query.filter_by(email=data['email']).first():
        return jsonify({'error': 'Username or email already taken'}), 409
    
    if data['role'] not in ['consumer', 'engineer', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    user = User(username=data['username'], email=data['email'])
    user.set_password(data['password'])
    db.session.add(user)
    db.session.commit()
    
    # Send email confirmation
    subject = 'Registration Confirmation'
    body = render_template('email_confirmation.html', username=data['username'], role=data['role'] )
    send_email(subject, data['email'], body)
    
    
    return jsonify({'message': 'User registered successfully'}), 201

@auth_bp.route('/login', methods=['POST'])
@limiter.limit("5 per minute")
def login():
    data = request.get_json()
    if not data or not data.get('username') or not data.get('password'):
        return jsonify({'error': 'Missing username or password'}), 400
    
    user = User.query.filter_by(username=data['username']).first()
    if not user or not user.check_password(data['password']):
        return jsonify({'error': 'Invalid username or password'}), 401
    
    access_token = create_access_token(identity={'id':user.id, 'role': user.role})
    refresh_token = create_refresh_token(identity={'id':user.id, 'role': user.role})
    return jsonify({'access_token': access_token, 'refresh_token': refresh_token}), 200


@auth_bp.route('/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh():
    current_user_id = get_jwt_identity()
    new_access_token = create_access_token(identity=current_user_id)
    return jsonify({'access_token': new_access_token}), 200


@auth_bp.route('/me', methods=['GET'])
@jwt_required()
def me():
    user_id = get_jwt_identity()
    return jsonify({'message': f'{user_id}'}), 200