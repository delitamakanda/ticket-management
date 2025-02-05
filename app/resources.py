from flask import render_template
from flask_restful import Resource, reqparse
from .models import db, Ticket, User
from flask_jwt_extended import jwt_required, get_jwt_identity
from .utils import role_required
from . import limiter
from .mailer import send_email
from .rate_limit_utils import rate_limit_per_role

ticket_parser = reqparse.RequestParser()
ticket_parser.add_argument('title', type=str, required=True, help='Title is required')
ticket_parser.add_argument('description', type=str, required=True, help='Description is required')
ticket_parser.add_argument('status', type=str, choices=['open', 'closed', 'in_progress'], default='open', help='Status must be open, closed, or in_progress')
ticket_parser.add_argument('priority', type=str, choices=['low', 'medium', 'high'], default='medium', help='Priority must be low, medium, or high')

class TicketListResource(Resource):
    @staticmethod
    @limiter.limit(rate_limit_per_role)
    def get():
        tickets = Ticket.query.all()
        return [tickets.serialize() for t in tickets], 200
    
    @staticmethod
    @jwt_required()
    @role_required(['consumer'])
    @limiter.limit(rate_limit_per_role())
    def post():
        args = ticket_parser.parse_args()
        identity = get_jwt_identity()
        user = User.query.get(identity['id'])
        ticket = Ticket(title=args['title'], description=args['description'], status=args['status'], priority=args['priority'])
        db.session.add(ticket)
        db.session.commit()
        
        # Send email notification
        subject = f'New Ticket: {args["title"]}'
        body = render_template('new_ticket_notification.html', ticket=ticket, username=user['username'])
        send_email(subject, user.email, body)
        return ticket.serialize(), 201
    
class TicketResource(Resource):
    @staticmethod
    def get(ticket_id):
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return {'message': 'Ticket not found'}, 404
        return ticket.serialize(), 200
    
    @staticmethod
    @jwt_required()
    @role_required(['engineer'])
    def put(ticket_id):
        user_id = get_jwt_identity()
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return {'message': 'Ticket not found'}, 404
        
        args = ticket_parser.parse_args()
        ticket.title = args['title']
        ticket.description = args['description']
        ticket.status = args.get('status', ticket.status)
        ticket.priority = args.get('priority', ticket.priority)
        
        user = User.query.get(user_id)
        
        if user:
            subject = f'Ticket Update: {ticket.title}'
            body = render_template('ticket_update_notification.html', ticket=ticket, username=user['username'])
            send_email(subject, user.email, body)
        
        db.session.commit()
        return ticket.serialize(), 200
    
    @staticmethod
    @jwt_required()
    @role_required(['engineer'])
    def delete(self, ticket_id):
        user_id = get_jwt_identity()
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return {'message': 'Ticket not found'}, 404
        db.session.delete(ticket)
        db.session.commit()
        return {'message': 'Ticket deleted successfully'}, 200