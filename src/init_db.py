# init_db.py
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from src.models import Base, Subscriber
from datetime import datetime
import os, secrets

DB_URL = "sqlite:///newsletter.db"

def seed_subscribers(session: Session):
    """Insert demo subscribers only if table is empty and env var is set."""
    existing = session.scalar(select(Subscriber.email).limit(1))
    if existing:
        print("✅ subscribers table already populated; skipping seeding")
        return

    raw = os.getenv("SEED_SUBSCRIBERS", "")
    emails = [e.strip() for e in raw.split(",") if e.strip()]
    if not emails:
        print("⚠️  No SEED_SUBSCRIBERS env-var; leaving table empty")
        return

    for email in emails:
        session.add(
            Subscriber(
                email=email,
                active=True,
                subscribed_at=datetime.utcnow(),
                token=secrets.token_hex(16),
            )
        )
    session.commit()
    print(f"✅ seeded {len(emails)} subscribers")

def main():
    engine = create_engine(DB_URL)
    Base.metadata.create_all(engine)
    print("✅ newsletter.db schema ensured")

    with Session(engine) as session:
        seed_subscribers(session)

if __name__ == "__main__":
    main()
