import requests
import os

class ServiceAssuranceApis:
    def __init__(self):
        self.status_update_api = os.getenv("DJANGO_BACKEND_URL") + "api/projects/tango/status/add/"
        self.risk_update_api = os.getenv("DJANGO_BACKEND_URL") + "api/projects/tango/risk/update/"
        self.action_create_api = os.getenv("DJANGO_BACKEND_URL") + "api/action/tango/add_list"
        self.collaboration_add = os.getenv("DJANGO_BACKEND_URL") + "api/collaborate/tango/add"
        self.headers = {
            'Content-Type': 'application/json'
        }
    
    def post_api(self, request_json, url):
        response = requests.post(url, headers=self.headers, json=request_json)
        return response
    
    def update_status(self, project_id, request_json):
        url = self.status_update_api + f'{project_id}'
        response = self.post_api(request_json, url)
        print("debug_update_status", request_json, response)
        return response
    
    def create_risk(self, project_id, request_json):
        print("debug create_risk data --- ", project_id, request_json)
        url = self.risk_update_api + f'{project_id}'
        response = self.post_api(request_json, url)
        print("debug _ create_risk _ ",  request_json, response, response.text)
        return response
    
    def add_action(self, request_json):
        url = self.action_create_api
        response = self.post_api(request_json, url)
        print("debug _ add_action _ ",  request_json, response, response.text)
        return response
    
    
    def add_collaboration(self, request_json):
        url = self.collaboration_add
        response = self.post_api(request_json, url)
        print("debug _ add_collaboration _ ",  request_json, response, response.text)
        return response