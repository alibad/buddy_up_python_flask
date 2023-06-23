from flask import Flask, request, jsonify
from slack_sdk import WebClient
from slack_sdk.signature import SignatureVerifier
from slack_sdk.errors import SlackApiError
import json
import os
from dotenv import load_dotenv
from urllib.parse import unquote_plus

# Global dictionary for storing channel mappings
channel_mappings = {}

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

def match_members_in_channel(channel: str, client: WebClient):
    try:
        print('Triggering matching logic for Channel ID: ' + channel)

        response = client.conversations_members(channel=channel)
        members = response.data['members']

        profiles = []
        for member_id in members:
            profile_response = client.users_profile_get(user=member_id)
            profile = profile_response.data['profile']
            if not profile.get('bot_id'):
                profiles.append({
                    'id': member_id,
                    'tzOffset': profile.get('tz_offset'),
                    'name': profile.get('real_name'),
                })

        print(str(len(profiles)) + ' user profiles found.')

        profiles.sort(key=lambda p: p['tzOffset'] if p['tzOffset'] is not None else 0)

        output_message = ''
        while len(profiles) > 1:
            member1 = profiles.pop(0)
            member2 = profiles.pop()

            if member1 and member2:
                output_message += f"* <@{member1['id']}> matched with <@{member2['id']}>. <@{member1['id']}>, you are in charge of scheduling the 1-1.\n"

        if len(profiles) == 1:
            member = profiles[0]
            output_message += f"* <@{member['id']}> couldn't be paired with anyone.\n"

        print('Sending matching message to Slack...')

        client.chat_postMessage(
            channel=channel,
            text=output_message
        )
    except Exception as e:
        print('Error matching members:', str(e))


@app.route('/api/slack/commands', methods=['POST'])
def handle_commands():
    if not signature_verifier.is_valid_request(request.get_data().decode('utf-8'), request.headers):
        return jsonify({'status': 'invalid_request'}), 403

    command = request.form
    command_text = command.get('text')
    command_name = command.get('command')
    channel_id = command.get('channel_id')

    if command_name == '/buddy_up':
        try:
            match_members_in_channel(channel_id, web_client)
            return jsonify({'status': 'ok'}), 200
        except Exception as e:
            return jsonify({"status": "error", "message": str(e)}), 500
    else:
        return jsonify({"status": "error", "message": "unknown_command"}), 400

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

    if event['type'] == 'url_verification':
        return jsonify({"challenge": event['challenge']}), 200

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
            if event['view']['callback_id'] == 'buddy_up':
                workflow_step_id = event['workflow_step']['step_id']
                workflow_step_edit_id = event['workflow_step']['workflow_step_edit_id']
                selected_channel = event['view']['state']['values']['channel_input']['channel_select']['selected_conversation']

                print(f"workflow_step_id: {workflow_step_id}")
                print(f"selected_channel: {selected_channel}")

                # Save the selected channel to Vercel KV
                # kv.set(workflow_step_id, selected_channel)
                channel_mappings[workflow_step_id] = selected_channel

                web_client.workflows_updateStep(workflow_step_edit_id=workflow_step_edit_id, inputs={"channel": {"value": selected_channel}}, outputs=[{"name": "message", "type": "text", "label": "Saved Workflow + Channel Link"}])

                return jsonify({'status': 'ok'}), 200
            else:
                channel_id = event['view']['state']['values']['channel_input']['channel_select']['selected_conversation']

                try:
                    match_members_in_channel(channel_id, web_client)
                    return jsonify({'status': 'ok'}), 200
                except SlackApiError as e:
                    return jsonify({"status": "error", "message": str(e)}), 500
            
        elif event['type'] == 'workflow_step_edit':
            trigger_id = event['trigger_id']
            workflow_step = event['workflow_step']

            view = {
                "type": "workflow_step",
                "callback_id": "buddy_up_workflow_step",
                "blocks": [{
                    "type": "input",
                    "block_id": "channel_input",
                    "label": {
                        "type": "plain_text",
                        "text": "Channel",
                        "emoji": True
                    },
                    "element": {
                        "type": "conversations_select",
                        "action_id": "channel_select",
                        "placeholder": {"type": "plain_text", "text": "Select a channel", "emoji": True}
                    }
                }]
            }

            try:
                web_client.views_open(
                    trigger_id=trigger_id,
                    view=view
                )

                return jsonify({'status': 'ok'}), 200
            except SlackApiError as e:
                
                print(f"e: {e}")
                
                return jsonify({'error': e.response['error']}), 500

        elif event['type'] == 'event_callback' and event['event']['type'] == 'workflow_step_execute':
            workflow_step_id = event['event']['workflow_step']['step_id']
            workflow_step_execute_id = event['event']['workflow_step']['workflow_step_execute_id']
            print(f"workflow_step_id: {workflow_step_id}")

            # Retrieve the selected channel from Vercel KV
            # selected_channel = kv.get(workflow_step_id)
            selected_channel = channel_mappings.get(workflow_step_id)
            print(f"selected_channel: {selected_channel}")

            match_members_in_channel(selected_channel, web_client)

            web_client.workflows_stepCompleted(workflow_step_execute_id=workflow_step_execute_id, outputs={"message": {"value": "Pairs have been matched"}})

            return jsonify({'status': 'ok'}), 200
        else:
            return jsonify({"status": "error", "message": "unknown_event"}), 400
    else:
        return jsonify({"status": "error", "message": "missing_payload"}), 400

if __name__ == "__main__":
    app.run(port=3000)
