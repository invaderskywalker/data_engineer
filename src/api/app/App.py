from flask import Flask, request, g
# from flask_socketio import SocketIO
# from src.trmeric_services.provider.Routes import providerBP
from src.routes.idea_pad import ideaBP
from src.database.Database import db_instance
from flask_cors import CORS
from src.api.middleware.request_logging import RequestLoggingMiddleware
from src.routes.discovery import discoveryQA
from src.routes.qna import qnaRoute
from src.routes.insight import insightRoute
from src.routes.integration import integrationRoute
from src.routes.tango import tangoRoutes
from src.routes.project import projectRoutesBP
from src.routes.cron import cronBP
from src.routes.roadmap import roadmapRoutesBP
from src.ws.events import init_websocket_events
from src.routes.agents import trmericAIRoute
from src.routes.provider import providerBP
from src.routes.internal import internalRoutes
from src.routes.graphql import graphQlRoutes
from src.routes.pinboard import pinBoardRoute
from src.routes.potential import potentialRoute
from src.routes.super_agent import superAgentAIRoute
from src.routes.health import healthRoute

from src.utils.socketio_init import SocketInitializer


import eventlet


eventlet.monkey_patch()

def init_routes(app: Flask):
    app.register_blueprint(providerBP)
    app.register_blueprint(discoveryQA)
    app.register_blueprint(ideaBP)
    app.register_blueprint(qnaRoute)
    app.register_blueprint(insightRoute)
    app.register_blueprint(integrationRoute)
    app.register_blueprint(tangoRoutes)
    app.register_blueprint(projectRoutesBP)
    app.register_blueprint(cronBP)
    app.register_blueprint(roadmapRoutesBP)
    app.register_blueprint(trmericAIRoute)
    app.register_blueprint(internalRoutes)
    app.register_blueprint(pinBoardRoute)
    app.register_blueprint(potentialRoute)
    app.register_blueprint(graphQlRoutes)
    app.register_blueprint(superAgentAIRoute)
    app.register_blueprint(healthRoute)


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

