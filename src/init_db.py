# init_db.py
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from src.models import Base, Subscriber
from datetime import datetime
import secrets

DB_URL = "sqlite:///newsletter.db"

HARDCODED_SUBS = [
"f20220012@pilani.bits-pilani.ac.in",
"f20240912@pilani.bits-pilani.ac.in",
"f20220264@pilani.bits-pilani.ac.in",
"f20230230@pilani.bits-pilani.ac.in",
"f20231173@pilani.bits-pilani.ac.in",
"f20240345@pilani.bits-pilani.ac.in",
"f20221265@pilani.bits-pilani.ac.in",
"f20240212@pilani.bits-pilani.ac.in",
"f20240972@pilani.bits-pilani.ac.in",
"f20240192@pilani.bits-pilani.ac.in",
"f20230352@pilani.bits-pilani.ac.in",
"f20221312@pilani.bits-pilani.ac.in",
"f20241228@pilani.bits-pilani.ac.in",
"f20230239@pilani.bits-pilani.ac.in",
"f20221723@pilani.bits-pilani.ac.in",
"f20230837@pilani.bits-pilani.ac.in",
"F20220832@pilani.bits-pilani.ac.in",
"f20230761@pilani.bits-pilani.ac.in",
"f20241281@pilani.bits-pilani.ac.in",
"f20230546@pilani.bits-pilani.ac.in",
"f20230705@pilani.bits-pilani.ac.in",
"f20221327@pilani.bits-pilani.ac.in",
"f20240952@pilani.bits-pilani.ac.in",
"f20240701@pilani.bits-pilani.ac.in",
"f20231085@pilani.bits-pilani.ac.in",
"f20230077@pilani.bits-pilani.ac.in",
"f20240043@pilani.bits-pilani.ac.in",
"f20240191@pilani.bits-pilani.ac.in",
"f20230151@pilani.bits-pilani.ac.in",
"f20220525@pilani.bits-pilani.ac.in",
"f20230906@pilani.bits-pilani.ac.in",
"f20220267@pilani.bits-pilani.ac.in",
"f20230724@pilani.bits-pilani.ac.in",
"f20240676@pilani.bits-pilani.ac.in",
"f20220504@pilani.bits-pilani.ac.in",
"f20221295@pilani.bits-pilani.ac.in",
"f20230220@pilani.bits-pilani.ac.in",
"f20241269@pilani.bits-pilani.ac.in",
"f20240125@pilani.bits-pilani.ac.in",
"varshasreekumar2003@gmail.com"
]

def seed_subscribers(session: Session):
    # Only seed if the table is empty
    if session.scalar(select(Subscriber.email).limit(1)):
        print("✅ subscribers already present; skipping hard-seed")
        return

    for email in HARDCODED_SUBS:
        session.add(
            Subscriber(
                email=email,
                active=True,
                subscribed_at=datetime.utcnow(),
                token=secrets.token_hex(16),
            )
        )
    session.commit()
    print(f"✅ seeded {len(HARDCODED_SUBS)} hard-coded subscribers")


def main():
    engine = create_engine(DB_URL)
    Base.metadata.create_all(engine)
    print("✅ newsletter.db schema ensured")

    with Session(engine) as session:
        seed_subscribers(session)

if __name__ == "__main__":
    main()
