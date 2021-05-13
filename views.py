from app import app, db

from sqlalchemy.orm import joinedload
from models import Ticket, Comment
from flask import request
from config import TICKET_STATUS_OPEN, TICKET_STATUS_CLOSED, TICKET_STATUS_ANSWERED, TICKET_STATUS_WAITING_FOR_ANSWER, \
    TICKET_STATUSES


@app.route('/tickets', methods=['GET'])
def ticket_all():
    tickets = Ticket.query.all()
    return tickets


@app.route('/ticket/<int:ticket_id>', methods=['GET'])
def ticket_get(ticket_id):
    ticket = Ticket.query.options(joinedload(Ticket.comments)).filter_by(id=ticket_id).one()
    return ticket


@app.route('/ticket', methods=['POST'])
def ticket_create():
    req_json = request.json
    new_ticket = Ticket(
        subject=req_json.get('subject'),
        text=req_json.get('text'),
        email=req_json.get('email'),
        status=TICKET_STATUS_OPEN
    )
    db.session.add(new_ticket)
    db.session.commit()
    return new_ticket


def ticket_status_is_valid(ticket, new_status):
    result = (ticket.status == TICKET_STATUS_OPEN and new_status in (TICKET_STATUS_ANSWERED, TICKET_STATUS_CLOSED)) or\
             (ticket.status == TICKET_STATUS_ANSWERED and new_status in (TICKET_STATUS_CLOSED,
                                                                         TICKET_STATUS_WAITING_FOR_ANSWER))
    return result


@app.route('/ticket/update_status/<int:ticket_id>', methods=['POST'])
def ticket_update_status(ticket_id):
    new_status = request.json.get('status')
    if new_status not in TICKET_STATUSES:
        raise BaseException(f"Bad status {new_status}. Allowed statuses are: {TICKET_STATUSES.join(',')}")

    ticket = Ticket.query.filter_by(id=ticket_id).one()
    if not ticket_status_is_valid(ticket, new_status):
        raise BaseException(f"Wrong status {new_status} after status {ticket.status}")

    db.session.query(Ticket).filter_by(id=ticket_id).update({Ticket.status: new_status})
    updated_ticket = db.session.query(Ticket).filter_by(id=ticket_id).one()
    return updated_ticket


@app.route('/ticket/delete/<int:ticket_id>', methods=['POST'])
def ticket_delete(ticket_id):
    db.session.query(Ticket).filter_by(id=ticket_id).delete()
    return "Success"
