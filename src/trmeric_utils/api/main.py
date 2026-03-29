# curl --location 'http://localhost:8000/api/notifications/tango_generated_notification' \
# --header 'Content-Type: application/json' \
# --data-raw '{
#     "receiver_email":"siddharth.govindarajulu@gmail.com",
#     "email_content": "<div><h4>Projects Overview</h4></div><h4>Upcoming Project Milestones and Risk Items Notification</h4>"
# }'


import requests
import os

class ApiUtils:
    def __init__(self):
        self.notification_url = os.getenv("DJANGO_BACKEND_URL") + "api/notifications/tango_generated_notification"
        self.headers = {
            'Content-Type': 'application/json'
        }
        
    def post_api(self, request_json, url):
        response = requests.post(url, headers=self.headers, json=request_json)
        return response
    
    def send_notification_mail_api(self, email_content, receiver_email, email_data = {}, template_key='TANGO-ALERT' ):
        try:
            url = self.notification_url
            request_json = {
                "email_content": email_content,
                "email_data": email_data,
                "receiver_email": receiver_email,
                "template_key": template_key
            }
            response = self.post_api(request_json, url)
            # print("debug_notification_mail_api", request_json, response)
            return response
        except Exception as e:
            return {"status": "error", "message": str(e), "event": "send_notification_mail_api_failed"}
