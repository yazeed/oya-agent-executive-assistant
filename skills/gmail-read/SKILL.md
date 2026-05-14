---
name: gmail-read
display_name: "Gmail Read"
description: "Read recent emails from Gmail inbox"
category: communication
icon: inbox
skill_type: sandbox
catalog_type: platform
requirements: "httpx>=0.25,google-auth>=2.0,requests>=2.20"
resource_requirements:
  - env_var: GMAIL_CREDENTIALS_JSON
    name: "Gmail Service Account JSON"
    description: "Google service account credentials JSON"
  - env_var: GMAIL_USER_EMAIL
    name: "Gmail User Email"
    description: "Email address to read from"
tool_schema:
  name: gmail_read
  description: "Read recent emails from Gmail inbox"
  parameters:
    type: object
    properties:
      max_results:
        type: "integer"
        description: "Number of emails to fetch (default 5)"
      query:
        type: "string"
        description: "Gmail search query (optional)"
---
# Gmail Read
Read recent emails from Gmail inbox
