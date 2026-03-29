from flask import Blueprint
from src.controller.graphql import GraphQLController
from src.trmeric_api.middleware.AuthandLogMiddleware import AuthAndLogMiddleware


graphQlRoutes = Blueprint("graphql", __name__, url_prefix="/trmeric_ai")

controller = GraphQLController()


@graphQlRoutes.route("/graphql/initialize", methods=["POST"])
def graphInitialize():
    return controller.initialize_graph()


# Global schema initialization (admin use only, run once when schema changes)
@graphQlRoutes.route("/graphql/initialize-schema", methods=["POST"])
def graphInitializeSchema():
    return controller.initialize_global_schema()


@graphQlRoutes.route("/graphql/load-roadmaps", methods=["POST"])
def graphLoadRoadmaps():
    return controller.load_roadmaps()


@graphQlRoutes.route("/graphql/load-projects", methods=["POST"])
def graphLoadProjects():
    return controller.load_projects()


@graphQlRoutes.route("/graphql/connect-patterns", methods=["POST"])
def graphConnectPatterns():
    return controller.connect_patterns()


@graphQlRoutes.route("/graphql/aggregate-portfolio", methods=["POST"])
def graphAggregatePortfolio():
    return controller.aggregate_portfolio()


@graphQlRoutes.route("/graphql/aggregate-customer", methods=["POST"])
def graphAggregateCustomer():
    return controller.aggregate_customer()


@graphQlRoutes.route("/graphql/run-knowledge-pipeline", methods=["POST"])
def graphRunKnowledgePipeline():
    return controller.run_knowledge_pipeline()


@graphQlRoutes.route("/graphql/load", methods=["POST"])
def graphLoadData():
    return controller.graphLoadData()


