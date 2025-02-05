from flask_mail import Message

from . import mail


def send_email(subject, recipient, body):
    msg = Message(subject, recipients=[recipient])
    msg.body = body
    try:
        mail.send(msg)
        return 'Email sent successfully'
    except Exception as e:
        return f'Error sending email: {str(e)}'