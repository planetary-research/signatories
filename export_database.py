from db_models import User, Admin, Campaign
from app import app

campaigns_file = "campaigns.txt"
admins_file = "admins.txt"
signatories_file = "signatories.txt"

with app.app_context():

    with open(signatories_file, "w") as f:
        f.write("ID, ORCID, Name, Affiliation, Campaign, Anonymous\n")
        for user in User.query.all():
            f.write(f"{user.id}, {user.orcid}, {user.name}, {user.affiliation}, {user.campaign}, {user.anonymous}\n")

    with open(admins_file, "w") as f:
        f.write("ORCID, Name, Role\n")
        for user in Admin.query.all():
            f.write(f"{user.orcid}, {user.name}, {user.role_id}\n")

    with open(campaigns_file, "w") as f:
        f.write("Slug, ORCID Ownder, Kind, Name, Short Description, Text, Sort alphabetical, Allow anonymous, Creation date\n")
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
                {campaign.creation_date}\n"
            )
