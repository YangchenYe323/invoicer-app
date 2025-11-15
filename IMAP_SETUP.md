# Gmail IMAP Setup Guide

This guide explains how to set up Gmail IMAP access with OAuth2 for the invoice extraction pipeline.

## Overview

The `imap_main.py` script connects to Gmail via IMAP using OAuth2 authentication and fetches email metadata. This is useful for:
- Listing recent emails
- Finding invoices to process
- Testing the pipeline with real Gmail data

## Prerequisites

1. **Google Cloud Project** with Gmail API enabled
2. **OAuth 2.0 Credentials** (Desktop application type)
3. **Python dependencies** (already installed via `uv`)

## Setup Steps

### 1. Create Google Cloud Project

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project (or select existing)
3. Enable the **Gmail API**:
   - Navigate to "APIs & Services" → "Library"
   - Search for "Gmail API"
   - Click "Enable"

### 2. Create OAuth 2.0 Credentials

1. Go to "APIs & Services" → "Credentials"
2. Click "Create Credentials" → "OAuth client ID"
3. Configure OAuth consent screen if prompted:
   - User Type: External (for testing)
   - Add your email as a test user
4. Application type: **Desktop application**
5. Name: "Invoice Extractor IMAP Client" (or any name)
6. Click "Create"
7. **Download the JSON file** (credentials.json)

### 3. Get OAuth Token

Use the helper script to obtain an access token:

```bash
# Get token (will open browser for OAuth flow)
uv run python get_gmail_token.py --credentials credentials.json

# This will save token to token.pickle for reuse
```

The script will:
- Open your browser
- Ask you to sign in to Gmail
- Request permission to access your email
- Save the token for future use

### 4. Export Environment Variables

```bash
# Copy the token from the script output
export GMAIL_ACCESS_TOKEN='ya29.a0AfB_by...'
export GMAIL_EMAIL='your-email@gmail.com'
```

### 5. Run IMAP Fetcher

```bash
# Fetch metadata for last 1000 emails
uv run python imap_main.py
```

## What It Does

The `imap_main.py` script will:

1. **Connect** to Gmail IMAP using OAuth2
2. **Fetch metadata** for the last 1000 emails:
   - Subject
   - From address
   - Date
   - Size in bytes
   - Whether it has attachments
   - Message ID / UID
3. **Display summary**:
   - Total emails
   - Total size
   - Attachment statistics
   - Size distribution
   - Recent 20 emails preview

## Example Output

```
Connecting to Gmail IMAP as you@gmail.com...
Successfully authenticated!

Selecting mailbox: INBOX
Total messages in INBOX: 15234
Fetching metadata for 1000 messages...
  Processed 100/1000 messages...
  Processed 200/1000 messages...
  ...

================================================================================
EMAIL METADATA SUMMARY
================================================================================
Total emails fetched: 1000
Total size: 156.34 MB
Average size: 156.34 KB
Emails with attachments: 127 (12.7%)

Size distribution:
  Min: 1.23 KB
  P50: 45.67 KB
  P90: 234.56 KB
  Max: 5.12 MB

================================================================================
RECENT EMAILS (Last 20)
================================================================================

📎 UID: 12345
   From: vendor@example.com
   Subject: Invoice #12345 - Your monthly subscription
   Date: Mon, 15 Nov 2025 10:30:00 -0800
   Size: 234.5 KB
```

## Token Management

### Token Expiration

Access tokens expire after ~1 hour. Options:

1. **Re-run get_gmail_token.py**: It will automatically refresh if refresh token is available
2. **Use refresh token**: Implement automatic refresh in your service
3. **Service account**: For production, use a service account instead

### Storing Tokens Securely

**For development**:
- Keep `credentials.json` and `token.pickle` out of git (already in .gitignore)
- Use environment variables for tokens

**For production**:
- Store tokens in secrets manager (AWS Secrets Manager, Google Secret Manager, etc.)
- Use service accounts with domain-wide delegation
- Implement automatic token refresh

## Next Steps

After verifying IMAP access works:

1. **Integrate with pipeline**: Pass email bytes to `InvoiceExtractionPipeline`
2. **Filter emails**: Only fetch potential invoices (by subject, sender, etc.)
3. **Incremental sync**: Track last processed UID, only fetch new emails
4. **Background job**: Run periodically to check for new invoices

## Troubleshooting

### Authentication Failed

- Check that Gmail API is enabled in your project
- Verify token hasn't expired
- Make sure you're using the correct email address
- Try regenerating the token

### "Less secure app" Error

- OAuth2 is the modern approach (not "less secure apps")
- Make sure you're using OAuth2, not app passwords

### Rate Limits

- Gmail IMAP has rate limits
- For production, implement exponential backoff
- Consider using Gmail API REST instead of IMAP for better rate limits

## Security Notes

- **Never commit** `credentials.json` or `token.pickle` to git
- **Rotate tokens** periodically
- **Limit scopes** to only what you need (we use full gmail access for IMAP)
- **Use service accounts** for production deployments
