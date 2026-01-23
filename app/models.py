from . import db
from sqlalchemy.sql import func

class Incident(db.Model):
    incident_id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    timestamp = db.Column(db.DateTime(timezone=True), server_default=func.now())
    student_id = db.Column(db.String(50), nullable=False)
    behavior = db.Column(db.String(100), nullable=False)
    confidence = db.Column(db.Float, nullable=False)
    video_clip_path = db.Column(db.String(255))
    camera_id = db.Column(db.Integer, nullable=False)
    reviewed_status = db.Column(db.Boolean, default=False)
    bbox_x = db.Column(db.Float)
    bbox_y = db.Column(db.Float)
    bbox_w = db.Column(db.Float)
    bbox_h = db.Column(db.Float)
    
    def to_dict(self):
        return {
            'incident_id': self.incident_id,
            'timestamp': self.timestamp.isoformat(),
            'student_id': self.student_id,
            'behavior': self.behavior,
            'confidence': self.confidence,
            'video_clip_path': self.video_clip_path,
            'camera_id': self.camera_id,
            'reviewed_status': self.reviewed_status,
            'bbox': {
                'x': self.bbox_x,
                'y': self.bbox_y,
                'w': self.bbox_w,
                'h': self.bbox_h
            }
        }
