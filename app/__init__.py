from flask import Flask
from config import Config
from app import db

def create_app(config_class=Config):
    app = Flask(__name__)
    app.config.from_object(config_class)

    db.init_app(app)

    from app.routes import bp as main_bp
    import importlib
    importlib.import_module("app.fleet_routes")
    app.register_blueprint(main_bp)

    @app.errorhandler(Exception)
    def handle_exception(e):
        import traceback
        print("Encountered exception: ", e) # log to vercel functions
        return "<pre><h2>Flask Application Error:</h2><br>" + traceback.format_exc() + "</pre>", 500

    return app
