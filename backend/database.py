from sqlalchemy import create_engine, Column, Integer, String, Float, Boolean, DateTime, JSON, Text
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
import datetime

SQLALCHEMY_DATABASE_URL = "sqlite:///./thesis_dashboard.db"

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args={"check_same_thread": False})
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, index=True)
    type = Column(String)  # ecommerce_events, sensor_events, custom
    uploaded_at = Column(DateTime, default=datetime.datetime.utcnow)
    row_count = Column(Integer)
    schema_json = Column(JSON)
    file_path = Column(String)

class ExperimentRun(Base):
    __tablename__ = "experiment_runs"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer)
    scenario_name = Column(String)  # clean, duplicated, dropped, corrupted, etc
    mode = Column(String)  # baseline, proposed, compare
    status = Column(String)  # pending, running, completed, failed
    started_at = Column(DateTime, default=datetime.datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    error_message = Column(Text, nullable=True)

class PipelineResult(Base):
    __tablename__ = "pipeline_results"

    id = Column(Integer, primary_key=True, index=True)
    experiment_run_id = Column(Integer)
    pipeline_type = Column(String)  # baseline, proposed
    detection_accuracy = Column(Float)
    precision = Column(Float)
    recall = Column(Float)
    false_positives = Column(Integer)
    false_negatives = Column(Integer)
    detected_loss = Column(Integer)
    detected_duplicates = Column(Integer)
    detected_corruption = Column(Integer)
    detected_inconsistency = Column(Integer)
    latency_ms = Column(Float)
    overhead_ms = Column(Float)
    summary_json = Column(JSON)

class StageCheckResult(Base):
    __tablename__ = "stage_check_results"

    id = Column(Integer, primary_key=True, index=True)
    experiment_run_id = Column(Integer)
    pipeline_type = Column(String)  # baseline, proposed
    stage_name = Column(String)
    check_name = Column(String)
    issue_type = Column(String)  # loss, duplication, corruption, inconsistency
    passed = Column(Boolean)
    findings_count = Column(Integer)
    notes = Column(Text, nullable=True)

Base.metadata.create_all(bind=engine)