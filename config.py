import os
from dotenv import load_dotenv

load_dotenv()

port = os.getenv('port')
sandbox = True

if (public_domain := os.getenv("public_domain")) is not None:
    sandbox = False
    code_callback_URI = f"{public_domain}/authorization-code-callback"
    orcid_url = "https://orcid.org/"
    signatories_url = os.path.join(public_domain, os.getenv("site_path"))

else:
    sandbox = True
    code_callback_URI = f"http://127.0.0.1:{port}/authorization-code-callback"
    orcid_url = "https://sandbox.orcid.org/"
    signatories_url = os.getenv("site_path")

# Load ORCID and admin parameters from .env file
cookie_secret = os.getenv("cookie_secret")
client_ID = os.getenv("client_ID")
client_secret = os.getenv("client_secret")
admin_orcid = os.getenv("admin_orcid")
orcid_member = os.getenv("orcid_member")
if orcid_member == 1:
    orcid_member = True
else:
    orcid_member = False
if os.getenv("everyone_is_editor").lower() == "true":
    everyone_is_editor = True
else:
    everyone_is_editor = False


# Database
basedir = os.path.abspath(os.path.dirname(__file__))
campaigndir = os.path.join(basedir, "campaigns")
dbdir = os.path.join(basedir, "db")
dbname = "signatories.db"
dbpath = os.path.abspath(os.path.join(dbdir, dbname))
db_URI = "sqlite:////" + dbpath
if os.getenv("show_examples").lower() == "true":
    show_examples = True
else:
    show_examples = False


# Default parameters for the home page
favicon = os.getenv("favicon")
site_title = os.getenv("site_title")
site_subtitle = os.getenv("site_subtitle")
site_path = os.getenv("site_path")
site_header = os.getenv("site_header")
if os.getenv("show_examples").lower() == "true":
    show_examples = True
else:
    show_examples = False


# Default parameters for the footer
footer_url_name = os.getenv("footer_url_name")
footer_url = os.getenv("footer_url")
if os.getenv("thank_prc").lower() == "true":
    thank_prc = True
else:
    thank_prc = False
contact_email = os.getenv("contact_email")
