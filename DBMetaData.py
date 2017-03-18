from credentials import mysqlURL
from sqlalchemy import create_engine, DateTime, Table, Column, Integer, String, Text,  MetaData

engine = create_engine(mysqlURL, echo=True)
metadata = MetaData()

subreddits = Table('subreddits', metadata,
    Column('id', Integer, primary_key=True),
    Column('name', String(50)),
    Column('redditId', String(50), unique=True),
)
posts = Table('posts', metadata,
    Column('id', Integer, primary_key=True),
    Column('subreddit_id', String(50)),
    Column('redditId', String(50), unique=True),
    Column('title', String(1000)),
    Column('description', Text),
    Column('score', Integer),
    Column('created', DateTime),
)
comments = Table('comments', metadata,
    Column('id', Integer, primary_key=True),
    Column('post_id', String(50)),
    Column('redditId', String(50), unique=True),
    Column('body', Text),
    Column('score', Integer),
    Column('created', DateTime),
)
# Exclude so it doesnt recreate tables every run through
metadata.create_all(engine)
