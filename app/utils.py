from flask_jwt_extended import get_jwt_identity
from flask import jsonify

def role_required(required_role):
    def decorator(f):
        def wrapper(*args, **kwargs):
            user_id = get_jwt_identity()
            if not user_id or user_id['role']!= required_role:
                return jsonify({'error': 'You do not have the required role to access this resource'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator