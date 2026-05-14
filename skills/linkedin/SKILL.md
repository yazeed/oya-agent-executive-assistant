---
name: linkedin
display_name: "LinkedIn"
description: "Create posts, comment, react, read feed, and send connection requests on LinkedIn via the browser extension."
category: social
icon: linkedin
skill_type: browser
catalog_type: platform
---
# LinkedIn (Browser-based)

Engage with LinkedIn through the browser extension. No API or OAuth required — you must be logged into LinkedIn in your browser.

## Setup

1. Add the **Browser** gateway to your agent (Gateways → Add Browser).
2. Install the Oya extension and bind it to this agent.
3. Open LinkedIn (linkedin.com) in a browser tab and stay logged in.

## Available Tools

These tools are injected automatically when the Browser gateway is connected and the extension is bound:

- **linkedin_create_post** — Create a new LinkedIn post. Opens the composer, types text, and publishes. Provide `text`.
- **linkedin_get_feed** — Read the LinkedIn feed. Returns posts with author, text, and URL. Use `count` (default 5).
- **linkedin_comment** — Comment on a post. Provide `post_url` and `text`.
- **linkedin_react** — React to a post (like, celebrate, support, etc.). Provide `post_url` and `reaction`.
- **linkedin_send_connection** — Send a connection request to a profile. Provide `profile_url` and optional `message`.

## Creating Posts

Use **linkedin_create_post** with the `text` parameter. The tool handles the full flow: opens the composer modal, types the text, and clicks Post.

## Reading the Feed

Use **linkedin_get_feed** for structured feed reading, or generic **browser_navigate** + **browser_analyze_page** for custom extraction.
