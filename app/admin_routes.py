from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required, get_jwt_identity
from .models import db, User, AuthenticationLog
from .utils import role_required
from . import limiter
from .logger import clean_old_logs
from .rate_limit_utils import rate_limit_per_role

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@limiter.limit(rate_limit_per_role)
@role_required(['admin'])
def get_users():
    identity = get_jwt_identity()
    if identity.get('role')!= 'admin':
        return jsonify({'error': 'Not authorized to access this resource'}), 403
    users = User.query.all()
    return [user.serialize() for user in users], 200


@admin_bp.route('/users/<int:user_id>', methods=['PUT'])
@jwt_required()
@role_required(['admin'])
def update_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return {'message': 'User not found'}, 404
    
    data = request.get_json()
    new_role = data.get('role')
    if new_role not in ['consumer', 'engineer', 'admin']:
        return jsonify({'error': 'Invalid role'}), 400
    
    user.role = new_role
    
    db.session.commit()
    return user.serialize(), 200


@admin_bp.route('/users/<int:user_id>', methods=['DELETE'])
@jwt_required()
@role_required(['admin'])
def delete_user(user_id):
    user = User.query.get(user_id)
    if not user:
        return {'message': 'User not found'}, 404
    
    db.session.delete(user)
    db.session.commit()
    return {'message': 'User deleted successfully'}, 200


@admin_bp.route('/logs', methods=['GET'])
@jwt_required()
@role_required(['admin'])
def get_logs():
    logs = AuthenticationLog.query.order_by(AuthenticationLog.timestamp.desc()).all()
    return [log.serialize() for log in logs], 200


@admin_bp.route('/clean_logs', methods=['POST'])
@jwt_required()
@role_required(['admin'])
@limiter.limit(rate_limit_per_role)
def clean_logs():
    clean_old_logs(days=30)
    return {'message': 'Old logs cleaned successfully'}, 200


