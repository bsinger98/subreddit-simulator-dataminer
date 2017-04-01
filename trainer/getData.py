from DBMetaData import engine, subreddits, posts, comments
from sqlalchemy import select
import re

# Load Comment data from server
conn = engine.connect()
data = []
commentSelect = select([comments.c.body]).where(comments.c.score >= 50).limit(2000)
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
text = ' '.join(raw_text)

# Remove URLS
urlRegex = r'^(https?:\/\/)?([\da-z\.-]+)\.([a-z\.]{2,6})([\/\w \.-]*)*\/?$'
text = re.sub(r'\w+:\/{2}[\d\w-]+(\.[\d\w-]+)*(?:(?:\/[^\s/]*))*', '<url>', text, flags=re.MULTILINE)
text = text.replace('<eos> ', '<eos>\n')

dataFile = open('data/data.txt', 'w')
dataFile.write(text)
