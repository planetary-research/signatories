import os
from dotenv import load_dotenv

load_dotenv()

port = 3000
sandbox = True

if (public_domain := os.getenv("public_domain")) is not None:
    sandbox = False
    code_callback_URI = f"{public_domain}/authorization-code-callback"
    orcid_url = "https://orcid.org/"
else:
    sandbox = True
    code_callback_URI = f"http://127.0.0.1:{port}/authorization-code-callback"
    orcid_url = "https://sandbox.orcid.org/"


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

basedir = os.path.abspath(os.path.dirname(__file__))
dbdir = os.path.join(basedir, "db")
dbname = os.getenv("database_name")
db_URI = "sqlite:////" + os.path.abspath(os.path.join(dbdir, dbname))
