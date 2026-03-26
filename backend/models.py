from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./experiment_results.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class ExperimentResult(Base):
    __tablename__ = "experiment_results"

    id = Column(Integer, primary_key=True, index=True)
    scenario = Column(String, index=True)
    baseline_latency = Column(Float)
    proposed_latency = Column(Float)
    latency_overhead = Column(Float)
    baseline_record_count = Column(Integer)
    proposed_source_count = Column(Integer)
    proposed_stored_rows = Column(Integer)
    proposed_detected_issues = Column(Integer)
    proposed_reconciliation = Column(Boolean)
    proposed_out_of_order_rate = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    false_positives = Column(Integer)
    false_negatives = Column(Integer)
    created_at = Column(DateTime, default=datetime.datetime.utcnow)

Base.metadata.create_all(bind=engine)