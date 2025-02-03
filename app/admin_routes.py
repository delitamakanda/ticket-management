from flask import Blueprint, request, jsonify
from flask_jwt_extended import jwt_required
from .models import db, User
from .utils import role_required
from . import limiter

admin_bp = Blueprint('admin', __name__)

@admin_bp.route('/users', methods=['GET'])
@jwt_required()
@limiter.limit("100 per hour")
@role_required(['admin'])
def get_users():
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


