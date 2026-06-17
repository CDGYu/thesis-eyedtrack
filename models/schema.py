from sqlalchemy import create_engine, Column, Integer, String, Float, DateTime, Boolean, JSON, ForeignKey
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class MonitoringSession(Base):
    __tablename__ = 'monitoring_sessions'

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), unique=True, nullable=False)
    start_time = Column(DateTime, nullable=False, default=datetime.utcnow)
    end_time = Column(DateTime)
    status = Column(String(20), nullable=False, default='active')
    device_info = Column(JSON)
    
    behaviors = relationship("DriverBehavior", back_populates="session")

class DriverBehavior(Base):
    __tablename__ = 'driver_behaviors'

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), ForeignKey('monitoring_sessions.session_id'))
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    behavior = Column(String(100), nullable=False)
    confidence = Column(Float, nullable=False)
    is_risky = Column(Boolean, nullable=False, default=False)
    ear = Column(Float)  # Eye Aspect Ratio
    mar = Column(Float)  # Mouth Aspect Ratio
    head_pose = Column(JSON)  # {pitch, yaw, roll}
    additional_metrics = Column(JSON)
    
    session = relationship("MonitoringSession", back_populates="behaviors")

class AlertLog(Base):
    __tablename__ = 'alert_logs'

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), ForeignKey('monitoring_sessions.session_id'))
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    alert_type = Column(String(50), nullable=False)
    severity = Column(String(20), nullable=False)
    message = Column(String(200))
    acknowledged = Column(Boolean, default=False)
    acknowledgment_time = Column(DateTime)

class PerformanceMetric(Base):
    __tablename__ = 'performance_metrics'

    id = Column(Integer, primary_key=True)
    session_id = Column(String(50), ForeignKey('monitoring_sessions.session_id'))
    timestamp = Column(DateTime, nullable=False, default=datetime.utcnow)
    fps = Column(Float)
    processing_time = Column(Float)
    memory_usage = Column(Float)
    cpu_usage = Column(Float)
    gpu_usage = Column(Float)
    additional_metrics = Column(JSON)

def init_db(engine_url):
    """Initialize the database with the schema"""
    engine = create_engine(engine_url)
    Base.metadata.create_all(engine)
    return engine 