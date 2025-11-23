from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    orcid = db.Column(db.String(length=19), primary_key=True)
    name = db.Column(db.String, nullable=False)
    affiliation = db.Column(db.String)
    anonymous = db.Column(db.Boolean)

    def __repr__(self):
        return "<User %s>" % self.orcid
