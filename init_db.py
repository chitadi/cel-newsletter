from sqlalchemy import create_engine
from src.models import Base

def main():
    engine = create_engine("sqlite:///newsletter.db")
    Base.metadata.create_all(engine)
    print("newsletter.db initialized with tables")

if __name__ == "__main__":
    main()
