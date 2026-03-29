
### path --- src/trmeric_services/cron/cron.py

import requests

if __name__ == "__main__":
    try:
        print("Triggering daily cron job via POST request...")
        
        response = requests.post(
            'http://localhost:8000/trmeric_ai/cron/v2/run',
            headers={
                "client-secret": "MY_SECRET",
                "Content-Type": "application/json"
            }
        )
        
    except Exception as e:
        print(f"Error while making POST request: {str(e)}")

