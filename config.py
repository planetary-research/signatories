import os
from dotenv import load_dotenv

load_dotenv()

port = os.getenv('port')
sandbox = True

if (public_domain := os.getenv("public_domain")) is not None:
    sandbox = False
    code_callback_URI = f"{public_domain}/authorization-code-callback"
    orcid_url = "https://orcid.org/"
    signatories_url = public_domain

else:
    sandbox = True
    code_callback_URI = f"http://127.0.0.1:{port}/authorization-code-callback"
    orcid_url = "https://sandbox.orcid.org/"
    signatories_url = '/'

# Load secrets from .env file
cookie_secret = os.getenv("cookie_secret")
client_ID = os.getenv("client_ID")
client_secret = os.getenv("client_secret")
admin_orcid = os.getenv("admin_orcid")
orcid_member = os.getenv("orcid_member")
if orcid_member == 1:
    orcid_member = True
else:
    orcid_member = False


# Database
basedir = os.path.abspath(os.path.dirname(__file__))
campaigndir = os.path.join(basedir, "campaigns")
dbdir = os.path.join(basedir, "db")
dbname = "signatories.db"
dbpath = os.path.abspath(os.path.join(dbdir, dbname))
db_URI = "sqlite:////" + dbpath


# Default parameters for the home page
action_name = "Signatories"
action_short_description = "Open source signing of statements and petitions"
action_kind = "Introduction"
action_path = "/"
favicon = os.getenv("favicon")

# Default parameters for the footer
footer_url_name = os.getenv("footer_url_name")
footer_url = os.getenv("footer_url")
thank_prc = os.getenv("thank_prc")
contact_email = os.getenv("contact_email")
