import os
import json
import time
import uuid
import httpx

BASE = "https://www.googleapis.com/drive/v3"
UPLOAD_BASE = "https://www.googleapis.com/upload/drive/v3"
DELAY = 0.05
MAX_RETRIES = 3


def _retry_request(method, url, headers, timeout=15, **kwargs):
    """Execute HTTP request with exponential backoff on 429 rate limits."""
    time.sleep(DELAY)
    for attempt in range(MAX_RETRIES + 1):
        with httpx.Client(timeout=timeout) as c:
            r = c.request(method, url, headers=headers, **kwargs)
        if r.status_code == 429:
            if attempt < MAX_RETRIES:
                wait = min(2 ** attempt, 30)
                time.sleep(wait)
                continue
        if r.status_code >= 400:
            try:
                detail = r.json()
            except Exception:
                detail = r.text[:500]
            raise Exception(f"HTTP {r.status_code}: {json.dumps(detail) if isinstance(detail, dict) else detail}")
        return r


def get_access_token(creds_json):
    """Exchange refresh token for a fresh access token from credentials JSON."""
    creds = json.loads(creds_json) if isinstance(creds_json, str) else creds_json
    r = httpx.post(
        "https://oauth2.googleapis.com/token",
        data={
            "client_id": creds["client_id"],
            "client_secret": creds["client_secret"],
            "refresh_token": creds["refresh_token"],
            "grant_type": "refresh_token",
        },
    )
    r.raise_for_status()
    return r.json()["access_token"]


def api_get(headers, path, params=None, timeout=15):
    return _retry_request("GET", f"{BASE}/{path}", headers, timeout=timeout, params=params or {}).json()


def api_post(headers, path, body, timeout=15):
    return _retry_request("POST", f"{BASE}/{path}", headers, timeout=timeout, json=body).json()


def api_patch(headers, path, body, timeout=15):
    return _retry_request("PATCH", f"{BASE}/{path}", headers, timeout=timeout, json=body).json()


def multipart_upload(headers, metadata, content, content_type, timeout=30):
    """Upload file using multipart/related for Drive API."""
    time.sleep(DELAY)
    boundary = uuid.uuid4().hex
    body = (
        f"--{boundary}\r\n"
        f"Content-Type: application/json; charset=UTF-8\r\n\r\n"
        f"{json.dumps(metadata)}\r\n"
        f"--{boundary}\r\n"
        f"Content-Type: {content_type}\r\n\r\n"
        f"{content}\r\n"
        f"--{boundary}--"
    )
    upload_headers = dict(headers)
    upload_headers["Content-Type"] = f"multipart/related; boundary={boundary}"
    with httpx.Client(timeout=timeout) as c:
        r = c.post(
            f"{UPLOAD_BASE}/files?uploadType=multipart&fields=id,name,mimeType,webViewLink",
            headers=upload_headers,
            content=body.encode("utf-8"),
        )
        r.raise_for_status()
        return r.json()


def file_link(file_id):
    return f"https://drive.google.com/file/d/{file_id}/view"


# --- Actions ---


def do_list_files(headers, folder_id, max_results):
    fid = folder_id or "root"
    q = f"'{fid}' in parents and trashed = false"
    data = api_get(
        headers,
        "files",
        params={
            "q": q,
            "pageSize": max_results,
            "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
            "orderBy": "modifiedTime desc",
        },
    )
    files = data.get("files", [])
    return {
        "files": [
            {
                "id": f["id"],
                "name": f["name"],
                "type": f.get("mimeType", ""),
                "modified": f.get("modifiedTime", ""),
                "size": f.get("size"),
                "url": f.get("webViewLink", file_link(f["id"])),
            }
            for f in files
        ],
        "count": len(files),
    }


def do_search_files(headers, query, max_results):
    q = f"{query} and trashed = false" if query else "trashed = false"
    data = api_get(
        headers,
        "files",
        params={
            "q": q,
            "pageSize": max_results,
            "fields": "files(id,name,mimeType,modifiedTime,size,webViewLink)",
            "orderBy": "modifiedTime desc",
        },
    )
    files = data.get("files", [])
    return {
        "files": [
            {
                "id": f["id"],
                "name": f["name"],
                "type": f.get("mimeType", ""),
                "modified": f.get("modifiedTime", ""),
                "size": f.get("size"),
                "url": f.get("webViewLink", file_link(f["id"])),
            }
            for f in files
        ],
        "count": len(files),
    }


def do_get_file_info(headers, file_id):
    data = api_get(
        headers,
        f"files/{file_id}",
        params={
            "fields": "id,name,mimeType,modifiedTime,createdTime,size,webViewLink,owners,sharingUser,shared,parents"
        },
    )
    return {
        "id": data["id"],
        "name": data.get("name", ""),
        "type": data.get("mimeType", ""),
        "created": data.get("createdTime", ""),
        "modified": data.get("modifiedTime", ""),
        "size": data.get("size"),
        "shared": data.get("shared", False),
        "owners": [o.get("emailAddress", "") for o in data.get("owners", [])],
        "parents": data.get("parents", []),
        "url": data.get("webViewLink", file_link(data["id"])),
    }


def do_create_folder(headers, name, folder_id):
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if folder_id:
        metadata["parents"] = [folder_id]
    data = api_post(headers, "files?fields=id,name,webViewLink", metadata)
    return {
        "id": data["id"],
        "name": data.get("name", ""),
        "url": data.get("webViewLink", file_link(data["id"])),
    }


def do_create_document(headers, name, content, folder_id):
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.document",
    }
    if folder_id:
        metadata["parents"] = [folder_id]
    if content:
        return multipart_upload(headers, metadata, content, "text/plain")
    data = api_post(headers, "files?fields=id,name,mimeType,webViewLink", metadata)
    return {
        "id": data["id"],
        "name": data.get("name", ""),
        "type": data.get("mimeType", ""),
        "url": data.get("webViewLink", file_link(data["id"])),
    }


def do_create_spreadsheet(headers, name, content, folder_id):
    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.spreadsheet",
    }
    if folder_id:
        metadata["parents"] = [folder_id]
    if content:
        return multipart_upload(headers, metadata, content, "text/csv")
    data = api_post(headers, "files?fields=id,name,mimeType,webViewLink", metadata)
    return {
        "id": data["id"],
        "name": data.get("name", ""),
        "type": data.get("mimeType", ""),
        "url": data.get("webViewLink", file_link(data["id"])),
    }


def do_upload_text(headers, name, content, mime_type, folder_id):
    metadata = {"name": name}
    if folder_id:
        metadata["parents"] = [folder_id]
    return multipart_upload(headers, metadata, content, mime_type)


def do_download_text(headers, file_id):
    """Download file content. Exports Google Docs as text, Sheets as CSV."""
    time.sleep(DELAY)
    # First get the file type
    info = api_get(headers, f"files/{file_id}", params={"fields": "id,name,mimeType"})
    mime = info.get("mimeType", "")

    with httpx.Client(timeout=30) as c:
        if mime == "application/vnd.google-apps.document":
            r = c.get(
                f"{BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/plain"},
            )
        elif mime == "application/vnd.google-apps.spreadsheet":
            r = c.get(
                f"{BASE}/files/{file_id}/export",
                headers=headers,
                params={"mimeType": "text/csv"},
            )
        else:
            r = c.get(
                f"{BASE}/files/{file_id}",
                headers=headers,
                params={"alt": "media"},
            )
        r.raise_for_status()
        return {
            "id": file_id,
            "name": info.get("name", ""),
            "type": mime,
            "content": r.text,
        }


def do_move_file(headers, file_id, destination_folder_id):
    # Get current parents
    info = api_get(headers, f"files/{file_id}", params={"fields": "id,name,parents"})
    current_parents = ",".join(info.get("parents", []))
    time.sleep(DELAY)
    with httpx.Client(timeout=15) as c:
        r = c.patch(
            f"{BASE}/files/{file_id}",
            headers=headers,
            params={
                "addParents": destination_folder_id,
                "removeParents": current_parents,
                "fields": "id,name,parents,webViewLink",
            },
        )
        r.raise_for_status()
        data = r.json()
    return {
        "id": data["id"],
        "name": data.get("name", ""),
        "parents": data.get("parents", []),
        "url": data.get("webViewLink", file_link(data["id"])),
    }


def do_copy_file(headers, file_id, name):
    body = {}
    if name:
        body["name"] = name
    data = api_post(headers, f"files/{file_id}/copy?fields=id,name,webViewLink", body)
    return {
        "id": data["id"],
        "name": data.get("name", ""),
        "url": data.get("webViewLink", file_link(data["id"])),
    }


def do_rename_file(headers, file_id, name):
    data = api_patch(
        headers, f"files/{file_id}?fields=id,name,webViewLink", {"name": name}
    )
    return {
        "id": data["id"],
        "name": data.get("name", ""),
        "url": data.get("webViewLink", file_link(data["id"])),
    }


def do_trash_file(headers, file_id):
    data = api_patch(headers, f"files/{file_id}?fields=id,name,trashed", {"trashed": True})
    return {"id": data["id"], "name": data.get("name", ""), "trashed": True}


def do_share_file(headers, file_id, share_email, share_role, share_type, notify):
    permission = {"role": share_role, "type": share_type}
    if share_type in ("user", "group"):
        permission["emailAddress"] = share_email
    time.sleep(DELAY)
    with httpx.Client(timeout=15) as c:
        r = c.post(
            f"{BASE}/files/{file_id}/permissions",
            headers=headers,
            params={
                "sendNotificationEmail": str(notify).lower(),
                "fields": "id,role,type,emailAddress",
            },
            json=permission,
        )
        # Auto-retry with "group" if "user" type fails (e.g. sharing with a Google Group)
        if r.status_code in (400, 404) and share_type == "user":
            permission["type"] = "group"
            time.sleep(DELAY)
            r = c.post(
                f"{BASE}/files/{file_id}/permissions",
                headers=headers,
                params={
                    "sendNotificationEmail": str(notify).lower(),
                    "fields": "id,role,type,emailAddress",
                },
                json=permission,
            )
        r.raise_for_status()
        data = r.json()
    return {
        "permission_id": data.get("id"),
        "role": data.get("role"),
        "type": data.get("type"),
        "email": data.get("emailAddress", ""),
    }


def do_list_permissions(headers, file_id):
    data = api_get(
        headers,
        f"files/{file_id}/permissions",
        params={"fields": "permissions(id,role,type,emailAddress,displayName)"},
    )
    perms = data.get("permissions", [])
    return {
        "permissions": [
            {
                "id": p.get("id"),
                "role": p.get("role"),
                "type": p.get("type"),
                "email": p.get("emailAddress", ""),
                "name": p.get("displayName", ""),
            }
            for p in perms
        ],
        "count": len(perms),
    }


# --- Main ---

try:
    creds_json = os.environ["GOOGLE_DRIVE_CREDENTIALS_JSON"]
    inp = json.loads(os.environ.get("INPUT_JSON", "{}"))
    action = inp.get("action", "")

    token = get_access_token(creds_json)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if action == "list_files":
        result = do_list_files(headers, inp.get("folder_id", ""), inp.get("max_results", 20))
    elif action == "search_files":
        result = do_search_files(headers, inp.get("query", ""), inp.get("max_results", 20))
    elif action == "get_file_info":
        result = do_get_file_info(headers, inp["file_id"])
    elif action == "create_folder":
        result = do_create_folder(headers, inp["name"], inp.get("folder_id", ""))
    elif action == "create_document":
        result = do_create_document(headers, inp["name"], inp.get("content", ""), inp.get("folder_id", ""))
    elif action == "create_spreadsheet":
        result = do_create_spreadsheet(headers, inp["name"], inp.get("content", ""), inp.get("folder_id", ""))
    elif action == "upload_text":
        result = do_upload_text(headers, inp["name"], inp.get("content", ""), inp.get("mime_type", "text/plain"), inp.get("folder_id", ""))
    elif action == "download_text":
        result = do_download_text(headers, inp["file_id"])
    elif action == "move_file":
        result = do_move_file(headers, inp["file_id"], inp["destination_folder_id"])
    elif action == "copy_file":
        result = do_copy_file(headers, inp["file_id"], inp.get("name", ""))
    elif action == "rename_file":
        result = do_rename_file(headers, inp["file_id"], inp["name"])
    elif action == "trash_file":
        result = do_trash_file(headers, inp["file_id"])
    elif action == "share_file":
        result = do_share_file(
            headers,
            inp["file_id"],
            inp.get("share_email", ""),
            inp.get("share_role", "reader"),
            inp.get("share_type", "user"),
            inp.get("notify", True),
        )
    elif action == "list_permissions":
        result = do_list_permissions(headers, inp["file_id"])
    else:
        result = {"error": f"Unknown action: {action}"}

    print(json.dumps(result))

except Exception as e:
    print(json.dumps({"error": str(e)}))
