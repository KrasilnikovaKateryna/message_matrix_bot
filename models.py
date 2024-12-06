from extensions import db

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(50), nullable=False)
    room_id = db.Column(db.String(50), nullable=False)
    status = db.Column(db.String(50), nullable=False)
    interval = db.Column(db.Integer, nullable=False)
    start = db.Column(db.String(8), nullable=True)
    end = db.Column(db.String(8), nullable=True)
    message = db.Column(db.String, nullable=False)
    always_on = db.Column(db.Boolean, default=False)


