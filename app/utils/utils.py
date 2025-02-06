from flask_jwt_extended import get_jwt_identity
from flask import jsonify
from functools import wraps

def role_required(required_role):
    def decorator(f):
        @wraps(f)
        def wrapper(*args, **kwargs):
            identity = get_jwt_identity()
            if not identity or identity.get('role') not in required_role:
                return jsonify({'error': 'You do not have the required role to access this resource'}), 403
            return f(*args, **kwargs)
        return wrapper
    return decorator