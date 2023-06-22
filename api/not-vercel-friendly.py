from slack_bolt import App, Ack
from dotenv import load_dotenv
import os

# Load environment variables
load_dotenv('.env.development.local')

# Setup the Slack Bolt App
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

if SLACK_BOT_TOKEN is None or SLACK_SIGNING_SECRET is None:
    print("Environment variables not set")
else:
    print("Environment variables are set")

app = App(token=SLACK_BOT_TOKEN, signing_secret=SLACK_SIGNING_SECRET)

@app.shortcut("buddy_up")
def buddy_up(ack: Ack, client, shortcut):
    ack()

    user_id = shortcut['user']['id']

    try:
        client.chat_postMessage(
            channel=user_id,
            text=f"Hello <@{user_id}>! You invoked the Buddy Up shortcut."
        )
    except Exception as e:
        print(f"Error posting message: {e}")

# Start your app
if __name__ == "__main__":
    app.start(port=3000)
