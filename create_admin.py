import os
import sys
from app import create_app
from app.models import db, User

def main():
    app = create_app()
    with app.app_context():
        # Ensure database tables exist
        db.create_all()
        
        print("========================================")
        print("  Antigravity Admin Account Generator   ")
        print("========================================")
        
        # Check if an admin already exists
        admin_exists = User.query.filter_by(role='admin').first()
        if admin_exists:
            print(f"Warning: An administrator user ({admin_exists.username}) already exists in the database.")
            proceed = input("Do you want to create another administrator? (y/n): ").strip().lower()
            if proceed != 'y':
                print("Aborting.")
                sys.exit(0)
        
        # Prompt for username
        username = input("Enter admin username: ").strip()
        if not username:
            print("Error: Username cannot be empty.")
            sys.exit(1)
            
        # Check if username is taken
        existing_user = User.query.filter_by(username=username).first()
        if existing_user:
            print(f"Error: A user with username '{username}' already exists.")
            sys.exit(1)
            
        import getpass
        password = getpass.getpass("Enter admin password (numbers only): ").strip()
        if len(password) < 6:
            print("Error: Password must be at least 6 characters long.")
            sys.exit(1)
        if not password.isdigit():
            print("Error: Password must contain only numbers.")
            sys.exit(1)
            
        confirm_password = getpass.getpass("Confirm admin password: ").strip()
        if password != confirm_password:
            print("Error: Passwords do not match.")
            sys.exit(1)
            
        # Create and save admin
        user = User(username=username, role='admin')
        user.set_password(password)
        db.session.add(user)
        db.session.commit()
        
        print("\nSUCCESS: Administrator account created successfully!")
        print(f"Username: {username}")
        print("Role: admin")
        print("========================================")

if __name__ == '__main__':
    main()
