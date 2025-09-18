from sqlalchemy import create_engine, Column, Text, DateTime, String, LargeBinary
from sqlalchemy.orm import declarative_base
from sqlalchemy import Integer
from sqlalchemy import Boolean, DateTime

Base = declarative_base()

class Article(Base):
    __tablename__ = "articles"
    id            = Column(String(64), primary_key=True)   # sha256
    source_name   = Column(Text)
    url           = Column(Text, unique=True)
    title         = Column(Text)
    published_at  = Column(DateTime)
    text          = Column(Text)
    fetched_at    = Column(DateTime)
    score        = Column(Integer)   # nullable
    summary      = Column(Text)      # nullable
    image_url   = Column(Text, nullable=True)
    vector       = Column(LargeBinary, nullable=True)


class Subscriber(Base):
    __tablename__ = "subscribers"
    email         = Column(String, primary_key=True)
    active        = Column(Boolean, default=True)
    subscribed_at = Column(DateTime)
    last_sent     = Column(DateTime)
    token         = Column(String(64))      # for 1-click unsubscribe link


class Video(Base):
    __tablename__ = "videos"
    video_id      = Column(String,   primary_key=True)    # YouTube ID
    channel_name  = Column(Text)
    url           = Column(Text)
    title         = Column(Text)
    description   = Column(Text)
    thumbnail_url = Column(Text)
    published_at  = Column(DateTime)
    score         = Column(Integer, nullable=True)
    summary       = Column(Text,    nullable=True)
    transcript    = Column(Text,    nullable=True)  # for scoring
    vector       = Column(LargeBinary, nullable=True)

class Tweet(Base):
    __tablename__ = "tweets"
    id           = Column(String(32), primary_key=True)  # tweet_id
    handle       = Column(String(64))
    url          = Column(Text, unique=True)
    text         = Column(Text)
    created_at   = Column(DateTime)
    like_count   = Column(Integer)
    retweet_count= Column(Integer)
    fetched_at   = Column(DateTime)
    score        = Column(Integer) 
    title        = Column(Text,    nullable=True)  # for newsletter titles
    image_url    = Column(Text,    nullable=True)  # for tweet screenshot

