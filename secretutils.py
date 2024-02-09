import os
from google.cloud import secretmanager

PROJECT_ID = "jce-project-411601"

class SecretUtils:
    def __init__(self):
        self.client = secretmanager.SecretManagerServiceClient()
        self.secret_path = f"projects/{PROJECT_ID}/secrets/<secret>/versions/1"

    def get_secret(self, key):
        response = self.client.access_secret_version(name = self.secret_path.replace("<secret>",key))
        return response.payload.data.decode("UTF-8")
