"""R6/R7: durable local demo records, portable to PostgreSQL via DATABASE_URL."""
import json
import os
from pathlib import Path
from sqlalchemy import create_engine, Column, String, Text
from sqlalchemy.orm import declarative_base, sessionmaker

ROOT = Path(__file__).resolve().parents[3]
STATE_DIR = ROOT / '.state'
STATE_DIR.mkdir(exist_ok=True)
URL = os.getenv('DATABASE_URL', f'sqlite:///{STATE_DIR / "operations.db"}')
engine = create_engine(URL, connect_args={'check_same_thread': False} if URL.startswith('sqlite') else {}, pool_pre_ping=True)
Session = sessionmaker(engine)
Base = declarative_base()


class Record(Base):
    __tablename__ = 'demo_records'
    key = Column(String(200), primary_key=True)
    category = Column(String(60), index=True, nullable=False)
    payload = Column(Text, nullable=False)


def initialize():
    Base.metadata.create_all(engine)


def save(category: str, key: str, value: dict):
    with Session.begin() as session:
        session.merge(Record(key=f'{category}:{key}', category=category, payload=json.dumps(value, allow_nan=False)))
    return value


def get(category: str, key: str):
    with Session() as session:
        row = session.get(Record, f'{category}:{key}')
        return json.loads(row.payload) if row else None


def listing(category: str):
    with Session() as session:
        return [json.loads(row.payload) for row in session.query(Record).filter_by(category=category).all()]

