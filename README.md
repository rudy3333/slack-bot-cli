# slack-bot-cli

terminal UI for browsing slack channels and sending messages as a bot.


## setup

### 1. create a slack application

create a [slack application](https://api.slack.com/apps) using the following [manifest.json](https://raw.githubusercontent.com/rudy3333/slack-bot-cli/refs/heads/main/manifest.json) file adjust to your liking

### 2. environment variables

create a `.env` file:

```
SLACK_BOT_TOKEN=xoxb-...
SLACK_APP_TOKEN=xapp-...
```

### 2. install dependencies

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 3. run

```bash
python3 cli.py
```
