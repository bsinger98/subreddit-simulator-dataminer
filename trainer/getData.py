from DBMetaData import engine, subreddits, posts, comments
from sqlalchemy import select

# Load Comment data from server
conn = engine.connect()
data = []
commentSelect = select([comments.c.body]).limit(5000)
rows = conn.execute(commentSelect)
for row in rows:
    data.append(row)

raw_text = []
for comment in data:
  words = comment[0].split()
  # Mark end of comment with <eos>
  words.append("<eos>")
  raw_text = raw_text + words

# TODO handle puncuation
raw_text = [x.lower() for x in raw_text]

dataFile = open('data/data.txt', 'w')
dataFile.write(' '.join(raw_text))
