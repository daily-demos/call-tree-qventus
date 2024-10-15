# Building a Call Tree With Daily Bots

This demo shows how you can build an IVR-style phone call tree powered by an LLM using Daily Bots.

The 'tree' istelf is built using [webhook function calling in Daily Bots](https://docs.dailybots.ai/api-reference/webhooks) in `main.py`, and [python-statemachine](https://python-statemachine.readthedocs.io/en/latest/) in `call_tree.py` like this:

1. The webserver in `main.py` starts a Daily Bot and provides a system prompt to start the call. It also defines several functions that the LLM can use to move to the next 'page' of the call.

2. When the user says something that meets the exit condition for a 'page', such as correctly identifying themselves as the person the bot is trying to reach, the LLM will return a function call instead of a response to the user. The Daily Bots framework will turn that function call into a webhook request sent to the `/webhooks` endpoint.

3. That webhook is sent to the state machine defined in `call_tree.py`, which transitions it to a new state, or 'page'. That new page adds instructions as additional system prompts into the bot's context. It also defines a new set of functions that the bot can use to leave this 'page' and move to the next pages.

## Running your own server

To run this yourself:

1. Sign up for a [Daily Bots account](https://bots.daily.co/sign-up). Add a credit card and grab your API key.
2. Clone this repo, set up a venv, and populate a .env file:

```
git clone git@github.com:daily-co/daily-bots-phone-tree.git
cd daily-bots-phone-tree
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp env.example .env
```

3. Add your OpenAI and Daily (Bots) API keys to the .env file. Your Daily Bots API key is available [here](https://bots.daily.co/dashboard/secrets).

4. Run the server: `uvicorn main:app --reload`.

5. Install [ngrok](https://ngrok.com/) so your local server can receive webhooks from Daily's servers. Start ngrok running in a terminal window with a command like `ngrok http --domain yourdomain.ngrok.app 8000`.

6. Use your Daily API key to [buy a phone number](https://docs.daily.co/reference/rest-api/phone-numbers/buy-phone-number).

7. Follow [this guide](https://docs.daily.co/guides/products/dial-in-dial-out/dialin-pinless#provisioning-sip-interconnect-and-pinless-dialin-workflow) to enable dial-in for your domain. For the `room_creation_api` property, point at your ngrok hostname: `"room_creation_api": "https://your domain.ngrok.app"`.

Dial your purchased phone number. You should hear hold music for 1-2 seconds and see activity in your terminal windows, then the phone should ring once, and the bot should start talking to you!
