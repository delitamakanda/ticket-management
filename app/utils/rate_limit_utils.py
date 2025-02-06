from flask_jwt_extended import get_jwt_identity

def rate_limit_per_role():
    identity = get_jwt_identity()
    if not identity:
        return "5 per minute"
    
    role = identity.get('role')
    if role == 'consumer':
        return "10 per minute"
    elif role == 'engineer':
        return "20 per minute"
    elif role == 'admin':
        return "100 per hour"
    return "5 per minute"