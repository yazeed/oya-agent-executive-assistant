import os
import json
import httpx
import uuid
import time
from datetime import datetime, timezone

BASE = "https://www.googleapis.com/calendar/v3"
MAX_RETRIES = 3


def get_access_token(creds_json):
    """Exchange refresh token for a fresh access token from credentials JSON."""
    creds = json.loads(creds_json) if isinstance(creds_json, str) else creds_json
    if creds.get("type") == "authorized_user":
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
    else:
        from google.oauth2 import service_account
        from google.auth.transport.requests import Request
        sa_creds = service_account.Credentials.from_service_account_info(
            creds, scopes=["https://www.googleapis.com/auth/calendar"]
        )
        sa_creds.refresh(Request())
        return sa_creds.token


def _retry_request(method, url, headers, timeout=15, **kwargs):
    """Execute HTTP request with exponential backoff on 429 rate limits."""
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


def api_get(headers, path, params=None, timeout=15):
    return _retry_request("GET", f"{BASE}/{path}", headers, timeout=timeout, params=params or {}).json()


def api_post(headers, path, body, params=None, timeout=15):
    return _retry_request("POST", f"{BASE}/{path}", headers, timeout=timeout, json=body, params=params or {}).json()


def api_patch(headers, path, body, params=None, timeout=15):
    return _retry_request("PATCH", f"{BASE}/{path}", headers, timeout=timeout, json=body, params=params or {}).json()


def api_delete(headers, path, params=None, timeout=15):
    _retry_request("DELETE", f"{BASE}/{path}", headers, timeout=timeout, params=params or {})


def parse_attendees(attendees_str):
    """Parse comma-separated emails into attendee list."""
    if not attendees_str or not attendees_str.strip():
        return []
    return [{"email": e.strip()} for e in attendees_str.split(",") if e.strip()]


def parse_reminders(reminders_str):
    """Parse reminders string into API format."""
    if not reminders_str or reminders_str == "default":
        return {"useDefault": True}
    if reminders_str == "none":
        return {"useDefault": False, "overrides": []}
    overrides = []
    for m in reminders_str.split(","):
        m = m.strip()
        if m.isdigit():
            overrides.append({"method": "popup", "minutes": int(m)})
    if not overrides:
        return {"useDefault": True}
    return {"useDefault": False, "overrides": overrides}


def is_all_day(time_str):
    """Check if a time string is a date-only (all-day event)."""
    if not time_str:
        return False
    try:
        datetime.strptime(time_str.strip(), "%Y-%m-%d")
        return True
    except ValueError:
        return False


def make_time_body(start_time, end_time, tz):
    """Build start/end dicts for the API, handling all-day vs timed events."""
    body = {}
    if start_time:
        if is_all_day(start_time):
            body["start"] = {"date": start_time.strip()}
            body["end"] = {"date": end_time.strip()} if end_time else {"date": start_time.strip()}
        else:
            body["start"] = {"dateTime": start_time}
            body["end"] = {"dateTime": end_time} if end_time else {"dateTime": start_time}
            if tz:
                body["start"]["timeZone"] = tz
                body["end"]["timeZone"] = tz
    return body


def make_conference_data():
    """Build conferenceData for a Google Meet link."""
    return {
        "createRequest": {
            "requestId": str(uuid.uuid4()),
            "conferenceSolutionKey": {"type": "hangoutsMeet"},
        }
    }


def format_event(e):
    """Format a calendar event for output."""
    start = e.get("start", {})
    end = e.get("end", {})
    attendees = e.get("attendees", [])
    conference = e.get("conferenceData", {})
    meet_link = ""
    for ep in conference.get("entryPoints", []):
        if ep.get("entryPointType") == "video":
            meet_link = ep.get("uri", "")
            break
    return {
        "id": e.get("id", ""),
        "summary": e.get("summary", "(no title)"),
        "description": (e.get("description") or "")[:500],
        "location": e.get("location", ""),
        "start": start.get("dateTime", start.get("date", "")),
        "end": end.get("dateTime", end.get("date", "")),
        "timezone": start.get("timeZone", ""),
        "status": e.get("status", ""),
        "visibility": e.get("visibility", "default"),
        "htmlLink": e.get("htmlLink", ""),
        "meet_link": meet_link,
        "organizer": e.get("organizer", {}).get("email", ""),
        "creator": e.get("creator", {}).get("email", ""),
        "attendees": [
            {
                "email": a.get("email", ""),
                "name": a.get("displayName", ""),
                "response": a.get("responseStatus", ""),
                "organizer": a.get("organizer", False),
            }
            for a in attendees
        ],
        "recurrence": e.get("recurrence", []),
        "color_id": e.get("colorId", ""),
        "reminders": e.get("reminders", {}),
    }


# --- Actions ---


def do_list_events(headers, calendar_id, inp):
    time_min = inp.get("time_min") or datetime.now(timezone.utc).isoformat()
    params = {
        "maxResults": min(int(inp.get("max_results", 10)), 50),
        "timeMin": time_min,
        "singleEvents": "true",
        "orderBy": "startTime",
    }
    if inp.get("time_max"):
        params["timeMax"] = inp["time_max"]
    if inp.get("query"):
        params["q"] = inp["query"]
    data = api_get(headers, f"calendars/{calendar_id}/events", params=params)
    events = [format_event(e) for e in data.get("items", [])]
    return {"events": events, "count": len(events)}


def do_get_event(headers, calendar_id, event_id):
    if not event_id:
        return {"error": "event_id is required for get_event"}
    e = api_get(headers, f"calendars/{calendar_id}/events/{event_id}")
    return format_event(e)


def do_create_event(headers, calendar_id, inp):
    if not inp.get("summary"):
        return {"error": "summary is required for create_event"}
    if not inp.get("start_time"):
        return {"error": "start_time is required for create_event"}

    tz = inp.get("timezone", "")
    body = {"summary": inp["summary"]}
    body.update(make_time_body(inp["start_time"], inp.get("end_time"), tz))

    if inp.get("description"):
        body["description"] = inp["description"]
    if inp.get("location"):
        body["location"] = inp["location"]

    attendees = parse_attendees(inp.get("attendees", ""))
    if attendees:
        body["attendees"] = attendees

    if inp.get("add_meet"):
        body["conferenceData"] = make_conference_data()

    if inp.get("recurrence"):
        rules = inp["recurrence"]
        body["recurrence"] = [rules] if isinstance(rules, str) else rules

    body["reminders"] = parse_reminders(inp.get("reminders", "default"))

    if inp.get("visibility") and inp["visibility"] != "default":
        body["visibility"] = inp["visibility"]
    if inp.get("color_id"):
        body["colorId"] = inp["color_id"]

    params = {"sendUpdates": inp.get("send_updates", "all")}
    if inp.get("add_meet"):
        params["conferenceDataVersion"] = 1

    data = api_post(headers, f"calendars/{calendar_id}/events", body, params=params)
    result = format_event(data)
    result["created"] = True
    return result


def do_update_event(headers, calendar_id, inp):
    event_id = inp.get("event_id", "")
    if not event_id:
        return {"error": "event_id is required for update_event"}

    # Fetch existing event to merge
    existing = api_get(headers, f"calendars/{calendar_id}/events/{event_id}")
    body = {}

    if inp.get("summary"):
        body["summary"] = inp["summary"]
    if inp.get("description") is not None:
        body["description"] = inp["description"]
    if inp.get("location") is not None:
        body["location"] = inp["location"]

    tz = inp.get("timezone", "")
    time_updates = make_time_body(inp.get("start_time"), inp.get("end_time"), tz)
    # For partial time updates, fill in the missing side from existing
    if "start" in time_updates and "end" not in time_updates:
        time_updates["end"] = existing.get("end", time_updates["start"])
    elif "end" in time_updates and "start" not in time_updates:
        time_updates["start"] = existing.get("start", time_updates["end"])
    body.update(time_updates)

    if inp.get("attendees"):
        new_attendees = parse_attendees(inp["attendees"])
        # Merge with existing attendees (don't remove existing ones)
        existing_emails = {a["email"] for a in existing.get("attendees", [])}
        merged = list(existing.get("attendees", []))
        for a in new_attendees:
            if a["email"] not in existing_emails:
                merged.append(a)
        body["attendees"] = merged

    if inp.get("add_meet") and not existing.get("conferenceData"):
        body["conferenceData"] = make_conference_data()

    if inp.get("recurrence"):
        rules = inp["recurrence"]
        body["recurrence"] = [rules] if isinstance(rules, str) else rules

    if inp.get("reminders"):
        body["reminders"] = parse_reminders(inp["reminders"])

    if inp.get("visibility") and inp["visibility"] != "default":
        body["visibility"] = inp["visibility"]
    if inp.get("color_id"):
        body["colorId"] = inp["color_id"]

    if not body:
        return {"error": "No fields to update"}

    params = {"sendUpdates": inp.get("send_updates", "all")}
    if inp.get("add_meet"):
        params["conferenceDataVersion"] = 1

    data = api_patch(headers, f"calendars/{calendar_id}/events/{event_id}", body, params=params)
    result = format_event(data)
    result["updated"] = True
    return result


def do_delete_event(headers, calendar_id, inp):
    event_id = inp.get("event_id", "")
    if not event_id:
        return {"error": "event_id is required for delete_event"}
    params = {"sendUpdates": inp.get("send_updates", "all")}
    api_delete(headers, f"calendars/{calendar_id}/events/{event_id}", params=params)
    return {"deleted": True, "event_id": event_id}


def do_quick_add(headers, calendar_id, text):
    if not text:
        return {"error": "text is required for quick_add"}
    with httpx.Client(timeout=15) as c:
        r = c.post(
            f"{BASE}/calendars/{calendar_id}/events/quickAdd",
            headers=headers,
            params={"text": text, "sendUpdates": "all"},
        )
        r.raise_for_status()
        data = r.json()
    result = format_event(data)
    result["created"] = True
    return result


def do_find_free_busy(headers, calendar_id, inp):
    time_min = inp.get("time_min")
    time_max = inp.get("time_max")
    if not time_min or not time_max:
        return {"error": "time_min and time_max are required for find_free_busy"}
    body = {
        "timeMin": time_min,
        "timeMax": time_max,
        "items": [{"id": calendar_id}],
    }
    with httpx.Client(timeout=15) as c:
        r = c.post(f"{BASE}/freeBusy", headers=headers, json=body)
        r.raise_for_status()
        data = r.json()
    cal_data = data.get("calendars", {}).get(calendar_id, {})
    busy_periods = cal_data.get("busy", [])
    return {
        "calendar_id": calendar_id,
        "time_min": time_min,
        "time_max": time_max,
        "busy": [
            {"start": b["start"], "end": b["end"]}
            for b in busy_periods
        ],
        "busy_count": len(busy_periods),
    }


def do_list_calendars(headers):
    data = api_get(headers, "users/me/calendarList")
    calendars = data.get("items", [])
    return {
        "calendars": [
            {
                "id": c.get("id", ""),
                "summary": c.get("summary", ""),
                "description": c.get("description", ""),
                "primary": c.get("primary", False),
                "access_role": c.get("accessRole", ""),
                "timezone": c.get("timeZone", ""),
                "color": c.get("backgroundColor", ""),
            }
            for c in calendars
        ],
        "count": len(calendars),
    }


# --- Main ---

try:
    creds_json = os.environ["GOOGLE_SERVICE_ACCOUNT_JSON"]
    calendar_id = os.environ.get("CALENDAR_ID", "primary")
    inp = json.loads(os.environ.get("INPUT_JSON", "{}"))
    action = inp.get("action", "")

    if inp.get("calendar_id"):
        calendar_id = inp["calendar_id"]

    token = get_access_token(creds_json)
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }

    if action == "list_events":
        result = do_list_events(headers, calendar_id, inp)
    elif action == "get_event":
        result = do_get_event(headers, calendar_id, inp.get("event_id", ""))
    elif action == "create_event":
        result = do_create_event(headers, calendar_id, inp)
    elif action == "update_event":
        result = do_update_event(headers, calendar_id, inp)
    elif action == "delete_event":
        result = do_delete_event(headers, calendar_id, inp)
    elif action == "quick_add":
        result = do_quick_add(headers, calendar_id, inp.get("text", ""))
    elif action == "find_free_busy":
        result = do_find_free_busy(headers, calendar_id, inp)
    elif action == "list_calendars":
        result = do_list_calendars(headers)
    else:
        result = {"error": f"Unknown action: {action}. Available: list_events, get_event, create_event, update_event, delete_event, quick_add, find_free_busy, list_calendars"}

    print(json.dumps(result))

except httpx.HTTPStatusError as e:
    detail = ""
    try:
        detail = e.response.json().get("error", {}).get("message", "")
    except Exception:
        detail = e.response.text[:200]
    print(json.dumps({"error": f"Google Calendar API error {e.response.status_code}: {detail}" if detail else f"Google Calendar API error {e.response.status_code}"}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
