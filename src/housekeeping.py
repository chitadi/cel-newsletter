import sqlite3

DB = "newsletter.db"

def housekeeping():
    conn = sqlite3.connect(DB)
    cur = conn.cursor()

    cur.execute("DELETE FROM articles")
    cur.execute("DELETE FROM videos")
    conn.commit()

    cur.execute("VACUUM")  # shrink file on disk
    conn.close()
    print("🧹 All articles and videos deleted, DB compacted")

if __name__ == "__main__":
    housekeeping()

