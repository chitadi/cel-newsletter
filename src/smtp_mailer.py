import os, smtplib, ssl, datetime, itertools
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from src.models import Subscriber

from dotenv import load_dotenv
load_dotenv()


FROM_ADDR = os.getenv("SMTP_USER")
HOST      = os.getenv("SMTP_HOST")
PORT      = int(os.getenv("SMTP_PORT", 587))
PASS      = os.getenv("SMTP_PASS")

def load_recipients():
    eng = create_engine("sqlite:///newsletter.db")
    with Session(eng) as ssn:
        emails = ssn.scalars(
            select(Subscriber.email)
            .where(Subscriber.active.is_(True))
        ).all()
    return emails

def chunk(it, n):
    it = iter(it)
    while (batch := list(itertools.islice(it, n))):
        yield batch

def send(html_path, txt_path):
    today = datetime.date.today()
    subj  = f"Chittem's Keep‑Up with Startups - {today.strftime('%B %d, %Y')}"

    html = open(html_path).read()
    txt  = open(txt_path).read()
    rcpts = load_recipients()  # list of emails

    context = ssl.create_default_context()
    with smtplib.SMTP(HOST, PORT) as server:
        server.connect(HOST, PORT)
        server.ehlo()
        server.starttls(context=context)
        server.ehlo()
        server.login(FROM_ADDR, PASS)

        for batch in chunk(rcpts, 50):
            msg = MIMEMultipart("alternative")
            msg["Subject"] = subj
            msg["From"]    = FROM_ADDR
            # msg["To"] = f"Undisclosed recipients <{FROM_ADDR}>"
            # msg["Bcc"]     = ", ".join(batch)

            msg.attach(MIMEText(txt,  "plain"))
            msg.attach(MIMEText(html, "html"))

            server.sendmail(FROM_ADDR, batch, msg.as_string())
            print(f"✅ sent to {len(batch)} recipients")

if __name__ == "__main__":
    base = f"newsletter_{datetime.date.today()}"
    send(f"{base}.html", f"{base}.txt")
