from app import create_app
from app.models import db
import os

app = create_app()

# Ensure that the database tables are created automatically on launch
with app.app_context():
    db.create_all()

if __name__ == '__main__':
    # Bind to 0.0.0.0 and use the PORT env var so Railway can route traffic
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
