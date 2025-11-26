from db_models import db, User


def create_dummy_users():
    """ Create dummy users when in sandbox """
    bob = User(orcid="0000-0002-1234-5678", name="Bob", anonymous=True)
    db.session.add(bob)

    alice = User(orcid="0000-0002-1234-5000", name="Alice", anonymous=False)
    db.session.add(alice)

    frank = User(orcid="0000-0002-1234-9000", name="Frank", anonymous=False)
    db.session.add(frank)

    charlie = User(orcid="0000-0002-1234-5001", name="Charlie", anonymous=False)
    db.session.add(charlie)

    db.session.commit()
    print("Dummy users created.")
