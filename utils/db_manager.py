from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, scoped_session
from sqlalchemy.pool import QueuePool
from contextlib import contextmanager
from datetime import datetime, timedelta
import json
import logging

from models.schema import Base, MonitoringSession, DriverBehavior, AlertLog, PerformanceMetric

logger = logging.getLogger(__name__)

class DatabaseManager:
    def __init__(self, config):
        self.config = config['integration']['database']
        self.engine_url = (
            f"mysql+pymysql://{self.config['username']}:{self.config['password']}"
            f"@{self.config['host']}:{self.config['port']}/{self.config['database']}"
        )
        
        self.engine = create_engine(
            self.engine_url,
            poolclass=QueuePool,
            pool_size=self.config['pool_size'],
            max_overflow=self.config['max_overflow'],
            pool_timeout=self.config['pool_timeout'],
            pool_recycle=self.config['pool_recycle']
        )
        
        self.Session = scoped_session(sessionmaker(bind=self.engine))
        
        # Initialize database schema
        Base.metadata.create_all(self.engine)
    
    @contextmanager
    def session_scope(self):
        """Provide a transactional scope around a series of operations."""
        session = self.Session()
        try:
            yield session
            session.commit()
        except Exception as e:
            session.rollback()
            logger.error(f"Database error: {str(e)}")
            raise
        finally:
            session.close()
    
    def create_monitoring_session(self, device_info=None):
        """Create a new monitoring session"""
        with self.session_scope() as session:
            new_session = MonitoringSession(
                session_id=f"session_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                device_info=device_info
            )
            session.add(new_session)
            session.commit()
            return new_session.session_id
    
    def end_monitoring_session(self, session_id):
        """End a monitoring session"""
        with self.session_scope() as session:
            monitoring_session = session.query(MonitoringSession).filter_by(session_id=session_id).first()
            if monitoring_session:
                monitoring_session.end_time = datetime.utcnow()
                monitoring_session.status = 'completed'
                return True
            return False
    
    def log_behavior(self, session_id, behavior_data):
        """Log driver behavior"""
        with self.session_scope() as session:
            behavior = DriverBehavior(
                session_id=session_id,
                behavior=behavior_data['behavior'],
                confidence=behavior_data['confidence'],
                is_risky=behavior_data.get('is_risky', False),
                ear=behavior_data.get('ear'),
                mar=behavior_data.get('mar'),
                head_pose=behavior_data.get('head_pose'),
                additional_metrics=behavior_data.get('additional_metrics')
            )
            session.add(behavior)
    
    def log_alert(self, session_id, alert_data):
        """Log an alert"""
        with self.session_scope() as session:
            alert = AlertLog(
                session_id=session_id,
                alert_type=alert_data['type'],
                severity=alert_data['severity'],
                message=alert_data.get('message')
            )
            session.add(alert)
    
    def log_performance_metrics(self, session_id, metrics):
        """Log performance metrics"""
        with self.session_scope() as session:
            perf_metric = PerformanceMetric(
                session_id=session_id,
                fps=metrics.get('fps'),
                processing_time=metrics.get('processing_time'),
                memory_usage=metrics.get('memory_usage'),
                cpu_usage=metrics.get('cpu_usage'),
                gpu_usage=metrics.get('gpu_usage'),
                additional_metrics=metrics.get('additional_metrics')
            )
            session.add(perf_metric)
    
    def get_recent_behaviors(self, hours=24, limit=50):
        """Get recent behaviors"""
        with self.session_scope() as session:
            start_time = datetime.utcnow() - timedelta(hours=hours)
            behaviors = session.query(DriverBehavior)\
                .filter(DriverBehavior.timestamp >= start_time)\
                .order_by(DriverBehavior.timestamp.desc())\
                .limit(limit)\
                .all()
            
            return [
                {
                    'id': b.id,
                    'session_id': b.session_id,
                    'timestamp': b.timestamp.isoformat(),
                    'behavior': b.behavior,
                    'confidence': b.confidence,
                    'is_risky': b.is_risky,
                    'ear': b.ear,
                    'mar': b.mar,
                    'head_pose': b.head_pose,
                    'additional_metrics': b.additional_metrics
                }
                for b in behaviors
            ]
    
    def get_session_summary(self, session_id):
        """Get summary for a specific session"""
        with self.session_scope() as session:
            behaviors = session.query(DriverBehavior)\
                .filter_by(session_id=session_id)\
                .all()
            
            alerts = session.query(AlertLog)\
                .filter_by(session_id=session_id)\
                .all()
            
            return {
                'total_behaviors': len(behaviors),
                'risky_behaviors': sum(1 for b in behaviors if b.is_risky),
                'total_alerts': len(alerts),
                'alert_types': {
                    alert_type: sum(1 for a in alerts if a.alert_type == alert_type)
                    for alert_type in set(a.alert_type for a in alerts)
                }
            }
    
    def cleanup_old_data(self, days=30):
        """Clean up old monitoring data"""
        with self.session_scope() as session:
            cutoff_date = datetime.utcnow() - timedelta(days=days)
            
            session.query(PerformanceMetric)\
                .filter(PerformanceMetric.timestamp < cutoff_date)\
                .delete()
            
            session.query(AlertLog)\
                .filter(AlertLog.timestamp < cutoff_date)\
                .delete()
            
            session.query(DriverBehavior)\
                .filter(DriverBehavior.timestamp < cutoff_date)\
                .delete()
            
            session.query(MonitoringSession)\
                .filter(MonitoringSession.start_time < cutoff_date)\
                .delete() 