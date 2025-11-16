# slack-bot-cli

a terminal UI for browsing Slack channels and sending messages as a bot.

## Installation & Setup

### 1. Create a Slack Application

1. Go to the [Slack App Directory](https://api.slack.com/apps)
2. Click **Create New App** → **From an app manifest**
3. Select your workspace
4. Copy the manifest from [manifest.json](https://raw.githubusercontent.com/rudy3333/slack-bot-cli/refs/heads/main/manifest.json) and paste it into the form
5. Adjust the manifest as needed for your use case
6. Review and create the app

### 2. Get Your Tokens

After creating the app:

1. Go to **OAuth & Permissions** in the left sidebar
2. Under **Bot Token Scopes**, verify the required scopes are present (the manifest should have added them)
3. Copy the **Bot User OAuth Token** (starts with `xoxb-`)
4. Go to **App-Level Tokens** and copy your **App Token** (starts with `xapp-`)
   - If you don't have one, create a new token with `connections:write` scope

### 3. Install the App to Your Workspace

1. In **Settings** → **Install App**, click **Install to Workspace**
2. Review and authorize the requested permissions

### 4. Set Environment Variables

Create a `.env` file in the project root:

```env
SLACK_BOT_TOKEN=xoxb-your-token-here
SLACK_APP_TOKEN=xapp-your-token-here
```


### 5. Install Python Dependencies

Ensure you have Python 3.8+ installed, then:

```bash
python3 -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 6. Run the Application

```bash
python3 cli.py
```
