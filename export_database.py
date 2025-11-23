from db_models import User
from app import app

file = "export.txt"

with app.app_context():

    with open(file, "w") as f:

        for signatory in User.query.all():
            if (signatory.anonymous):
                f.write(f"{signatory.name} (anonymous), {signatory.affiliation}\n")
                print(f"{signatory.name} (anonymous), {signatory.affiliation}")
            else:
                f.write(f"{signatory.name}, {signatory.affiliation}\n")
                print(f"{signatory.name}, {signatory.affiliation}")

    print(f"User count: {len(User.query.all())}")
    print(f"Database exported to file: {file}")
