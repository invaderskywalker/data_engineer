from flask import Flask, request, g
# from flask_socketio import SocketIO
# from src.trmeric_services.provider.Routes import providerBP
from src.database.Database import db_instance
from flask_cors import CORS
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.ws.events import init_websocket_events
from src.routes.super_agent import superAgentAIRoute
from src.routes.health import healthRoute
from src.routes.data_engineer import dataEngineerRoute

from src.utils.socketio_init import SocketInitializer


import eventlet


eventlet.monkey_patch()

def init_routes(app: Flask):
    app.register_blueprint(superAgentAIRoute)
    app.register_blueprint(healthRoute)
    app.register_blueprint(dataEngineerRoute)


# socketio = SocketIO(cors_allowed_origins="*")
ALLOWED_ORIGINS = [
    "http://localhost:5173",
    "http://localhost:5174",
    "https://trmeric.com",
    "https://trmeric-live.trmeric.com",
    "https://trmeric-dev.trmeric.com",
    "https://dev.tangotrmeric.com",
    "https://qa.tangotrmeric.com",
    "https://production.tangotrmeric.com",
    "https://www.trmeric.com",
    "https://eu-trmeric-live.trmeric.com",
    "https://eu.qa.tangotrmeric.com",
]

# def get_mongo_client():
#     """Get or create MongoDB client in app context."""
#     if 'mongo_client' not in g:
#         g.mongo_client = MongoBaseClient()
#         # g.mongo_client.initialize_all_models()
        
#         job_dao = JobDAO(self.connection_string)
#         job_dao.create_collection()   # Ensure collection exists
#         job_dao._ensure_indexes()
        
#     return g.mongo_client

def create_app():
    app = Flask(__name__)
    CORS(app, origins=ALLOWED_ORIGINS, supports_credentials=True)


    init_routes(app)
    app.before_request(RequestLoggingMiddleware.log_request_info)
    
    db_instance.connect()
    # MongoInitializer().initialize_all_models()
    
    # Initialize MongoDB on app startup
    # with app.app_context():
    #     get_mongo_client()  # Ensure MongoDB client is initialized

    @app.teardown_appcontext
    def close_connections(exception):
        # Close PostgreSQL connection
        db_instance.closeDatabase()
        # Close MongoDB connection
        # if 'mongo_client' in g:
        #     g.mongo_client.close()
        #     g.pop('mongo_client')

    # @app.teardown_appcontext
    # def close_db_connection(exception):
    #     db_instance.closeDatabase()

    # Initialize SocketIO with matching CORS settings
    socketio = SocketInitializer().get_socketio()
    socketio.init_app(app, cors_allowed_origins=ALLOWED_ORIGINS)
    
    # Set up WebSocket events (after app setup)
    init_websocket_events(socketio)
    return app


app = create_app()

