import threading

from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_restful import Api
from flask_mail import Mail
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from config import Config

mail = Mail()
limiter = Limiter(key_func=get_remote_address, default_limits=["100 per hour", "10 per minute"])
db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)
    
    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    limiter.init_app(app)
    mail.init_app(app)
    
    from .routes.auth_routes import auth_bp
    from .routes.admin_routes import admin_bp
    
    from .resources import TicketResource, TicketListResource
    api = Api(app)
    api.add_resource(TicketListResource, '/api/tickets')
    api.add_resource(TicketResource, '/api/tickets/<int:ticket_id>')
    
    app.register_blueprint(auth_bp, url_prefix='/api/auth')
    app.register_blueprint(admin_bp, url_prefix='/api/admin')

    return app
