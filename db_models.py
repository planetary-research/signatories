import datetime
from flask_sqlalchemy import SQLAlchemy

db = SQLAlchemy()


class User(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    orcid = db.Column(db.String(length=19), nullable=False)
    name = db.Column(db.String, nullable=False)
    campaign = db.Column(db.String, db.ForeignKey("campaign.action_slug"), nullable=False)
    affiliation = db.Column(db.String)
    anonymous = db.Column(db.Boolean, nullable=False, default=False)

    def __repr__(self):
        return "<User %s>" % self.orcid


class Admin(db.Model):
    orcid = db.Column(db.String(length=19), primary_key=True)
    name = db.Column(db.String, nullable=False)
    role = db.Column(db.Integer, nullable=False, default=1)

    def __repr__(self):
        return "<Admin %s>" % self.orcid


class Campaign(db.Model):
    action_slug = db.Column(db.String, nullable=False, primary_key=True)
    owner_orcid = db.Column(db.String(length=19), default='')
    action_kind = db.Column(db.String, nullable=False)
    action_name = db.Column(db.String, nullable=False)
    action_short_description = db.Column(db.String, default='')
    action_text = db.Column(db.String, nullable=False)
    sort_alphabetical = db.Column(db.Boolean, nullable=False, default=False)
    allow_anonymous = db.Column(db.Boolean, nullable=False, default=True)
    creation_date = db.Column(db.DateTime, nullable=False, default=datetime.datetime.now(datetime.UTC))

    def __repr__(self):
        return "<Campaign %s>" % self.action_slug
