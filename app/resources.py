from flask import render_template
from flask_restful import Resource, reqparse
from .models import db, Ticket, User
from flask_jwt_extended import jwt_required, get_jwt_identity
from .utils.utils import role_required
from . import limiter
from .mailer import send_email
from .utils.rate_limit_utils import rate_limit_per_role
from .utils.ai_utils import generate_ticket_suggestion
from . import socketio

ticket_parser = reqparse.RequestParser()
ticket_parser.add_argument('title', type=str, required=True, help='Title is required')
ticket_parser.add_argument('description', type=str, required=True, help='Description is required')
ticket_parser.add_argument('status', type=str, choices=['open', 'closed', 'in_progress'], default='open', help='Status must be open, closed, or in_progress')
ticket_parser.add_argument('priority', type=str, choices=['low', 'medium', 'high'], default='medium', help='Priority must be low, medium, or high')

class TicketListResource(Resource):
    @staticmethod
    @jwt_required()
    @limiter.limit(rate_limit_per_role)
    def get():
        """
        Get all tickets
        ---
        responses:
            200:
                description: List of all tickets
                schema:
                    type: array
                    
        """
        tickets = Ticket.query.all()
        return [tickets.serialize() for t in tickets], 200
    
    @staticmethod
    @jwt_required()
    @role_required(['consumer'])
    @limiter.limit(rate_limit_per_role)
    def post():
        """
        Create a new ticket
        ---
        parameters:
            - in: body
              name: ticket
              schema:
                type: object
                properties:
                  title:
                    type: string
                  description:
                    type: string
                  status:
                    type: string
                    default: open
                    enum: [open, closed, in_progress]
                  priority:
                    type: string
                    default: medium
                    enum: [low, medium, high]
                required: [title, description]
        responses:
            201:
                description: Created ticket
        """
        args = ticket_parser.parse_args()
        
        if not args['title'] or not args['description']:
            args['title'], args['description'] = generate_ticket_suggestion(args.get('title', '') + ' ' + args.get('description', ''))
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
        """
        Get a single ticket
        ---
        parameters:
            - in: path
              name: ticket_id
              type: integer
        responses:
            200:
                description: Single ticket
                schema:
                    type: object
                    
        """
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return {'message': 'Ticket not found'}, 404
        return ticket.serialize(), 200
    
    @staticmethod
    @jwt_required()
    @role_required(['engineer'])
    def put(ticket_id):
        """
        Update a ticket
        ---
        responses:
            200:
                description: Updated ticket
                schema:
                    type: object
        """
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
        # emit event to update ticket list
        socketio.emit('ticket_updated', ticket.serialize(), broadcoast=True)
        return ticket.serialize(), 200
    
    @staticmethod
    @jwt_required()
    @role_required(['engineer'])
    def delete(self, ticket_id):
        """
        Delete a ticket by ID
        ---
        parameters:
            - in: path
              name: ticket_id
              type: integer
        responses:
            200:
                description: Ticket deleted successfully
        """
        user_id = get_jwt_identity()
        ticket = Ticket.query.get(ticket_id)
        if not ticket:
            return {'message': 'Ticket not found'}, 404
        db.session.delete(ticket)
        db.session.commit()
        return {'message': 'Ticket deleted successfully'}, 200