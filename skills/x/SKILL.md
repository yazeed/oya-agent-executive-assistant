---
name: x
display_name: "X (Twitter)"
description: "Create tweets, reply, retweet, like, search, and manage your X (Twitter) account"
category: social
icon: twitter
skill_type: sandbox
catalog_type: platform
requirements: "httpx>=0.25"
resource_requirements:
  - env_var: X_ACCESS_TOKEN
    name: "X Access Token"
    description: "OAuth 2.0 access token (auto-provided by gateway connection)"
config_schema:
  properties:
    posting_rules:
      type: text
      label: "Posting Rules"
      description: "Rules for how the LLM should create tweets"
      placeholder: "- Keep tweets concise\n- Use relevant hashtags\n- Never post controversial content"
      group: rules
    safety_rules:
      type: text
      label: "Safety Rules"
      description: "Safety rules and constraints"
      placeholder: "- Always confirm with the user before tweeting\n- Never share confidential information"
      group: rules
tool_schema:
  name: x
  description: "Create tweets, reply, retweet, like, search, and manage your X (Twitter) account"
  parameters:
    type: object
    properties:
      action:
        type: "string"
        description: "Which operation to perform"
        enum: ['get_me', 'create_tweet', 'delete_tweet', 'reply', 'retweet', 'like', 'unlike', 'search', 'get_user', 'get_tweet', 'follow', 'get_user_tweets']
      text:
        type: "string"
        description: "Tweet text content -- for create_tweet, reply"
        default: ""
      tweet_id:
        type: "string"
        description: "Tweet ID -- for delete_tweet, reply, retweet, like, unlike, get_tweet"
        default: ""
      query:
        type: "string"
        description: "Search query -- for search"
        default: ""
      username:
        type: "string"
        description: "Username (without @) -- for get_user"
        default: ""
      target_user_id:
        type: "string"
        description: "User ID to follow -- for follow"
        default: ""
      user_id:
        type: "string"
        description: "User ID -- for get_user_tweets"
        default: ""
      max_results:
        type: "integer"
        description: "Max results for search and get_user_tweets (5-100)"
        default: 10
    required: [action]
---
# X (Twitter)

Create tweets, reply, retweet, like, search, and manage your X (Twitter) account.

## Profile
- **get_me** -- Get your X profile info (name, username, description, followers/following counts).

## Tweeting
- **create_tweet** -- Create a tweet. Provide `text`.
- **reply** -- Reply to a tweet. Provide `tweet_id` and `text`.
- **delete_tweet** -- Delete a tweet. Provide `tweet_id`.

## Engagement
- **retweet** -- Retweet a tweet. Provide `tweet_id`.
- **like** -- Like a tweet. Provide `tweet_id`.
- **unlike** -- Unlike a tweet. Provide `tweet_id`.

## Networking
- **follow** -- Follow a user. Provide `target_user_id` (numeric user ID, get it from `get_user` first).
- **get_user_tweets** -- Get a user's recent tweets. Provide `user_id` and optional `max_results` (5-100).

## Search & Lookup
- **search** -- Search recent tweets. Provide `query` and optional `max_results` (10-100).
- **get_user** -- Get a user's profile. Provide `username`.
- **get_tweet** -- Get a tweet by ID. Provide `tweet_id`.
