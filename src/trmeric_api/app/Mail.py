from flask_mail import Mail

mail = None
def initMail(app):
  mail = Mail(app)