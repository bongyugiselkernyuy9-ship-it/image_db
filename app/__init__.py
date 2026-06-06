import os
from flask import Flask
from flask_login import LoginManager
from flask_wtf.csrf import CSRFProtect
from app.models import db, User, FileView

login_manager = LoginManager()
login_manager.login_view = 'main.login'
login_manager.login_message_category = 'warning'
csrf = CSRFProtect()

def create_app():
    app = Flask(__name__)
    
    # Configure directories
    base_dir = os.path.abspath(os.path.dirname(os.path.dirname(__file__)))
    instance_dir = os.path.join(base_dir, 'instance')
    upload_dir = os.path.join(base_dir, 'uploads')
    trash_dir = os.path.join(base_dir, 'trash')   # Soft-deleted files are moved here
    
    os.makedirs(instance_dir, exist_ok=True)
    os.makedirs(upload_dir, exist_ok=True)
    os.makedirs(trash_dir, exist_ok=True)
    
    # Configurations
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'dev-key-antigravity-123456789')
    app.config['SQLALCHEMY_DATABASE_URI'] = os.environ.get(
        'DATABASE_URL', f"sqlite:///{os.path.join(instance_dir, 'app.db')}"
    )
    app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
    
    # File uploads configuration
    app.config['UPLOAD_FOLDER'] = upload_dir
    app.config['TRASH_FOLDER'] = trash_dir
    # Limit maximum upload file size to 2 GB (2 * 1024 * 1024 * 1024 bytes)
    app.config['MAX_CONTENT_LENGTH'] = 2 * 1024 * 1024 * 1024
    
    # Security cookies
    app.config['SESSION_COOKIE_SECURE'] = False  # Local environment
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    
    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    csrf.init_app(app)
    
    # Register user loader
    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))
    
    # Custom Jinja filters
    @app.template_filter('filesize')
    def format_filesize(size_in_bytes):
        if size_in_bytes is None:
            return "0 Bytes"
        for unit in ['Bytes', 'KB', 'MB', 'GB']:
            if size_in_bytes < 1024.0:
                return f"{size_in_bytes:.2f} {unit}"
            size_in_bytes /= 1024.0
        return f"{size_in_bytes:.2f} TB"
        
    @app.template_filter('datetimeformat')
    def format_datetime(value, format='%Y-%m-%d %H:%M'):
        if value is None:
            return ""
        return value.strftime(format)
        
    # Register blueprint (routes)
    from app.routes import bp
    app.register_blueprint(bp)
    
    # Create DB tables if they don't exist
    with app.app_context():
        db.create_all()
    
    return app
