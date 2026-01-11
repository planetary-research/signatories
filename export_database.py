from db_models import Signatory, Admin, Campaign, Block
from app import app

campaigns_file = "campaigns.txt"
admins_file = "admins.txt"
signatories_file = "signatories.txt"
banned_file = "banned.txt"

with app.app_context():

    with open(signatories_file, "w") as f:
        f.write("ID, ORCID, Name, Affiliation, Campaign, Anonymous\n")
        for user in Signatory.query.all():
            f.write(f"{user.id}, {user.orcid}, {user.name}, {user.affiliation}, {user.campaign}, {user.anonymous}\n")

    with open(admins_file, "w") as f:
        f.write("ORCID, Name, Role\n")
        for user in Admin.query.all():
            f.write(f"{user.orcid}, {user.name}, {user.role_id}\n")

    with open(banned_file, "w") as f:
        f.write("ORCID, Name\n")
        for user in Block.query.all():
            f.write(f"{user.orcid}, {user.name}\n")

    with open(campaigns_file, "w") as f:
        f.write("Slug, ORCID Ownder, Kind, Name, Short Description, Text, Sort alphabetical, Allow anonymous, Is active, Creation date\n")
        for campaign in Campaign.query.all():
            f.write(
                f"{campaign.action_slug}, \
                {campaign.owner_orcid}, \
                {campaign.action_kind}, \
                {campaign.action_name}, \
                {campaign.action_short_description}, \
                {campaign.action_text}, \
                {campaign.sort_alphabetical}, \
                {campaign.allow_anonymous}, \
                {campaign.is_active}, \
                {campaign.creation_date}\n"
            )
