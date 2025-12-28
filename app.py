import os
import re
import datetime
from datetime import timedelta
from io import BytesIO
import tomllib
from flask import Flask
from flask import request, session
from flask import redirect, render_template
from flask import send_from_directory, send_file
from markupsafe import escape
from waitress import serve
import orcid
from pyexcel_ods3 import save_data

import config
from db_models import db, Signatory, Admin, Campaign, UserRole
from utils import get_orcid_name, checksum


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
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=2)
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
        admin = Admin(orcid=config.admin_orcid, name=name, role_id=3)
        db.session.add(admin)
        db.session.commit()

        for role_name in ("User", "Editor", "Administrator"):
            role = UserRole(name=role_name)
            db.session.add(role)

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

home_URI = config.site_path
logout_URI = os.path.join(config.site_path, "logout")
user_URI = os.path.join(config.site_path, "<slug>", "user")
thank_you_URI = os.path.join(config.site_path, "<slug>", "thank-you")
signature_removed_URI = os.path.join(config.site_path, "<slug>", "signature-removed")
privacy_URI = os.path.join(config.site_path, "privacy")
faq_URI = os.path.join(config.site_path, "faq")
action_URI = os.path.join(config.site_path, "<slug>")
admin_URI = os.path.join(config.site_path, "admin")
insufficient_privileges_URI = os.path.join(config.site_path, "insufficient-privileges")
create_URI = os.path.join(config.site_path, "create")
editor_URI = os.path.join(config.site_path, "editor")
edit_URI = os.path.join(config.site_path, "<slug>", "edit")

action_template = "action-with-sidebar.html"  # default template for actions

base_data = {
    "home_uri": home_URI,
    "logout_uri": logout_URI,
    "user_uri": user_URI,
    "privacy_uri": privacy_URI,
    "faq_uri": faq_URI,
    "thank_you_uri": thank_you_URI,
    "signature_removed_URI": signature_removed_URI,
    "admin_uri": admin_URI,
    "create_uri": create_URI,
    "editor_uri": editor_URI,
    "user_URI_defined": None,
    "thank_you_URI_defined": None,
    "signature_removed_URI_defined": None,
    "signatories_url": config.signatories_url,
    "footer_url_name": config.footer_url_name,
    "footer_url": config.footer_url,
    "show_examples": config.show_examples,
    "thank_prc": config.thank_prc,
    "contact_email": config.contact_email,
    "orcid_url": config.orcid_url,
    "authorization_uri_admin": api.get_login_url(
        scope="/authenticate",
        redirect_uri=config.code_callback_URI + "-admin"),
    "redirect_alerts": None,
    "role_id": 0,
    "everyone_is_editor": config.everyone_is_editor,
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
        config.favicon, mimetype='image/vnd.microsoft.icon')


@app.route(home_URI)
def home():
    # Home page
    if session.get("orcid") is None:
        role_id = 0
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    campaign_list = dict()
    # Create list of signatory campaigns
    for row in Campaign.query.filter_by(is_active=True).all():
        campaign_list[row.action_slug] = [
            row.action_name, row.action_short_description,
            os.path.join(config.site_path, row.action_slug)]
    data = {
        "header_title": config.site_title,
        "header_subtitle": config.site_subtitle,
        "header_path": config.site_path,
        "text_header": config.site_header,
        "campaigns": campaign_list,
        "page": "home",
        "role_id": role_id,
    }
    base_data["user_URI_defined"] = None
    base_data["thank_you_URI_defined"] = None
    base_data["signature_removed_URI_defined"] = None

    return render_template("index.html", **(base_data | data))


@app.route(action_URI, methods=["POST", "GET"])
def action(slug):
    # Show the campaign
    if session.get("orcid") is None:
        role_id = 0
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    # Get the ORCID authentication URI
    URI = api.get_login_url(scope="/authenticate", redirect_uri=config.code_callback_URI)

    # check if the campaign exists
    result = Campaign.query.filter_by(action_slug=slug).first()
    if not result:
        data = {
            "header_title": config.site_title,
            "header_subtitle": config.site_subtitle,
            "header_path": config.site_path,
        }
        return render_template("campaign-not-found.html", **(base_data | data))

    action_data = Campaign.query.filter_by(action_slug=slug).first()

    # Create list of signatories and counts
    total_signatures = len(Signatory.query.filter_by(campaign=slug).all())
    anonymous_signatures = len(Signatory.query.filter_by(anonymous=True, campaign=slug).all())
    if action_data.sort_alphabetical:
        visible_signatures = Signatory.query.filter_by(anonymous=False, campaign=slug).order_by(Signatory.name.asc()).all()
    else:
        visible_signatures = Signatory.query.filter_by(anonymous=False, campaign=slug).all()

    if request.method == "POST":
        if request.form.get("mode") == "download-ods":
            visible_signatures_list = []
            for row in visible_signatures:
                if row.affiliation is None:
                    affiliation = ''
                else:
                    affiliation = row.affiliation
    
                visible_signatures_list.append([row.name, affiliation, row.orcid, 'https://orcid.org/'+row.orcid])
            ods_output = {slug: visible_signatures_list}
            ods_bytes = BytesIO()
            save_data(ods_bytes, ods_output)
            ods_bytes.seek(0)  # Reset the pointer to the beginning of the file
            return send_file(ods_bytes, as_attachment=True, download_name=slug+".ods")

    data = {
        "header_title": action_data.action_name,
        "header_subtitle": action_data.action_kind.upper(),
        "header_path": os.path.join(config.site_path, slug),
        "action_kind": action_data.action_kind,
        "text_header": action_data.action_short_description,
        "action_text": action_data.action_text,
        "action_created": action_data.creation_date,
        "action_closed": action_data.closed_date,
        "authorization_uri": URI,
        "total_signatures": total_signatures,
        "anonymous_signatures": anonymous_signatures,
        "visible_signatures": visible_signatures,
        "is_active": action_data.is_active,
        "role_id": role_id,
        "download_uri": os.path.join(config.site_path, slug),
    }
    base_data["user_URI_defined"] = os.path.join(config.site_path, slug, "user")
    base_data["thank_you_URI_defined"] = os.path.join(config.site_path, slug, "thank-you")
    base_data["signature_removed_URI_defined"] = os.path.join(config.site_path, slug, "signature-removed")

    return render_template(action_template, **(base_data | data))


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


@app.route("/authorization-code-callback-admin", methods=["GET"])
def authorize_admin():
    # Instantiate the return code
    code = None

    # If a GET request is made
    if request.method == "GET":
        # Fetch (and sanitise) the return code
        code = escape(request.args["code"])

        # Exchange the security code for a token
        token = api.get_token_from_authorization_code(code, config.code_callback_URI+"-admin")

        # Extract the ORCID and user name from the token, and set to session
        session["orcid"] = escape(token["orcid"])
        session["name"] = escape(token["name"])
        session.permanent = True

        return redirect(editor_URI)

    return "Fetching ORCID account details..."


@app.route(privacy_URI)
def privacy():
    # Show the privacy page
    if session.get("orcid") is None:
        role_id = 0
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    data = {
        "header_title": config.site_title,
        "header_subtitle": config.site_subtitle,
        "header_path": config.site_path,
        "role_id": role_id,
    }
    return render_template("privacy.html", **(base_data | data))


@app.route(faq_URI)
def faq():
    # Show the faq page
    if session.get("orcid") is None:
        role_id = 0
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    data = {
        "header_title": config.site_title,
        "header_subtitle": config.site_subtitle,
        "header_path": config.site_path,
        "role_id": role_id,
    }
    return render_template("faq.html", **(base_data | data))


@app.route(user_URI, methods=["POST", "GET"])
def user(slug):
    # Show the page allowing a logged in user to sign a campaign
    if session.get("orcid") is None:
        return redirect(home_URI)
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    user = Signatory.query.filter_by(orcid=session["orcid"], campaign=slug).first()
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
                user = Signatory(
                    orcid=session["orcid"], name=session["name"], campaign=slug)
                db.session.add(user)
                db.session.commit()

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
            if request.form["confirmation"].lower() == "delete":
                # Delete user account
                Signatory.query.filter_by(orcid=session["orcid"], campaign=slug).delete()
                # Commit to database
                db.session.commit()
                # Logout
                return redirect(base_data["signature_removed_URI_defined"])
            else:
                alerts["danger"] = "Please confirm your response with \"delete\""

    if user is not None:
        in_database = True
        affiliation = user.affiliation
        anonymous = user.anonymous
        if user.name == '':
            alerts["danger"] = "Your ORCID user name is marked as private and will not be shown. " \
                "Please change the visibility of your name in your ORCID account."
    else:
        in_database = False
        affiliation = ''
        anonymous = None

    data = {
        "header_path": os.path.join(config.site_path, slug),
        "header_title": action_data.action_name,
        "header_subtitle": action_data.action_short_description,
        "action_kind": action_data.action_kind,
        "action_text": action_data.action_text,
        "name": session["name"],
        "affiliation": affiliation,
        "anonymous": anonymous,
        "allow_anonymous": action_data.allow_anonymous,
        "orcid_id": session["orcid"],
        "alert": alerts,
        "in_database": in_database,
        "role_id": role_id,
    }

    return render_template("user.html", **(base_data | data))


@app.route(admin_URI, methods=["POST", "GET"])
def admin():
    # Show the admin page

    # Check if the user is logged in
    if session.get("orcid") is None:
        print("User session not set")
        return redirect("/")

    # Query database for user's ORCID
    user = Admin.query.filter_by(orcid=session["orcid"]).first()
    if user is None:
        print("User is not in the Admin database")
        return redirect(insufficient_privileges_URI)

    # Check if the user has sufficient permissions
    if user.role_id < 3:
        print("Insufficient permissions to view the Admin page")
        return redirect(insufficient_privileges_URI)

    role = UserRole.query.filter_by(role_id=user.role_id).first()
    modify_options = [[1, "Remove"], [2, "Editor"], [3, "Administrator"]]
    delete_options = [[1, "Delete"]]  # [2, "Ban"]
    alerts = base_alerts.copy()

    orphans = len(Campaign.query.filter_by(action_slug='').all())

    # If an update is pushed
    if request.method == "POST":

        # Add or modify a user
        if request.form.get("mode") == "modify_user":
            # Get the user's ORCID
            user_id = escape(request.form["user_id"])
            # Get the desired user role
            role_id = int(request.form["user_role"])

            # Check if we are not accidently changing self
            if user_id == session["orcid"]:
                alerts["danger"] = "You cannot modify yourself."
            # Check if the ORCID is valid (4 groups of 4 digits)
            elif (re.match(r"\d{4}-\d{4}-\d{4}-\d{3}[0-9|xX]", user_id.strip()) is None) or not checksum(user_id.strip()):
                alerts["danger"] = "Invalid ORCID."
            # All good
            else:
                # Try to get user from DB
                user = Admin.query.filter_by(orcid=user_id).first()
                if user is None and role_id > 1:
                    # Try to get public name and email from orcid profile
                    orcid_name = get_orcid_name(api, user_id)
                    if orcid_name == '':
                        alerts["warning"] = "The ORCID user name is marked as private and will not be shown."
                    # Add new user
                    user = Admin(orcid=user_id, name=orcid_name, role_id=role_id)
                    db.session.add(user)
                    alerts["success"] = "New user added to admin database."
                elif user is None and role_id == 1:
                    alerts["warning"] = "User does not exist and can not be deleted."
                elif role_id > 1:
                    # Modify role ID
                    if user.role_id == role_id:
                        alerts["info"] = "User role did not need to be modified."
                    else:
                        user.role_id = role_id
                        alerts["success"] = "User role modified."
                else:
                    db.session.delete(user)
                    alerts["success"] = "User deleted."

                db.session.commit()

        # Delete or ban user
        if request.form.get("mode") == "delete_ban_user":
            # Get the user's ORCID
            user_id = escape(request.form["user_id"])
            # Get the desired user role
            user_option = int(request.form["user_option"])

            # Check if we are not accidently changing self
            if user_id == session["orcid"]:
                alerts["danger"] = "You cannot delete your own signatures."
            # Check if the ORCID is valid (4 groups of 4 digits)
            elif (re.match(r"\d{4}-\d{4}-\d{4}-\d{3}[0-9|xX]", user_id.strip()) is None) or not checksum(user_id.strip()):
                alerts["danger"] = "Invalid ORCID."
            # All good
            else:
                # See if user is in the admin database
                user = Admin.query.filter_by(orcid=user_id).first()
                if user is not None:
                    alerts["danger"] = "Can not delete or ban users with administrator roles."
                else:
                    result = Signatory.query.filter_by(orcid=user_id).all()
                    num_deleted = len(result)
                    if num_deleted > 0:
                        Signatory.query.filter_by(orcid=user_id).delete()
                        db.session.commit()
                        if num_deleted == 1:
                            alerts["success"] = f"Deleted {num_deleted} signature associated with ORCID {user_id}."
                        else:
                            alerts["success"] = f"Deleted {num_deleted} signatures associated with ORCID {user_id}."

                    else:
                        alerts["info"] = f"No signatures to delete for ORCID {user_id}."

                    # if user_option == 2: ## Add user to ban list

        # Download database file
        if request.form.get("mode") == "backup_db":
            return send_file(config.dbpath, as_attachment=True)

        # Delete database orphans
        if request.form.get("mode") == "delete_orphans":
            Campaign.query.filter_by(action_slug='').delete()
            db.session.commit()
            alerts["success"] = "Deleted orphan campaigns"
            orphans = 0

    # Create a list of administrators and editors and count all users
    admins = Admin.query.filter_by(role_id=3).order_by(Admin.name.asc()).all()
    editors = Admin.query.filter_by(role_id=2).order_by(Admin.name.asc()).all()

    data = {
        "header_title": session["name"],
        "header_subtitle": session["orcid"],
        "header_path": editor_URI,
        "name": session["name"],
        "orcid_id": session["orcid"],
        "role": role.name.capitalize(),
        "role_id": role.role_id,
        "modify_options": modify_options,
        "delete_options": delete_options,
        "alert": alerts,
        "editors": editors,
        "admins": admins,
        "orphans": orphans,
        "page": 'admin'
    }

    # Serve the admin page
    return render_template("admin.html", **(base_data | data))


@app.route(create_URI, methods=["POST", "GET"])
def create():
    # Show the page to create a campaign

    # Check if the user is logged in
    if session.get("orcid") is None:
        print("User session not set")
        return redirect("/")

    if base_data["everyone_is_editor"] is False:
        # Query database for user's ORCID
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            print("User is not in the Admin database")
            return redirect(insufficient_privileges_URI)

        # Check if the user has sufficient permissions
        role_id = user.role_id
        if role_id < 2:
            print("Insufficient permissions to view this page")
            return redirect(insufficient_privileges_URI)
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2

    # Default alerts (= None)
    alerts = base_alerts.copy()

    new_campaign = Campaign(
        action_slug="",
        action_kind="",
        action_name="",
        action_short_description="",
        action_text="",
        sort_alphabetical=False,
        allow_anonymous=True,
        owner_orcid=None,
        is_active=True,
    )
    # If an update is pushed
    if request.method == "POST":
        if request.form.get("mode") == "create_campaign":
            if request.form["sort_alphabetical"] == "True":
                sort_alphabetical = True
            else:
                sort_alphabetical = False
            if request.form["allow_anonymous"] == "True":
                allow_anonymous = True
            else:
                allow_anonymous = False
            if request.form["activate_campaign"] == 'True':
                is_active = True
                closed_date = None
            else:
                is_active = False
                closed_date = datetime.datetime.now(datetime.UTC)

            action_slug = escape(request.form["action_slug"])
            new_campaign = Campaign(
                action_slug=action_slug,
                action_kind=escape(request.form["action_kind"]),
                action_name=escape(request.form["action_name"]),
                action_short_description=escape(request.form["action_short_description"]),
                action_text=request.form["action_text"],
                sort_alphabetical=sort_alphabetical,
                allow_anonymous=allow_anonymous,
                owner_orcid=session["orcid"],
                owner_name=session["name"],
                is_active=is_active,
                closed_date=closed_date,
            )

            if Campaign.query.filter_by(action_slug=action_slug).first() is not None:
                alerts["danger"] = "Action slug already exists. Please choose another."
            elif action_slug == '':
                alerts["danger"] = "Action slug cannot be an empty string."
            elif ' ' in action_slug:
                alerts["danger"] = "Action slug cannot contain spaces."
            else:
                db.session.add(new_campaign)
                db.session.commit()

                base_data["redirect_alerts"] = {
                    "success": "Campaign created.",
                    "danger": None,
                    "info": None,
                    "warning": None,
                }
                return redirect(editor_URI)

    data = {
        "header_title": session["name"],
        "header_subtitle": session["orcid"],
        "header_path": editor_URI,
        "name": session["name"],
        "orcid_id": session["orcid"],
        "role_id": role_id,
        "alert": alerts,
        "page": 'create',
        "form_slug": new_campaign.action_slug,
        "form_kind": new_campaign.action_kind,
        "form_name": new_campaign.action_name,
        "form_short_description": new_campaign.action_short_description,
        "form_text": new_campaign.action_text,
        "form_sort_alphabetical": new_campaign.sort_alphabetical,
        "form_allow_anonymous": new_campaign.allow_anonymous,
        "form_activate_campaign": new_campaign.is_active,
    }

    return render_template("create.html", **(base_data | data))


@app.route(editor_URI)
def editor():
    # Show the editor page with their list of campaigns

    # Check if the user is logged in
    if session.get("orcid") is None:
        print("User session not set")
        return redirect("/")

    if base_data["everyone_is_editor"] is False:
        # Query database for user's ORCID
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            print("User is not in the Admin database")
            return redirect(insufficient_privileges_URI)

        # Check if the user has sufficient permissions
        role_id = user.role_id
        if role_id < 2:
            print("Insufficient permissions to view this page")
            return redirect(insufficient_privileges_URI)
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2

    # Default alerts (= None)
    if base_data["redirect_alerts"] is None:
        alerts = base_alerts.copy()
    else:
        alerts = base_data["redirect_alerts"]
        base_data["redirect_alerts"] = None

    my_campaigns = dict()
    all_campaigns = dict()
    # Create list of signatory campaigns
    for row in Campaign.query.order_by(Campaign.action_name.asc()).all():
        if row.owner_orcid == session["orcid"]:
            my_campaigns[row.action_slug] = [
                row.action_name, row.action_short_description,
                os.path.join(config.site_path, row.action_slug),
                row.is_active
            ]

    if role_id == 3:
        for row in Campaign.query.order_by(Campaign.action_name.asc()).all():
            all_campaigns[row.action_slug] = [
                row.action_name, row.action_short_description,
                os.path.join(config.site_path, row.action_slug),
                row.is_active
            ]

    data = {
        "header_title": session["name"],
        "header_subtitle": session["orcid"],
        "header_path": editor_URI,
        "name": session["name"],
        "orcid_id": session["orcid"],
        "role_id": role_id,
        "alert": alerts,
        "page": 'editor',
        "my_campaigns": my_campaigns,
        "all_campaigns": all_campaigns,
    }

    return render_template("editor.html", **(base_data | data))


@app.route(edit_URI, methods=["POST", "GET"])
def edit(slug):
    # Show the page to edit a specific campaign

    # Check if the user is logged in
    if session.get("orcid") is None:
        print("User session not set")
        return redirect("/")

    if base_data["everyone_is_editor"] is False:
        # Query database for user's ORCID
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            print("User is not in the Admin database")
            return redirect(insufficient_privileges_URI)

        # Check if the user has sufficient permissions
        role_id = user.role_id
        if role_id < 2:
            print("Insufficient permissions to view this page")
            return redirect(insufficient_privileges_URI)
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2

    edit_campaign = Campaign.query.filter_by(action_slug=slug).first()
    if not edit_campaign:
        return render_template("campaign-not-found.html", **(base_data))

    # For editors, check if the user is the campaign owner
    if role_id == 2:
        if edit_campaign.owner_orcid != session["orcid"]:
            print("Insufficient permissions to edit this action")
            return redirect(insufficient_privileges_URI)

    # Default alerts (= None)
    alerts = base_alerts.copy()

    # If an update is pushed
    if request.method == "POST":
        if request.form.get("mode") == "edit_campaign":
            if request.form["sort_alphabetical"] == "True":
                sort_alphabetical = True
            else:
                sort_alphabetical = False
            if request.form["allow_anonymous"] == "True":
                allow_anonymous = True
            else:
                allow_anonymous = False

            edit_campaign.action_kind = escape(request.form["action_kind"])
            edit_campaign.action_name = escape(request.form["action_name"])
            edit_campaign.action_short_description = escape(request.form["action_short_description"])
            edit_campaign.action_text = request.form["action_text"]
            edit_campaign.sort_alphabetical = sort_alphabetical
            edit_campaign.allow_anonymous = allow_anonymous

            db.session.commit()

            base_data["redirect_alerts"] = {
                "success": "Campaign updated.",
                "danger": None,
                "info": None,
                "warning": None,
            }
            return redirect(editor_URI)

        if request.form.get("mode") == "close_activate":
            if request.form["is_active"] == "Active":
                is_active = True
                edit_campaign.closed_date = None
                alert_text = "Campaign activated."
            else:
                is_active = False
                edit_campaign.closed_date = datetime.datetime.now(datetime.UTC)
                alert_text = "Campaign deactivated."

            edit_campaign.is_active = is_active
            db.session.commit()

            base_data["redirect_alerts"] = {
                "success": alert_text,
                "danger": None,
                "info": None,
                "warning": None,
            }
            return redirect(editor_URI)

        if request.form.get("mode") == "reset_date":
            edit_campaign.creation_date = datetime.datetime.now(datetime.UTC)
            db.session.commit()

            base_data["redirect_alerts"] = {
                "success": "Campaign creation date updated.",
                "danger": None,
                "info": None,
                "warning": None,
            }
            return redirect(editor_URI)

        if request.form.get("mode") == "delete_campaign":
            if request.form["confirmation"].lower() == "delete":
                # delete campaign and all signatories
                Campaign.query.filter_by(action_slug=slug).delete()
                Signatory.query.filter_by(campaign=slug).delete()
                db.session.commit()
                base_data["redirect_alerts"] = {
                    "success": "Campaign deleted.",
                    "danger": None,
                    "info": None,
                    "warning": None,
                }
                return redirect(editor_URI)
            else:
                alerts["danger"] = "Please confirm your response with \"delete\"."
            db.session.commit()

    data = {
        "header_title": session["name"],
        "header_subtitle": session["orcid"],
        "header_path": editor_URI,
        "name": session["name"],
        "orcid_id": session["orcid"],
        "role_id": role_id,
        "owner_orcid": edit_campaign.owner_orcid,
        "owner_name": edit_campaign.owner_name,
        "creation_date": edit_campaign.creation_date,
        "alert": alerts,
        "page": 'editor',
        "form_kind": edit_campaign.action_kind,
        "form_name": edit_campaign.action_name,
        "form_short_description": edit_campaign.action_short_description,
        "form_text": edit_campaign.action_text,
        "form_sort_alphabetical": edit_campaign.sort_alphabetical,
        "form_allow_anonymous": edit_campaign.allow_anonymous,
        "is_active": edit_campaign.is_active,
    }

    return render_template("edit.html", **(base_data | data))


@app.route(thank_you_URI)
def thank_you(slug):
    # Show page thanking the user for signing the campaign
    if session.get("orcid") is None:
        return redirect(home_URI)
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    action_data = Campaign.query.filter_by(action_slug=slug).first()

    data = {
        "header_title": action_data.action_name,
        "header_subtitle": action_data.action_kind.upper(),
        "header_path": os.path.join(config.site_path, slug),
        "action_kind": action_data.action_kind,
        "role_id": role_id,
    }
    base_data["user_URI_defined"] = None
    base_data["thank_you_URI_defined"] = None
    base_data["signature_removed_URI_defined"] = None

    # If a user session exists, close it (if admin, do nothing)
    if role_id == 0:
        session.pop("name", None)
        session.pop("orcid", None)

    return render_template("thank-you.html", **(base_data | data))


@app.route(signature_removed_URI)
def signature_removed(slug):
    # Show page confirming that the user signature was removed
    if session.get("orcid") is None:
        return redirect(home_URI)
    elif base_data["everyone_is_editor"] is True:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is not None:
            role_id = user.role_id
        else:
            role_id = 2
    else:
        user = Admin.query.filter_by(orcid=session["orcid"]).first()
        if user is None:
            role_id = 0
        else:
            role_id = user.role_id

    action_data = Campaign.query.filter_by(action_slug=slug).first()

    data = {
        "header_title": action_data.action_name,
        "header_subtitle": action_data.action_kind.upper(),
        "header_path": os.path.join(config.site_path, slug),
        "action_kind": action_data.action_kind,
        "role_id": role_id,
    }
    base_data["user_URI_defined"] = None
    base_data["thank_you_URI_defined"] = None
    base_data["signature_removed_URI_defined"] = None

    # If a user session exists, close it (if admin, do nothing)
    if role_id == 0:
        session.pop("name", None)
        session.pop("orcid", None)

    return render_template("signature-removed.html", **(base_data | data))


@app.route(insufficient_privileges_URI)
def insufficient_privileges():
    data = {
        "header_title": config.site_title,
        "header_subtitle": config.site_subtitle,
        "header_path": config.site_path,
    }
    return render_template("insufficient-privileges.html", **(base_data | data))


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
    data = {
        "header_title": config.site_title,
        "header_subtitle": config.site_subtitle,
        "header_path": config.site_path,
    }
    return render_template("404.html", **(base_data | data)), 404


if __name__ == "__main__":
    if config.sandbox:
        app.run(host="127.0.0.1", port=config.port, debug=True)
    else:
        serve(app, host="127.0.0.1", port=config.port)
