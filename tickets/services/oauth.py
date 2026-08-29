import json
from urllib.parse import urlencode
from urllib.request import Request, urlopen
from .security import decrypt, encrypt

PROVIDERS={
    "GMAIL":{"token":"https://oauth2.googleapis.com/token","scope":"https://mail.google.com/"},
    "OUTLOOK":{"token":"https://login.microsoftonline.com/common/oauth2/v2.0/token","scope":"https://outlook.office.com/IMAP.AccessAsUser.All offline_access"},
    "YAHOO":{"token":"https://api.login.yahoo.com/oauth2/get_token","scope":"mail-r"},
}

def refresh_access_token(account):
    cfg=PROVIDERS.get(account.provider)
    if not cfg: raise RuntimeError(f"OAuth2 is not configured for provider {account.provider}.")
    client_id=decrypt(account.oauth_client_id_encrypted); client_secret=decrypt(account.oauth_client_secret_encrypted); refresh=decrypt(account.oauth_refresh_token_encrypted)
    if not client_id or not client_secret or not refresh: raise RuntimeError("OAuth2 requires client ID, client secret and refresh token.")
    data=urlencode({"client_id":client_id,"client_secret":client_secret,"refresh_token":refresh,"grant_type":"refresh_token","scope":cfg["scope"]}).encode()
    req=Request(cfg["token"],data=data,headers={"Content-Type":"application/x-www-form-urlencoded"},method="POST")
    with urlopen(req,timeout=20) as r: payload=json.loads(r.read().decode())
    if "access_token" not in payload: raise RuntimeError(payload.get("error_description") or payload.get("error") or "OAuth token refresh failed")
    return payload["access_token"]
