
from flask import Flask
from config import Config
from models import db, User, create_database_views
from extensions import login_manager, mail
from routes import register_routes
from deepface import DeepFace
import os



def preload_deepface_models():
    """Preload DeepFace models once at startup to prevent reloading each request."""
    try:
        print(" Loading DeepFace models...")
        DeepFace.build_model("VGG-Face")
        DeepFace.build_model("Emotion")
        print("DeepFace models loaded and cached successfully.")
    except Exception as e:
        print(f"Error preloading DeepFace models: {e}")


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Initialize extensions
    db.init_app(app)
    login_manager.init_app(app)
    mail.init_app(app)

    login_manager.login_view = "login"
    login_manager.login_message = "Please log in to access this page."

    @login_manager.user_loader
    def load_user(user_id):
        return User.query.get(int(user_id))

    # Register routes
    register_routes(app)

    # Create required folders
    for folder in ["uploads", "face_encodings", "static/css", "static/js", "static/images"]:
        os.makedirs(folder, exist_ok=True)

    return app


if __name__ == "__main__":
    preload_deepface_models()
    app = create_app()

    with app.app_context():
        db.create_all()
        create_database_views(db)

        # Create default admin if not exists
        admin = User.query.filter_by(username="admin").first()
        if not admin:
            admin = User(
                username="admin",
                email="admin@example.com",
                name="Admin User",
                is_admin=True,
            )
            admin.set_password("admin123")
            db.session.add(admin)
            db.session.commit()
            print(" Default admin created (username='admin', password='admin123')")

    # Run Flask app
    app.run(debug=True, host="0.0.0.0", port=5000)
