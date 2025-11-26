from flask import Flask
from flask import request, session
from flask import redirect, render_template
from flask import send_from_directory
from markupsafe import escape
from waitress import serve
import orcid
import os
from datetime import timedelta
import tomllib

import config
from db_models import db, User
from db_sandbox import create_dummy_users


base_campaign = 'signatories.toml'


""" App configuration """
app = Flask(__name__)

app.config.from_file(os.path.join(config.campaigndir, base_campaign), load=tomllib.load, text=False)
dbpath = os.path.abspath(os.path.join(config.dbdir, app.config['DATABASE_NAME']))
db_URI = "sqlite:////" + dbpath
print(f"Database: {app.config['DATABASE_NAME']}")
print(db_URI)

app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["SQLALCHEMY_DATABASE_URI"] = db_URI
app.config["SECRET_KEY"] = config.cookie_secret
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(days=7)
app.config.from_object(__name__)

""" Database """
db.init_app(app)

if not os.path.exists(dbpath):
    print(f"Database doesn't exist. Creating new database: {db_URI}")
    if not os.path.isdir(config.dbdir):
        os.mkdir(config.dbdir)
    with app.app_context():
        db.create_all()
        db.session.commit()
        if config.sandbox:
            create_dummy_users()

""" ORCID API """
if config.orcid_member:
    api = orcid.MemberAPI(config.client_ID, config.client_secret, sandbox=config.sandbox)
else:
    api = orcid.PublicAPI(config.client_ID, config.client_secret, sandbox=config.sandbox)

if config.sandbox:
    api._token_url = "https://sandbox.orcid.org/oauth/token"
else:
    api._token_url = "https://orcid.org/oauth/token"

""" Default URLs """

action_slug = app.config["ACTION_SLUG"]

home_URI = os.path.join("/", action_slug)
logout_URI = os.path.join("/", action_slug, "logout")
user_URI = os.path.join("/", action_slug, "user")
thank_you_URI = os.path.join("/", action_slug, "thank-you")
privacy_URI = os.path.join("/", action_slug, "privacy")


base_data = {
    "home_uri": home_URI,
    "logout_uri": logout_URI,
    "user_uri": user_URI,
    "privacy_uri": privacy_URI,
    "thank_you_uri": thank_you_URI,
    "action_kind": app.config["ACTION_KIND"],
    "action_name": app.config["ACTION_NAME"],
    "action_short_description": app.config["ACTION_SHORT_DESCRIPTION"],
    "action_text": app.config["ACTION_TEXT"],
    "sort_alphabetical": app.config["SORT_ALPHABETICAL"],
    "footer_url_name": app.config["FOOTER_URL_NAME"],
    "footer_url": app.config["FOOTER_URL"],
    "thank_prc": app.config["THANK_PRC"],
    "contact_email": app.config["CONTACT_EMAIL"],
    "use_banner": app.config["USE_BANNER"],
    "banner_width": app.config["BANNER_WIDTH"],
    "banner_file": os.path.join("img", app.config["BANNER_FILE"]),
    "orcid_url": config.orcid_url,
}

base_alerts = {
    "success": None,
    "danger": None,
    "info": None,
    "warning": None,
}


def checksum(x):
    """ Routine to verify ORCID checksum """
    total = 0
    for s in x[:-1]:
        if s == "-":
            continue
        total = 2 * (total + int(s))

    remainder = total % 11
    result = (12 - remainder) % 11

    if (result == 10) and (x[-1] == "X"):
        return True
    elif result == int(x[-1]):
        return True
    else:
        return False


""" Routes """


@app.route('/favicon.ico')
def favicon():
    return send_from_directory(
        os.path.join(app.root_path, 'static/img'),
        app.config["FAVICON"], mimetype='image/vnd.microsoft.icon')


@app.route('/')
def base():
    if action_slug == "":
        return home()
    else:
        return redirect(home_URI)

@app.route(home_URI)
def home():
    # Get the ORCID authentication URI
    URI = api.get_login_url(scope="/authenticate", redirect_uri=config.code_callback_URI)

    # Create list of signatories and counts
    total_signatures = len(User.query.all())
    anonymous_signatures = len(User.query.filter_by(anonymous=True).all())
    if base_data["sort_alphabetical"]:
        visible_signatures = User.query.filter_by(anonymous=False).order_by(User.name.asc()).all()
    else:
        visible_signatures = User.query.filter_by(anonymous=False).all()

    data = {
        "authorization_uri": URI,
        "total_signatures": total_signatures,
        "anonymous_signatures": anonymous_signatures,
        "visible_signatures": visible_signatures,
    }
    data.update(base_data)
    return render_template("index.html", **data)


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
        return redirect(user_URI)

    return "Fetching ORCID account details..."


@app.route(privacy_URI)
def privacy():
    data = {}
    data.update(base_data)
    return render_template("privacy.html", **data)


@app.route(user_URI, methods=["POST", "GET"])
def user():
    # Check if the user is logged in
    if session.get("orcid") is None:
        return redirect(home_URI)

    user = User.query.filter_by(orcid=session["orcid"]).first()

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
                    orcid=session["orcid"], name=session["name"])
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
            return redirect(thank_you_URI)

        # Delete all user data
        if request.form.get("mode") == "delete":
            # Check the confirmation option
            if request.form["confirmation"].lower() == "yes":
                # Delete user account
                User.query.filter_by(orcid=session["orcid"]).delete()
                # Commit to database
                db.session.commit()
                # Logout
                return redirect(logout_URI)
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
        "name": session["name"],
        "affiliation": affiliation,
        "anonymous": anonymous,
        "orcid_id": session["orcid"],
        "alert": alerts,
        "in_database": in_database,
    }
    data.update(base_data)

    # Serve user page
    return render_template("user.html", **data)


@app.route(thank_you_URI)
def thank_you():
    # If a user session exists, close it
    if session.get("orcid") is not None:
        session.pop("name", None)
        session.pop("orcid", None)
    data = {}
    data.update(base_data)
    return render_template("thank-you.html", **data)


@app.route(logout_URI)
def logout():
    # If a user session exists, close it
    if session.get("orcid") is not None:
        session.pop("name", None)
        session.pop("orcid", None)
    return redirect(home_URI)


@app.errorhandler(404)
def page_not_found(e):
    # we should instead render a 404.html page
    return redirect(home_URI)


if __name__ == "__main__":
    if config.sandbox:
        app.run(host="127.0.0.1", port=config.port, debug=True)
    else:
        serve(app, host="127.0.0.1", port=config.port)
