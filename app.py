import os
from datetime import timedelta
import tomllib
from flask import Flask
from flask import request, session
from flask import redirect, render_template
from flask import send_from_directory
from markupsafe import escape
from waitress import serve
import orcid

import config
from db_models import db, User, Admin, Campaign
from utils import get_orcid_name


""" ORCID API """
if config.orcid_member:
    api = orcid.MemberAPI(config.client_ID, config.client_secret, sandbox=config.sandbox)
else:
    api = orcid.PublicAPI(config.client_ID, config.client_secret, sandbox=config.sandbox)

if config.sandbox:
    api._token_url = "https://sandbox.orcid.org/oauth/token"
else:
    api._token_url = "https://orcid.org/oauth/token"

""" App configuration """
app = Flask(__name__)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = config.db_URI
app.config["SECRET_KEY"] = config.cookie_secret
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config.from_object(__name__)

""" Database """
db.init_app(app)

# Create database if it doesn't exist and add admin
if not os.path.exists(config.dbpath):
    print(f"Database doesn't exist. Creating new database: {config.db_URI}")
    if not os.path.isdir(config.dbdir):
        os.mkdir(config.dbdir)
    with app.app_context():
        db.create_all()
        # get admin name from orcid
        name = get_orcid_name(api, config.admin_orcid)
        admin = Admin(orcid=config.admin_orcid, name=name, role=3)
        db.session.add(admin)
        db.session.commit()

""" Read files in Campaigns and add to database if they don't already exist """
files = os.listdir(config.campaigndir)

for file in files:
    with open(os.path.join(config.campaigndir, file), "rb") as f:
        data = tomllib.load(f)
        with app.app_context():
            result = Campaign.query.filter_by(action_slug=data["ACTION_SLUG"]).first()
            if not result:
                print(f"Creating new campaing for file: {file}")
                new_campaign = Campaign(
                    action_slug=data["ACTION_SLUG"],
                    action_kind=data["ACTION_KIND"],
                    action_name=data["ACTION_NAME"],
                    action_short_description=data["ACTION_SHORT_DESCRIPTION"],
                    action_text=data["ACTION_TEXT"],
                    sort_alphabetical=data["SORT_ALPHABETICAL"],
                    allow_anonymous=data["ALLOW_ANONYMOUS"],
                )
                db.session.add(new_campaign)
                db.session.commit()


""" Default URLs """

home_URI = "/"
logout_URI = "/logout"
user_URI = "/<slug>/user"
thank_you_URI = "/<slug>/thank-you"
signature_removed_URI = "/<slug>/signature-removed"
privacy_URI = "/privacy"
action_URI = "/<slug>"

base_data = {
    "home_uri": home_URI,
    "logout_uri": logout_URI,
    "user_uri": user_URI,
    "privacy_uri": privacy_URI,
    "thank_you_uri": thank_you_URI,
    "signature_removed_URI": signature_removed_URI,
    "action_kind": config.action_kind,
    "action_name": config.action_name,
    "action_path": config.action_path,
    "action_short_description": config.action_short_description,
    "signatories_url": config.signatories_url,
    "footer_url_name": config.footer_url_name,
    "footer_url": config.footer_url,
    "thank_prc": config.thank_prc,
    "contact_email": config.contact_email,
    "orcid_url": config.orcid_url,
}

base_alerts = {
    "success": None,
    "danger": None,
    "info": None,
    "warning": None,
}


""" Routes """


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static/img'),
        app.config["favicon"], mimetype='image/vnd.microsoft.icon')


@app.route(home_URI)
def home():
    campaign_list = dict()
    # Create list of signatory campaigns
    for row in Campaign.query.all():
        campaign_list[row.action_slug] = [row.action_name, row.action_short_description]
    data = {
        "campaigns": campaign_list,
    }
    base_data["user_URI_defined"] = None
    base_data["thank_you_URI_defined"] = None
    base_data["signature_removed_URI_defined"] = None

    return render_template("index.html", **(base_data | data))


@app.route(action_URI)
def action(slug):
    # Get the ORCID authentication URI
    URI = api.get_login_url(scope="/authenticate", redirect_uri=config.code_callback_URI)

    # check if the campaign exists
    result = Campaign.query.filter_by(action_slug=slug).first()
    if not result:
        return render_template("campaign-not-found.html", **(base_data))

    action_data = Campaign.query.filter_by(action_slug=slug).first()

    # Create list of signatories and counts
    total_signatures = len(User.query.filter_by(campaign=slug).all())
    anonymous_signatures = len(User.query.filter_by(anonymous=True, campaign=slug).all())
    if action_data.sort_alphabetical:
        visible_signatures = User.query.filter_by(anonymous=False, campaign=slug).order_by(User.name.asc()).all()
    else:
        visible_signatures = User.query.filter_by(anonymous=False, campaign=slug).all()

    data = {
        "action_kind": action_data.action_kind,
        "action_name": action_data.action_name,
        "action_short_description": action_data.action_short_description,
        "action_text": action_data.action_text,
        "action_path": "/" + action_data.action_slug,
        "authorization_uri": URI,
        "total_signatures": total_signatures,
        "anonymous_signatures": anonymous_signatures,
        "visible_signatures": visible_signatures,
    }
    base_data["user_URI_defined"] = "/" + slug + "/user"
    base_data["thank_you_URI_defined"] = "/" + slug + "/thank-you"
    base_data["signature_removed_URI_defined"] = "/" + slug + "/signature-removed"

    return render_template("action.html", **(base_data | data))


@app.route("/authorization-code-callback", methods=["GET"])
def authorize():
    # Instantiate the return code
    code = None

    # If a GET request is made
    if request.method == "GET":
        # Fetch (and sanitise) the return code
        code = escape(request.args["code"])

        # Exchange the security code for a token
        token = api.get_token_from_authorization_code(code, config.code_callback_URI)

        # Extract the ORCID and user name from the token, and set to session
        session["orcid"] = escape(token["orcid"])
        session["name"] = escape(token["name"])
        session.permanent = True

        # Serve the user page
        return redirect(base_data["user_URI_defined"])

    return "Fetching ORCID account details..."


@app.route(privacy_URI)
def privacy():
    data = {}
    data.update(base_data)
    return render_template("privacy.html", **data)


@app.route(user_URI, methods=["POST", "GET"])
def user(slug):
    # Check if the user is logged in
    if session.get("orcid") is None:
        return redirect(home_URI)

    user = User.query.filter_by(orcid=session["orcid"], campaign=slug).first()
    action_data = Campaign.query.filter_by(action_slug=slug).first()

    # Default alerts
    alerts = base_alerts.copy()

    # Execute when an update is pushed
    if request.method == "POST":
        # Update signature information
        if request.form.get("mode") == "update_info":
            affiliation = request.form["affiliation"]
            anonymous = request.form["anonymous"]

            # The user is not yet in the database
            if user is None:
                user = User(
                    orcid=session["orcid"], name=session["name"], campaign=slug)
                db.session.add(user)
                db.session.commit()

            # If the affiliation is empty, set to None in the database
            if affiliation == "":
                user.affiliation = None
            else:
                user.affiliation = affiliation
            if anonymous == "True":
                user.anonymous = True
            else:
                user.anonymous = False

            db.session.commit()

            return redirect(base_data["thank_you_URI_defined"])

        # Delete all user data
        if request.form.get("mode") == "delete":
            # Check the confirmation option
            if request.form["confirmation"].lower() == "yes":
                # Delete user account
                User.query.filter_by(orcid=session["orcid"], campaign=slug).delete()
                # Commit to database
                db.session.commit()
                # Logout
                return redirect(base_data["signature_removed_URI_defined"])
            else:
                alerts["info"] = "Please confirm your response with \"yes\""

    if user is not None:
        in_database = True
        affiliation = user.affiliation
        anonymous = user.anonymous
        if affiliation is None:
            affiliation = ''
        if user.name == '':
            alerts["danger"] = "Your ORCID user name is marked as private and will not be shown. " \
                "Please change the visibility of your name in your ORCID account."
    else:
        in_database = False
        affiliation = ''
        anonymous = None

    data = {
        "action_kind": action_data.action_kind,
        "action_name": action_data.action_name,
        "action_short_description": action_data.action_short_description,
        "action_text": action_data.action_text,
        "action_path": "/" + action_data.action_slug,
        "name": session["name"],
        "affiliation": affiliation,
        "anonymous": anonymous,
        "allow_anonymous": action_data.allow_anonymous,
        "orcid_id": session["orcid"],
        "alert": alerts,
        "in_database": in_database,
    }

    # Serve user page
    return render_template("user.html", **(base_data | data))


@app.route(thank_you_URI)
def thank_you(slug):
    action_data = Campaign.query.filter_by(action_slug=slug).first()

    # If a user session exists, close it
    if session.get("orcid") is not None:
        session.pop("name", None)
        session.pop("orcid", None)
    data = {
        "action_kind": action_data.action_kind,
        "action_name": action_data.action_name,
        "action_short_description": action_data.action_short_description,
        "action_path": "/" + action_data.action_slug,
    }
    base_data["user_URI_defined"] = None
    base_data["thank_you_URI_defined"] = None
    base_data["signature_removed_URI_defined"] = None

    return render_template("thank-you.html", **(base_data | data))


@app.route(signature_removed_URI)
def signature_removed(slug):
    action_data = Campaign.query.filter_by(action_slug=slug).first()

    # If a user session exists, close it
    if session.get("orcid") is not None:
        session.pop("name", None)
        session.pop("orcid", None)
    data = {
        "action_kind": action_data.action_kind,
        "action_name": action_data.action_name,
        "action_short_description": action_data.action_short_description,
        "action_path": "/" + action_data.action_slug,
    }
    base_data["user_URI_defined"] = None
    base_data["thank_you_URI_defined"] = None
    base_data["signature_removed_URI_defined"] = None

    return render_template("signature-removed.html", **(base_data | data))


@app.route(logout_URI)
def logout():
    # If a user session exists, close it
    if session.get("orcid") is not None:
        session.pop("name", None)
        session.pop("orcid", None)

    base_data["user_URI_defined"] = None
    base_data["thank_you_URI_defined"] = None
    base_data["signature_removed_URI_defined"] = None

    return redirect(home_URI)


@app.errorhandler(404)
def page_not_found(e):
    return render_template("404.html", **(base_data)), 404


if __name__ == "__main__":
    if config.sandbox:
        app.run(host="127.0.0.1", port=config.port, debug=True)
    else:
        serve(app, host="127.0.0.1", port=config.port)
