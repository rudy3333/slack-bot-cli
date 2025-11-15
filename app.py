import os
from dotenv import load_dotenv
from slack_bolt import App
from slack_bolt.adapter.socket_mode import SocketModeHandler

load_dotenv()

# This sample slack application uses SocketMode
# For the companion getting started setup guide, 
# see: https://slack.dev/bolt-python/tutorial/getting-started 

# Initializes your app with your bot token
app = App(token=os.environ.get("SLACK_BOT_TOKEN"))


# Listens to incoming messages that contain "hello"
@app.message("hello")
def message_hello(message, say):
    # say() sends a message to the channel where the event was triggered
    say(
        blocks=[
            {
                "type": "section",
                "text": {"type": "mrkdwn", "text": f"Hey there <@{message['user']}>!"},
                "accessory": {
                    "type": "button",
                    "text": {"type": "plain_text", "text": "Click Me"},
                    "action_id": "button_click",
                },
            }
        ],
        text=f"Hey there <@{message['user']}>!",
    )


@app.action("button_click")
def action_button_click(body, ack, say):
    # Acknowledge the action
    ack()
    say(f"<@{body['user']['id']}> clicked the button")


def get_all_public_channels():
    channels = []
    cursor = None
    
    while True:
        try:
            result = app.client.conversations_list(
                types="public_channel",
                cursor=cursor,
                limit=200
            )
            
            if not result["ok"]:
                print(f"Error fetching channels: {result.get('error', 'Unknown error')}")
                break
            
            channels.extend(result["channels"])
            
            cursor = result.get("response_metadata", {}).get("next_cursor")
            if not cursor:
                break
                
        except Exception as e:
            print(f"Error getting channels: {e}")
            break
    
    return channels


# Start your app
if __name__ == "__main__":
    public_channels = get_all_public_channels()
    print(f"Found {len(public_channels)} public channels")
    for channel in public_channels:
        print(f"  - {channel['name']} ({channel['id']})")
    
    print(public_channels)
    channel_id = "C09T0J1578V"
    try:
        result = app.client.conversations_join(channel=channel_id)
        if result["ok"]:
            print(f"Successfully joined channel {channel_id}")
        else:
            print(f"Failed to join channel {channel_id}: {result.get('error', 'Unknown error')}")
    except Exception as e:
        print(f"Error joining channel {channel_id}: {e}")
    
    SocketModeHandler(app, os.environ["SLACK_APP_TOKEN"]).start()
