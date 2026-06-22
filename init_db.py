from app import create_app
from models import db, User, create_database_views

from werkzeug.security import generate_password_hash

def init_database():
    app = create_app()
    
    with app.app_context():
        # Create all tables
        db.create_all()
        create_database_views(db)
        
        # Create default admin
        admin = User.query.filter_by(username='admin').first()
        if not admin:
            admin = User(
                username='admin',
                email='admin@example.com',
                name='Admin User',
                is_admin=True,
                security_question='What is the default admin PIN?',
                security_answer_hash=generate_password_hash('1234'),
                admin_pin_hash=generate_password_hash('1234'),
                secret_key='ADMIN-MFA-RECOVERY-KEY-2026'
            )
            admin.set_password('admin123')
            db.session.add(admin)
            db.session.commit()
            print("✓ Database initialized")
            print("✓ Default admin created:")
            print("  Username: admin")
            print("  Password: admin123")
            print("  PIN: 1234")
            print("\nPlease change the admin password after first login!")
        else:
            print("✓ Database already initialized")
            print("✓ Admin user already exists")

if __name__ == '__main__':
    init_database()

