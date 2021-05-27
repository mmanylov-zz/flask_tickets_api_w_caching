import os
import json

from datetime import datetime
from functools import wraps

from flask import Flask, request
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_caching import Cache
from sqlalchemy.orm import joinedload
from jsonschema import validate as validate_jsonschema, ValidationError
from pydantic import BaseModel, ValidationError as PydanticValidationError, validator

from config import TicketStatus


app = Flask(__name__)
env_config = os.getenv("APP_SETTINGS", "config.DevelopmentConfig")
app.config.from_object(env_config)
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
db = SQLAlchemy(app)
cache = Cache(app)
migrate = Migrate(app, db)


CACHE_KEY_ALL_TICKETS = 'all_tickets'
CACHE_KEY_TEMPLATE_TICKET = 'ticket_{ticket_id}'
CACHE_KEY_TEMPLATE_COMMENT = 'comments_for_ticket_{ticket_id}'


class Ticket(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    subject = db.Column(db.String(256), nullable=False)
    text = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(256), nullable=False)
    status = db.Column(db.String(16), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    updated_at = db.Column(db.DateTime)

    def __repr__(self):
        return '<Ticket id={} subject={}>'.format(self.id, self.subject)

    def to_dict(self):
        return {
            'id': self.id,
            'subject': self.subject,
            'text': self.text,
            'email': self.email,
            'status': self.status,
            'created_at': str(self.created_at) if self.created_at else None,
            'updated_at': str(self.updated_at) if self.updated_at else None,
        }


class Comment(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    text = db.Column(db.Text, nullable=False)
    email = db.Column(db.String(256), nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)

    ticket_id = db.Column(db.Integer, db.ForeignKey('ticket.id', onupdate='CASCADE', ondelete='CASCADE'), nullable=False)
    ticket = db.relationship('Ticket', backref=db.backref('comments', lazy=True))

    def __repr__(self):
        return '<Comment id={}>'.format(self.id)

    def to_dict(self):
        return {
            'id': self.id,
            'ticket_id': self.ticket_id,
            'text': self.text,
            'email': self.email,
            'created_at': str(self.created_at) if self.created_at else None,
        }


def validate_schema(schema):
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                validate_jsonschema(instance=request.json, schema=schema)
            except ValidationError as e:
                return {'error': str(e)}, 400
            return func(*args, **kwargs)
        return wrapper
    return decorator


class TicketPydantic(BaseModel):
    subject: str
    text: str
    email: str

    @validator('subject')
    def min_length(cls, v):
        if len(v) <= 8:
            raise ValueError('value must be longer than 8 symbols')
        return v


@app.route('/tickets', methods=['GET'])
def ticket_all():
    tickets = cache.get(CACHE_KEY_ALL_TICKETS)
    if tickets is None:
        tickets = Ticket.query.all()
        cache.set(CACHE_KEY_ALL_TICKETS, tickets)
    return json.dumps([t.to_dict() for t in tickets])


@app.route('/ticket/<int:ticket_id>', methods=['GET'])
def ticket_get(ticket_id):
    ticket = cache.get(CACHE_KEY_TEMPLATE_TICKET.format(ticket_id=ticket_id))
    if ticket is None:
        ticket = Ticket.query.options(joinedload(Ticket.comments, innerjoin=True)).filter_by(id=ticket_id).one()
        cache.set(CACHE_KEY_TEMPLATE_TICKET.format(ticket_id=ticket_id), ticket)
    return ticket.to_dict()


@app.route('/ticket/<int:ticket_id>/comments', methods=['GET'])
def ticket_comments_get(ticket_id):
    comments = cache.get(CACHE_KEY_TEMPLATE_COMMENT.format(ticket_id=ticket_id))
    if comments is None:
        comments = Comment.query.options().filter_by(ticket_id=ticket_id).all()
        cache.set(CACHE_KEY_TEMPLATE_COMMENT.format(ticket_id=ticket_id), comments)
    return json.dumps([c.to_dict() for c in comments])


@app.route('/ticket', methods=['POST'])
@validate_schema(schema={
    'type': 'object',
    'properties': {
        'subject': {'type': 'string'},
        'text': {'type': 'string'},
        'email': {'type': 'string'}
    }
})
def ticket_create():
    req_json = request.json

    try:
        TicketPydantic(**req_json)
    except PydanticValidationError as e:
        return e.json(), 400

    new_ticket = Ticket(
        subject=req_json.get('subject'),
        text=req_json.get('text'),
        email=req_json.get('email'),
        status=TicketStatus.OPEN.value
    )
    db.session.add(new_ticket)
    db.session.commit()
    cache.delete(CACHE_KEY_ALL_TICKETS)
    return new_ticket.to_dict()


def ticket_status_is_valid(ticket, new_status):
    if ticket.status == TicketStatus.CLOSED:
        return False

    result = (ticket.status == TicketStatus.OPEN and new_status in (TicketStatus.ANSWERED, TicketStatus.CLOSED)) or\
             (ticket.status == TicketStatus.ANSWERED and new_status in
              (TicketStatus.CLOSED, TicketStatus.WAITING_FOR_ANSWER))
    return result


@app.route('/ticket/update_status/<int:ticket_id>', methods=['POST'])
def ticket_update_status(ticket_id):
    new_status = request.json.get('status')
    if new_status not in [item.value for item in TicketStatus]:
        return f"Bad status {new_status}. Allowed statuses are: {', '.join([item.value for item in TicketStatus])}", 400

    ticket = Ticket.query.filter_by(id=ticket_id).one()
    if not ticket_status_is_valid(ticket, new_status):
        return f"Wrong status {new_status} after status {ticket.status}", 400

    db.session.query(Ticket).filter_by(id=ticket_id).update({Ticket.status: new_status, Ticket.updated_at: datetime.utcnow()})
    db.session.commit()
    updated_ticket = db.session.query(Ticket).filter_by(id=ticket_id).one()
    cache.delete(CACHE_KEY_TEMPLATE_TICKET.format(ticket_id=ticket_id))
    cache.delete(CACHE_KEY_ALL_TICKETS)
    return updated_ticket.to_dict()


@app.route('/ticket/delete/<int:ticket_id>', methods=['POST'])
def ticket_delete(ticket_id):
    db.session.query(Ticket).filter_by(id=ticket_id).delete()
    db.session.commit()
    cache.delete(CACHE_KEY_TEMPLATE_TICKET.format(ticket_id=ticket_id))
    cache.delete(CACHE_KEY_ALL_TICKETS)
    return "Success"


@app.route('/ticket/<int:ticket_id>/comment', methods=['POST'])
def ticket_comment_create(ticket_id):
    req_json = request.json
    new_comment = Comment(
        ticket_id=ticket_id,
        text=req_json.get('text'),
        email=req_json.get('email')
    )
    db.session.add(new_comment)
    db.session.commit()
    cache.delete(CACHE_KEY_TEMPLATE_COMMENT.format(ticket_id=ticket_id))
    return new_comment.to_dict()


@app.route('/ticket/<int:ticket_id>/comment/<int:comment_id>/delete', methods=['POST'])
def ticket_comment_delete(ticket_id, comment_id):
    db.session.query(Comment).filter_by(id=comment_id, ticket_id=ticket_id).delete()
    db.session.commit()
    cache.delete(CACHE_KEY_TEMPLATE_COMMENT.format(ticket_id=ticket_id))
    return "Success"


if __name__ == '__main__':
    with app.app_context():
        cache.clear()
    app.run(host="0.0.0.0")
