from google_auth_oauthlib.flow import InstalledAppFlow
from google.oauth2.credentials import Credentials

SCOPES = ["https://www.googleapis.com/auth/drive.file"]

flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
creds = flow.run_local_server(port=0)  # opens a local browser on your PC

print("refresh_token =", creds.refresh_token)
print("client_id =", creds.client_id)
print("client_secret =", creds.client_secret)
print("token_uri =", creds.token_uri)
