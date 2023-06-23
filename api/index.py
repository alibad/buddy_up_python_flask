from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from slack_sdk.errors import SlackApiError
import json
import os
from dotenv import load_dotenv
from urllib.parse import unquote_plus

# Load environment variables
load_dotenv('.env.development.local')

# Setup the WebClient and the SignatureVerifier
SLACK_BOT_TOKEN = os.getenv("SLACK_BOT_TOKEN")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

web_client = WebClient(token=SLACK_BOT_TOKEN)
signature_verifier = SignatureVerifier(SLACK_SIGNING_SECRET)

if SLACK_BOT_TOKEN is None or SLACK_SIGNING_SECRET is None:
    print("Environment variables not set")
else:
    print("Environment variables are set")

# Create a new Flask web server
app = Flask(__name__)

# The route for the Slack events
@app.route('/api/slack/events', methods=['POST'])
def slack_events():
    data = request.get_data().decode('utf-8')

    # parse URL-encoded data
    payload = unquote_plus(data)

    if payload.startswith('payload='):
        payload = payload[len('payload='):]

    print(f"Received data: {payload}")

    event = json.loads(payload)

    print(f"Received event: {event}")

    if not signature_verifier.is_valid_request(data, request.headers):
        return jsonify({'status': 'invalid_request'}), 403

    if event is not None:
        print(f"Event type: {event['type']}")

        if event['type'] == 'shortcut' and event['callback_id'] == 'buddy_up':

            user_id = event['user']['id']

            print(f"Posting a message to: {event}")

            try:
                # Open a modal
                view_payload = {
                    "trigger_id": event['trigger_id'],
                    "view": {
                        "type": "modal",
                        "callback_id": "buddy_up_modal",
                        "title": {
                            "type": "plain_text",
                            "text": "Buddy Up"
                        },
                        "blocks": [
                            {
                                "type": "input",
                                "block_id": "channel_input",
                                "label": {
                                    "type": "plain_text",
                                    "text": "Select a channel"
                                },
                                "element": {
                                    "type": "conversations_select",
                                    "action_id": "channel_select",
                                    "placeholder": {
                                        "type": "plain_text",
                                        "text": "Select a channel"
                                    }
                                }
                            }
                        ],
                        "submit": {
                            "type": "plain_text",
                            "text": "Submit"
                        }
                    }
                }

                response = web_client.views_open(**view_payload)
                print(f"Response: {response}")

                return jsonify({'status': 'ok'}), 200
            except SlackApiError as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        elif event['type'] == 'view_submission':
            user_id = event['user']['id']
            channel_id = event['view']['state']['values']['channel_input']['channel_select']['selected_conversation']

            try:
                web_client.chat_postMessage(
                    channel=channel_id,
                    text=f"Hello! This message is sent from <@{user_id}>."
                )
                return jsonify({'status': 'ok'}), 200
            except SlackApiError as e:
                return jsonify({"status": "error", "message": str(e)}), 500
        else:
            return jsonify({"status": "error", "message": "unknown_event"}), 400
    else:
        return jsonify({"status": "error", "message": "missing_payload"}), 400

if __name__ == "__main__":
    app.run(port=3000)
