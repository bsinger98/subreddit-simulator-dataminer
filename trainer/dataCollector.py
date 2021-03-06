# -*- coding: utf-8 -*-
import praw
from datetime import datetime
from credentials import mysqlURL
from sqlalchemy import create_engine, DateTime, Table, Column, Integer, String, Text,  MetaData, ForeignKey, select
from DBMetaData import engine, subreddits, posts, comments

def doesNotExistInDB(redditInfo, table, conn):
    s = select([table]).where(table.c.redditId == redditInfo.id)
    rows = conn.execute(s);
    count = 0;
    for row in rows:
        count += 1;

    if (count == 0):
        return True;

    return False;

user_agent = "web:subredditSimulatorLTSM:v.1"
r = praw.Reddit(user_agent=user_agent)

conn = engine.connect()

while True:
    subreddit = r.get_subreddit('the_donald')
    if(doesNotExistInDB(subreddit, subreddits, conn)):
        subredditIns = subreddits.insert().values(name=subreddit.display_name, redditId=subreddit.id)
        subredditIns.compile().params
        conn.execute(subredditIns);

# For each submission log the submission to DB
    for submission in subreddit.get_hot(limit=20):
        if(doesNotExistInDB(submission, posts, conn)):
            postDate = datetime.fromtimestamp(submission.created_utc)
            postIns = posts.insert().values(subreddit_id=subreddit.id, redditId=submission.id, title=submission.title, description=submission.selftext, score=submission.score, created=postDate)
            postIns.compile().params
            conn.execute(postIns)

        # Now log comments to DB
        submission_comments = praw.helpers.flatten_tree(submission.comments)
        for comment in submission_comments:
            if(hasattr(comment,'body') and doesNotExistInDB(comment,comments, conn)):
                # Sometimes comments dont have a created date for some reason
                # If it doesnt have a created date I just use current date because it is close enough
                if hasattr(comment, 'created_utc'):
                    commentDate = datetime.fromtimestamp(comment.created_utc)
                else:
                    commentDate = datetime.now()
                commentIns = comments.insert().values(post_id=subreddit.id, redditId=comment.id, body=comment.body, score=comment.score, created=commentDate)
                commentIns.compile().params
                conn.execute(commentIns)
    # Sleep for 3 hours
    time.sleep(10800)

