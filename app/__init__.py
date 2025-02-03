from flask import Flask
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_jwt_extended import JWTManager
from flask_restful import Api
from config import Config

db = SQLAlchemy()
migrate = Migrate()
jwt = JWTManager()

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    db.init_app(app)
    migrate.init_app(app, db)
    jwt.init_app(app)
    
    from .resources import TicketResource, TicketListResource
    api = Api(app)
    api.add_resource(TicketListResource, '/api/tickets')
    api.add_resource(TicketResource, '/api/tickets/<int:ticket_id>')

    return app
