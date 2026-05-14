import os
import json
import re
import httpx

BASE = "https://api.x.com/2"


def _md_to_plain(text):
    """Convert Markdown to plain text. X/Twitter has no markup support."""
    if not text:
        return text
    s = text
    # Remove horizontal rules
    s = re.sub(r'^---+\s*$', '', s, flags=re.MULTILINE)
    # Headers → plain text (strip # prefix)
    s = re.sub(r'^#{1,6}\s+', '', s, flags=re.MULTILINE)
    # Bold+italic ***text*** or ___text___
    s = re.sub(r'\*{3}(.+?)\*{3}', r'\1', s)
    s = re.sub(r'_{3}(.+?)_{3}', r'\1', s)
    # Bold **text** or __text__
    s = re.sub(r'\*{2}(.+?)\*{2}', r'\1', s)
    s = re.sub(r'_{2}(.+?)_{2}', r'\1', s)
    # Italic *text* or _text_
    s = re.sub(r'(?<!\w)\*(.+?)\*(?!\w)', r'\1', s)
    s = re.sub(r'(?<!\w)_(.+?)_(?!\w)', r'\1', s)
    # Strikethrough ~~text~~
    s = re.sub(r'~~(.+?)~~', r'\1', s)
    # Inline code `text`
    s = re.sub(r'`([^`]+)`', r'\1', s)
    # Links [text](url) → text (url)
    s = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'\1 (\2)', s)
    # Bullet lists: * or - at start → •
    s = re.sub(r'^[\*\-]\s+', '• ', s, flags=re.MULTILINE)
    # Collapse 3+ consecutive blank lines to 2
    s = re.sub(r'\n{3,}', '\n\n', s)
    return s.strip()


def get_access_token():
    return os.environ.get("X_ACCESS_TOKEN", "")


def api_get(headers, path, params=None, timeout=15):
    with httpx.Client(timeout=timeout) as c:
        r = c.get(f"{BASE}/{path}", headers=headers, params=params)
        r.raise_for_status()
        return r.json()


def api_post(headers, path, body, timeout=15):
    with httpx.Client(timeout=timeout) as c:
        r = c.post(f"{BASE}/{path}", headers=headers, json=body)
        r.raise_for_status()
        return r.json() if r.content else {}


def api_delete(headers, path, timeout=15):
    with httpx.Client(timeout=timeout) as c:
        r = c.delete(f"{BASE}/{path}", headers=headers)
        r.raise_for_status()
        return r.json() if r.content else {}


# --- Actions ---


def do_get_me(headers):
    data = api_get(headers, "users/me", params={
        "user.fields": "id,name,username,description,public_metrics,profile_image_url"
    })
    user = data.get("data", {})
    metrics = user.get("public_metrics", {})
    return {
        "id": user.get("id", ""),
        "name": user.get("name", ""),
        "username": user.get("username", ""),
        "description": user.get("description", ""),
        "followers_count": metrics.get("followers_count", 0),
        "following_count": metrics.get("following_count", 0),
        "tweet_count": metrics.get("tweet_count", 0),
        "profile_image_url": user.get("profile_image_url", ""),
    }


def do_create_tweet(headers, text):
    if not text or not text.strip():
        return {"error": "text is required for create_tweet"}
    data = api_post(headers, "tweets", {"text": _md_to_plain(text)})
    tweet = data.get("data", {})
    return {
        "tweet_id": tweet.get("id", ""),
        "text": tweet.get("text", ""),
        "created": True,
    }


def do_reply(headers, tweet_id, text):
    if not tweet_id or not tweet_id.strip():
        return {"error": "tweet_id is required for reply"}
    if not text or not text.strip():
        return {"error": "text is required for reply"}
    data = api_post(headers, "tweets", {
        "text": _md_to_plain(text),
        "reply": {"in_reply_to_tweet_id": tweet_id.strip()},
    })
    tweet = data.get("data", {})
    return {
        "tweet_id": tweet.get("id", ""),
        "text": tweet.get("text", ""),
        "replied_to": tweet_id.strip(),
        "created": True,
    }


def do_delete_tweet(headers, tweet_id):
    if not tweet_id or not tweet_id.strip():
        return {"error": "tweet_id is required for delete_tweet"}
    data = api_delete(headers, f"tweets/{tweet_id.strip()}")
    return {"tweet_id": tweet_id.strip(), "deleted": data.get("data", {}).get("deleted", True)}


def do_retweet(headers, user_id, tweet_id):
    if not tweet_id or not tweet_id.strip():
        return {"error": "tweet_id is required for retweet"}
    data = api_post(headers, f"users/{user_id}/retweets", {"tweet_id": tweet_id.strip()})
    return {"tweet_id": tweet_id.strip(), "retweeted": data.get("data", {}).get("retweeted", True)}


def do_like(headers, user_id, tweet_id):
    if not tweet_id or not tweet_id.strip():
        return {"error": "tweet_id is required for like"}
    data = api_post(headers, f"users/{user_id}/likes", {"tweet_id": tweet_id.strip()})
    return {"tweet_id": tweet_id.strip(), "liked": data.get("data", {}).get("liked", True)}


def do_unlike(headers, user_id, tweet_id):
    if not tweet_id or not tweet_id.strip():
        return {"error": "tweet_id is required for unlike"}
    api_delete(headers, f"users/{user_id}/likes/{tweet_id.strip()}")
    return {"tweet_id": tweet_id.strip(), "unliked": True}


def do_follow(headers, user_id, target_user_id):
    if not target_user_id or not target_user_id.strip():
        return {"error": "target_user_id is required for follow"}
    data = api_post(headers, f"users/{user_id}/following", {"target_user_id": target_user_id.strip()})
    return {"target_user_id": target_user_id.strip(), "following": data.get("data", {}).get("following", True)}


def do_get_user_tweets(headers, user_id, max_results=10):
    if not user_id or not user_id.strip():
        return {"error": "user_id is required for get_user_tweets"}
    max_results = max(5, min(100, int(max_results or 10)))
    data = api_get(headers, f"users/{user_id.strip()}/tweets", params={
        "max_results": max_results,
        "tweet.fields": "id,text,author_id,created_at,public_metrics",
    })
    tweets = data.get("data", [])
    return {
        "user_id": user_id.strip(),
        "tweets": [
            {
                "tweet_id": t["id"],
                "text": t.get("text", ""),
                "created_at": t.get("created_at", ""),
                "metrics": t.get("public_metrics", {}),
            }
            for t in tweets
        ],
        "count": len(tweets),
    }


def do_search(headers, query, max_results=10):
    if not query or not query.strip():
        return {"error": "query is required for search"}
    max_results = max(10, min(100, int(max_results or 10)))
    data = api_get(headers, "tweets/search/recent", params={
        "query": query.strip(),
        "max_results": max_results,
        "tweet.fields": "id,text,author_id,created_at,public_metrics,reply_settings",
    })
    tweets = data.get("data", []) or []
    return {
        "tweets": [
            {
                "tweet_id": t.get("id", ""),
                "text": t.get("text", ""),
                "author_id": t.get("author_id", ""),
                "created_at": t.get("created_at", ""),
                "metrics": t.get("public_metrics", {}),
                "reply_settings": t.get("reply_settings", "everyone"),
            }
            for t in tweets
        ],
        "result_count": data.get("meta", {}).get("result_count", len(tweets)),
    }


def do_get_user(headers, username):
    if not username or not username.strip():
        return {"error": "username is required for get_user"}
    username = username.strip().lstrip("@")
    data = api_get(headers, f"users/by/username/{username}", params={
        "user.fields": "id,name,username,description,public_metrics,profile_image_url"
    })
    user = data.get("data", {})
    metrics = user.get("public_metrics", {})
    return {
        "user_id": user.get("id", ""),
        "name": user.get("name", ""),
        "username": user.get("username", ""),
        "description": user.get("description", ""),
        "followers_count": metrics.get("followers_count", 0),
        "following_count": metrics.get("following_count", 0),
        "tweet_count": metrics.get("tweet_count", 0),
    }


def do_get_tweet(headers, tweet_id):
    if not tweet_id or not tweet_id.strip():
        return {"error": "tweet_id is required for get_tweet"}
    data = api_get(headers, f"tweets/{tweet_id.strip()}", params={
        "tweet.fields": "id,text,author_id,created_at,public_metrics,reply_settings",
    })
    tweet = data.get("data", {})
    return {
        "tweet_id": tweet.get("id", ""),
        "text": tweet.get("text", ""),
        "author_id": tweet.get("author_id", ""),
        "created_at": tweet.get("created_at", ""),
        "metrics": tweet.get("public_metrics", {}),
        "reply_settings": tweet.get("reply_settings", "everyone"),
    }


# --- Main ---

try:
    access_token = get_access_token()
    if not access_token:
        raise ValueError("No X access token available. Please reconnect the X gateway.")
    inp = json.loads(os.environ.get("INPUT_JSON", "{}"))
    action = inp.get("action", "")

    headers = {
        "Authorization": f"Bearer {access_token}",
        "Content-Type": "application/json",
    }

    if action == "get_me":
        result = do_get_me(headers)
    elif action == "create_tweet":
        result = do_create_tweet(headers, inp.get("text", ""))
    elif action == "reply":
        result = do_reply(headers, inp.get("tweet_id", ""), inp.get("text", ""))
    elif action == "delete_tweet":
        result = do_delete_tweet(headers, inp.get("tweet_id", ""))
    elif action == "retweet":
        me = do_get_me(headers)
        result = do_retweet(headers, me["id"], inp.get("tweet_id", ""))
    elif action == "like":
        me = do_get_me(headers)
        result = do_like(headers, me["id"], inp.get("tweet_id", ""))
    elif action == "unlike":
        me = do_get_me(headers)
        result = do_unlike(headers, me["id"], inp.get("tweet_id", ""))
    elif action == "search":
        result = do_search(headers, inp.get("query", ""), inp.get("max_results", 10))
    elif action == "get_user":
        result = do_get_user(headers, inp.get("username", ""))
    elif action == "get_tweet":
        result = do_get_tweet(headers, inp.get("tweet_id", ""))
    elif action == "follow":
        me = do_get_me(headers)
        result = do_follow(headers, me["id"], inp.get("target_user_id", ""))
    elif action == "get_user_tweets":
        result = do_get_user_tweets(headers, inp.get("user_id", ""), inp.get("max_results", 10))
    else:
        result = {"error": f"Unknown action: {action}. Available: get_me, create_tweet, reply, delete_tweet, retweet, like, unlike, search, get_user, get_tweet, follow, get_user_tweets"}

    print(json.dumps(result))

except httpx.HTTPStatusError as e:
    status = e.response.status_code
    detail = ""
    try:
        detail = e.response.json().get("detail", "") or str(e.response.json())
    except Exception:
        detail = e.response.text[:200]
    if status == 403:
        detail_lower = detail.lower()
        if "reply" in detail_lower and ("restrict" in detail_lower or "control" in detail_lower or "setting" in detail_lower or "not allowed" in detail_lower):
            msg = f"Reply restricted: this tweet's author has limited who can reply (followers or mentioned users only). Skip this post and try another. Detail: {detail}"
        else:
            hint = (
                "This usually means the access token has been revoked or the X account's API permissions have changed. "
                "Common cause: the same X account is connected to multiple agents, and another agent refreshed the token "
                "(X uses rotating tokens — only the last refresh is valid). "
                "Fix: go to the agent's Gateways settings and reconnect the X account."
            )
            msg = f"X API error 403 (Forbidden): {detail}. {hint}" if detail else f"X API error 403 (Forbidden). {hint}"
    elif status == 429:
        msg = f"X API rate limit hit (429). Wait before retrying. Detail: {detail}" if detail else "X API rate limit hit (429). Wait before retrying."
    else:
        msg = f"X API error {status}: {detail}" if detail else f"X API error {status}"
    print(json.dumps({"error": msg}))
except Exception as e:
    print(json.dumps({"error": str(e)}))
