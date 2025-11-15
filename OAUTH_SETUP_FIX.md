# Fixing OAuth "redirect_uri_mismatch" Error

If you're getting `Error 400: redirect_uri_mismatch`, here's how to fix it:

## Option 1: Fix OAuth Credentials Configuration (Recommended)

The issue is that your OAuth credentials need to be configured correctly for desktop applications.

### Steps:

1. **Go to Google Cloud Console** → [Credentials](https://console.cloud.google.com/apis/credentials)

2. **Delete the existing OAuth client** (the one you just created)

3. **Create NEW OAuth client ID**:
   - Application type: **Desktop app** (NOT Web application!)
   - Name: "Gmail Invoice Extractor"
   - Click "Create"

4. **Download the JSON** and save as `credentials.json`

5. **Run the token script again**:
   ```bash
   uv run python get_gmail_token.py --credentials credentials.json
   ```

### Why This Happens

- **Desktop app** credentials automatically include `http://localhost` as a valid redirect URI
- **Web app** credentials require you to manually specify redirect URIs
- The script uses a local server, which needs `http://localhost:PORT` to be allowed

## Option 2: Use Console Flow (Fallback)

If Option 1 doesn't work, use the console-based flow (copy-paste method):

```bash
uv run python get_gmail_token.py --credentials credentials.json --console
```

This will:
1. Give you a URL to visit in your browser
2. You sign in and grant permissions
3. Google gives you a code
4. You paste the code back into the terminal

## Option 3: Manually Configure Redirect URIs

If you want to keep using "Web application" type:

1. Edit your OAuth client in Google Cloud Console
2. Add these **Authorized redirect URIs**:
   ```
   http://localhost
   http://localhost:8080
   http://localhost:8090
   http://127.0.0.1
   http://127.0.0.1:8080
   http://127.0.0.1:8090
   ```
3. Save and wait ~5 minutes for changes to propagate
4. Try again

## Verify Your Setup

After fixing, run:
```bash
# Should work without errors
uv run python get_gmail_token.py --credentials credentials.json

# Export the token
export GMAIL_ACCESS_TOKEN='...'  # From script output
export GMAIL_EMAIL='your@gmail.com'

# Test IMAP connection
uv run python imap_main.py
```

## Quick Checklist

- [ ] Used **Desktop app** (not Web app) for OAuth credentials
- [ ] Downloaded fresh `credentials.json`
- [ ] Deleted any old `token.pickle` file
- [ ] Re-ran `get_gmail_token.py`
- [ ] Saw browser open successfully
- [ ] Granted permissions in browser
- [ ] Got token in output

If you're still stuck, try the `--console` flag for manual copy-paste flow.
