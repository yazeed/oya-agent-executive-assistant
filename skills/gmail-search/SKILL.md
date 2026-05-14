---
name: gmail-search
display_name: "Gmail Search"
description: "Search emails in Gmail with a query"
category: communication
icon: search
skill_type: sandbox
catalog_type: platform
requirements: "httpx>=0.25,google-auth>=2.0,requests>=2.20"
resource_requirements:
  - env_var: GMAIL_CREDENTIALS_JSON
    name: "Gmail Service Account JSON"
    description: "Google service account credentials JSON"
  - env_var: GMAIL_USER_EMAIL
    name: "Gmail User Email"
    description: "Email address to search"
tool_schema:
  name: gmail_search
  description: "Search emails in Gmail"
  parameters:
    type: object
    properties:
      query:
        type: "string"
        description: "Gmail search query (e.g. 'from:john subject:meeting')"
      max_results:
        type: "integer"
        description: "Max results (default 10)"
    required: [query]
---
# Gmail Search
Search emails in Gmail with a query
