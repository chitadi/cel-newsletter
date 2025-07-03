# import datetime, pytz, sqlite3

# UTC = pytz.utc
# DB  = "newsletter.db"

# def housekeeping():
#     conn = sqlite3.connect(DB)
#     cur  = conn.cursor()

#     now = datetime.datetime.now(tz=UTC)
#     cur.execute("""
#         DELETE FROM articles
#         WHERE published_at < ?
#     """, (now - datetime.timedelta(days=1),))

#     cur.execute("""
#         UPDATE articles SET html=NULL
#         WHERE html IS NOT NULL
#           AND published_at < ?
#     """, (now - datetime.timedelta(days=1),))

#     conn.commit()
#     cur.execute("VACUUM")           # shrink file on disk
#     conn.close()
#     print("🧹 DB housekeeping done")

# if __name__ == "__main__":
#     housekeeping()

import sqlite3

DB = "newsletter.db"

def housekeeping():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("DELETE FROM articles")
    conn.commit()

    cur.execute("VACUUM")  # shrink file on disk
    conn.close()
    print("🧹 All articles deleted, DB compacted")

if __name__ == "__main__":
    housekeeping()

