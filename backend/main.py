# ── main.py (or whichever file you use to start the app) ──

from config import app, db
from model_editor import model_editor_bp
from model_converter import model_converter_bp
from surrogate_model import surrogate_modeling_bp
from sessions import sessions_bp
from bms_api import bms_bp
from idf_editor import idf_editor_bp
from weather_editor import weather_bp
from instrument import instrument_bp

# Register each blueprint under its URL prefix
app.register_blueprint(model_editor_bp, url_prefix='/model_editor')
app.register_blueprint(instrument_bp, url_prefix='/model_editor')
app.register_blueprint(model_converter_bp, url_prefix='/model_converter')
app.register_blueprint(surrogate_modeling_bp, url_prefix='/surrogate_modeling')
app.register_blueprint(sessions_bp, url_prefix='/sessions')
app.register_blueprint(bms_bp, url_prefix='/bms')
app.register_blueprint(idf_editor_bp, url_prefix='/idf_editor')
app.register_blueprint(weather_bp, url_prefix='/weather')

if __name__ == '__main__':
    # Create all database tables if they don't already exist
    with app.app_context():
        db.create_all()
        # The sessions that ship with the platform (the bdopt demo) are offered in the Sessions menu, and
        # the demo is opened by itself on a fresh instance (no session, no model). A failure here must not
        # stop the platform.
        try:
            import sessions
            sessions.seed_sessions_if_missing()
            # populate_tables writes the progress into the Flask session: it needs a request context.
            with app.test_request_context():
                warnings = sessions.open_demo_if_empty()
            if warnings is not None:
                print('Demo session opened.', *warnings, flush=True)
        except Exception as exc:
            print(f'Demo session not loaded: {exc}', flush=True)

    # host="0.0.0.0" so Docker can forward 5000 from the host into the container.
    #
    # debug=False is load-bearing, not tidiness:
    #  - The reloader watches everything under /app, and export_model writes
    #    parameters.py into /app/base_notebooks. With the reloader on, the server
    #    restarted mid-request and the export download was lost at random.
    #  - The Werkzeug debugger executes arbitrary code from the browser; the
    #    platform ships with its port published, so it must never be enabled.
    #
    # Single process (rather than several gunicorn workers) keeps the in-memory
    # IDF in idf_session coherent, and avoids a worker timeout killing the
    # multi-minute EnergyPlus probe run and FMU conversion. threaded=True still
    # lets the UI poll /progress while one of those is running.
    app.run(host="0.0.0.0", port=5000, debug=False, use_reloader=False, threaded=True)
