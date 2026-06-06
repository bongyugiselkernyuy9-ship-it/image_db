from datetime import datetime
from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model, UserMixin):
    __tablename__ = 'users'
    
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.String(256), nullable=False)
    role = db.Column(db.String(20), nullable=False, default='employee')  # 'admin' or 'employee'
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    created_employees = db.relationship('Employee', backref='creator', lazy=True)
    uploaded_files = db.relationship('FileMetadata', backref='uploader', lazy=True,
                                     foreign_keys='FileMetadata.uploader_id')
    file_views = db.relationship('FileView', backref='user', lazy=True)
    
    def set_password(self, password):
        self.password_hash = generate_password_hash(password)
        
    def check_password(self, password):
        return check_password_hash(self.password_hash, password)
        
    @property
    def is_admin(self):
        return self.role == 'admin'

    def __repr__(self):
        return f'<User {self.username} ({self.role})>'


class Employee(db.Model):
    __tablename__ = 'employees'
    
    id = db.Column(db.Integer, primary_key=True)
    full_name = db.Column(db.String(128), nullable=False)
    employee_id = db.Column(db.String(64), unique=True, nullable=False, index=True)
    department = db.Column(db.String(64), nullable=False)
    position = db.Column(db.String(64), nullable=False)
    email = db.Column(db.String(120), nullable=False)
    phone = db.Column(db.String(20), nullable=False)
    hire_date = db.Column(db.Date, nullable=False)
    photo = db.Column(db.String(256), nullable=True)  # Store relative path/filename of photo
    created_by_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)
    
    # Relationships
    files = db.relationship('FileMetadata', backref='employee', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<Employee {self.full_name} ({self.employee_id})>'


class FileMetadata(db.Model):
    __tablename__ = 'files'
    
    id = db.Column(db.Integer, primary_key=True)
    filename = db.Column(db.String(256), unique=True, nullable=False)  # Sanitized, stored filename on disk
    original_name = db.Column(db.String(256), nullable=False)          # Original filename on upload
    file_type = db.Column(db.String(128), nullable=False)              # MIME type, e.g., 'image/png'
    upload_date = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    size = db.Column(db.Integer, nullable=False)                       # Size in bytes
    tags = db.Column(db.String(256), nullable=True)                    # Comma-separated tags
    
    # Foreign keys
    uploader_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    employee_id = db.Column(db.Integer, db.ForeignKey('employees.id'), nullable=False)
    
    # --- Soft Delete Fields ---
    # When True, the file is in the trash and hidden from normal listings
    deleted = db.Column(db.Boolean, default=False, nullable=False)
    # Timestamp of when the file was moved to trash
    deleted_at = db.Column(db.DateTime, nullable=True)
    # ID of the user who performed the soft delete
    deleted_by = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True)
    
    # Relationship to the user who deleted the file (separate from uploader)
    deleter = db.relationship('User', foreign_keys=[deleted_by], backref='deleted_files')
    # Relationship to file view records
    views = db.relationship('FileView', backref='file', lazy=True, cascade="all, delete-orphan")

    def __repr__(self):
        return f'<FileMetadata {self.original_name}>'


class FileView(db.Model):
    """Tracks which users have viewed which files.
    A user must view a file before they are allowed to delete it.
    Each user+file pair has at most one record (unique constraint).
    """
    __tablename__ = 'file_views'
    
    id = db.Column(db.Integer, primary_key=True)
    file_id = db.Column(db.Integer, db.ForeignKey('files.id'), nullable=False)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    viewed_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    
    # Prevent duplicate view records for the same user+file combination
    __table_args__ = (
        db.UniqueConstraint('file_id', 'user_id', name='uq_file_user_view'),
    )
    
    def __repr__(self):
        return f'<FileView file={self.file_id} user={self.user_id} at {self.viewed_at}>'


class AuditLog(db.Model):
    __tablename__ = 'audit_logs'
    
    id = db.Column(db.Integer, primary_key=True)
    action = db.Column(db.String(64), nullable=False, index=True)      # e.g., 'LOGIN', 'UPLOAD_FILE', etc.
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=True) # Nullable if anonymous or deleted
    username = db.Column(db.String(64), nullable=False)                # Preserve username even if user deleted
    timestamp = db.Column(db.DateTime, default=datetime.utcnow, index=True)
    details = db.Column(db.Text, nullable=True)                        # Contextual log details

    def __repr__(self):
        return f'<AuditLog {self.action} by {self.username} at {self.timestamp}>'
