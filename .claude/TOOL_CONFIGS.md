# Tool Configuration Files

## email_list_tool.py

**Config File:** `data/email_tool_config.json`

**Schema:**
```json
{
  "sender_email": "srini@unmistakablemedia.com",
  "sender_name": "Srini Rao",
  "reply_to_email": "srini@unmistakablemedia.com",
  "reply_to_name": "Srini Rao",
  "rate_limits": {
    "max_emails_per_minute": 20,
    "max_emails_per_hour": 500,
    "max_emails_per_day": 5000
  },
  "unsubscribe_url_base": "http://localhost:5001/unsubscribe"
}
```

**Fields:**
- `sender_email`: From address for all outgoing emails
- `sender_name`: Display name for sender
- `reply_to_email`: Reply-to address
- `reply_to_name`: Reply-to display name
- `rate_limits`: Email sending limits to prevent API throttling
- `unsubscribe_url_base`: Base URL for unsubscribe links (email param appended automatically)

**Usage:**
All hardcoded values moved to config file. Tool loads config via `load_config()` function with fallback defaults if file doesn't exist.
