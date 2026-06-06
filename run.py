from app import create_app
from app.models import db

app = create_app()

# Ensure that the database tables are created automatically on launch
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Start the server locally
    app.run(host='127.0.0.1', port=5000, debug=True)
