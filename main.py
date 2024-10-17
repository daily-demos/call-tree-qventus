import json
import os
import uuid
from typing import Annotated, Optional

import aiohttp
import modal
import pytz
from dotenv import load_dotenv
from fastapi import FastAPI, Header
from pydantic import BaseModel
from starlette.responses import StreamingResponse

from call_tree import CallTree

load_dotenv(override=True)

modal_app = modal.App("phone-tree")
image = (
    modal.Image.debian_slim(python_version="3.11")
    .pip_install("boto3")
    .pip_install_from_requirements("requirements.txt")
)


class FunctionCallRequest(BaseModel):
    function_name: str
    tool_call_id: str
    arguments: dict


class StartRequest(BaseModel):
    From: str = None
    To: str = None
    callId: str = None
    callDomain: str = None
    dialout: str = None


class LanguageRequest(BaseModel):
    language: str


app = FastAPI()
load_dotenv(override=True)

languages = {
    "english": {
        "value": "en-US",
        "tts_model": "sonic-english",
        "stt_model": "nova-2-conversationalai",
        "default_voice": "79a125e8-cd45-4c13-8a67-188112f4dd22",
    },
    "french": {
        "value": "fr",
        "tts_model": "sonic-multilingual",
        "stt_model": "nova-2-general",
        "default_voice": "a8a1eb38-5f15-4c1d-8722-7ac0f329727d",
    },
    "spanish": {
        "value": "es",
        "tts_model": "sonic-multilingual",
        "stt_model": "nova-2-general",
        "default_voice": "846d6cb0-2301-48b6-9683-48f5618ea2f6",
    },
    "german": {
        "value": "de",
        "tts_model": "sonic-multilingual",
        "stt_model": "nova-2-general",
        "default_voice": "b9de4a89-2257-424b-94c2-db18ba68c81a",
    },
}

call_trees = {}


async def language_changer(function_name, tool_call_id, arguments):
    """If the LLM calls the change_language function, this function sends RTVI message to change the TTS and STT languages."""

    lang = languages[arguments["language"]]
    events = [
        {
            "update-config": {
                "config": [
                    {
                        "service": "tts",
                        "options": [
                            {"name": "voice", "value": lang["default_voice"]},
                            {"name": "model", "value": lang["tts_model"]},
                            {"name": "language", "value": lang["value"]},
                        ],
                    },
                    # { Changing this during the call breaks transcription?
                    #     "service": "stt",
                    #     "options": [
                    #         {"name": "model", "value": lang["stt_model"]},
                    #         {"name": "language", "value": lang["value"]},
                    #     ],
                    # },
                ]
            }
        },
        {
            "action": {
                "service": "llm",
                "action": "function_result",
                "arguments": [
                    {"name": "function_name", "value": function_name},
                    {"name": "tool_call_id", "value": tool_call_id},
                    {"name": "arguments", "value": arguments},
                    {
                        "name": "result",
                        "value": {"language": arguments["language"]},
                    },
                ],
            }
        },
    ]
    for e in events:
        for k, v in e.items():
            yield f"event: {k}\ndata: {json.dumps(v)}\n\n"
    yield "data:close\n\n"


async def response_streamer(messages, function_name, tool_call_id, arguments):
    """Takes an array of RTVI messages and formats them as server-sent events."""

    for m in messages:
        print(f"!!! m is: {m}")
        for k, v in m.items():
            yield f"event: {k}\ndata: {json.dumps(v)}\n\n"
    yield "data:close\n\n"


# If you want to also use this webhook server for a dial-in bot, you can use the
# /start action here.
@app.post("/start")
async def start(req: StartRequest):
    """POST to this endpoint to start a Daily Bots session."""

    async with aiohttp.ClientSession() as session:
        conversation_id = str(uuid.uuid4())
        run_on_config = True
        if req.dialout:
            run_on_config = False
        bot_config = {
            "bot_profile": "voice_2024_10",
            "max_duration": "300",
            "services": {"tts": "cartesia", "llm": "openai"},
            "api_keys": {"openai": os.getenv("OPENAI_API_KEY", None)},
            "webhook_tools": {
                "change_language": {
                    "url": f"{os.getenv('WEBHOOK_HOST', 'http://localhost:8000')}/language",
                    "method": "POST",
                    "streaming": True,
                    "custom_headers": {"conversation-id": conversation_id},
                },
                "*": {
                    "url": f"{os.getenv('WEBHOOK_HOST', 'http://localhost:8000')}/webhook",
                    "method": "POST",
                    "streaming": True,
                    "custom_headers": {"conversation-id": conversation_id},
                },
            },
            "config": [
                {
                    "service": "tts",
                    "options": [
                        {
                            "name": "voice",
                            "value": "829ccd10-f8b3-43cd-b8a0-4aeaa81f3b30",
                        }
                    ],
                },
                {
                    "service": "stt",
                    "options": [{"name": "model", "value": "nova-2-general"}],
                },
                {
                    "service": "llm",
                    "options": [
                        {"name": "model", "value": "gpt-4o"},
                        {
                            "name": "initial_messages",
                            "value": [
                                {
                                    "role": "system",
                                    "content": [
                                        {
                                            "type": "text",
                                            "text": "You are Jackie, an agent for Bob's Barber Academy. You are calling to speak with Chad Bailey. Your responses are being converted to speech, so avoid special characters and markup. Begin by introducing yourself and confirming you're speaking with Chad. If you've confirmed you're speaking with Chad, call the correct_person function. If Chad isn't available, call the not_available_now function. If you've called the wrong number, call the wrong_number function. If someone asks why you're calling, tell them we received an request for more information about Bob's Barber Academy from an online form filled out by Chad.",
                                        }
                                    ],
                                }
                            ],
                        },
                        {
                            "name": "tools",
                            "value": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "correct_person",
                                        "description": "Call this function when you've verified that you're speaking to the correct person.",
                                        "parameters": {
                                            "type": "object",
                                            "properties": {
                                                "name": {
                                                    "type": "string",
                                                    "description": "The name of the person you're speaking with.",
                                                },
                                            },
                                            "required": ["name"],
                                        },
                                    },
                                },
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "not_available_now",
                                        "description": "Call this function if the person you're trying to reach isn't available to speak right now.",
                                        "parameters": {
                                            "type": "object",
                                            "properties": {
                                                "name": {
                                                    "type": "string",
                                                    "description": "The name of the person you're trying to speak with.",
                                                },
                                            },
                                            "required": ["name"],
                                        },
                                    },
                                },
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "wrong_number",
                                        "description": "Call this function if the person you're talking to says you've called the wrong number.",
                                        "parameters": {
                                            "type": "object",
                                            "properties": {
                                                "name": {
                                                    "type": "string",
                                                    "description": "The name of the person you're trying to speak with.",
                                                },
                                            },
                                            "required": ["name"],
                                        },
                                    },
                                },
                            ],
                        },
                        {"name": "run_on_config", "value": run_on_config},
                    ],
                },
            ],
        }
        call_trees[conversation_id] = CallTree("Chad Bailey", "Bob's Barber Academy")
        if req.callId:
            bot_config["dialin_settings"] = {
                "callId": req.callId,
                "callDomain": req.callDomain,
            }
        if req.dialout:
            bot_config["dialout_settings"] = [{"phoneNumber": req.dialout}]
        headers = {"Authorization": f"Bearer {os.getenv('DAILY_API_KEY')}"}
        response_data = {}
        r = await session.post(
            os.getenv("BOT_START_URL", "https://api.daily.co/v1/bots/start"),
            headers=headers,
            json=bot_config,
        )
        if r.status != 200:
            text = await r.text()
            raise Exception(f"Problem starting a bot worker: {text}")

        response_data = await r.json()
        print(f"Bot config: {bot_config}")
        print(f"Room to join: {response_data['room_url']}?t={response_data['token']}")
        return response_data


@app.post("/language")
async def set_language(req: FunctionCallRequest):
    """The LLM will POST a webhook to this endpoint if it calls the change_lanugage function."""

    print("Language request received: req")
    return StreamingResponse(
        language_changer(req.function_name, req.tool_call_id, req.arguments),
        media_type="text/event-stream",
    )


@app.post("/webhook")
async def webhook(
    req: FunctionCallRequest, conversation_id: Annotated[str | None, Header()] = None
):
    """This is the webhook endpoint used for calling all the call tree functions."""

    print(f"!!! got a webhook function call: {req}, conversation_id: {conversation_id}")
    ct = call_trees[conversation_id]
    # we'll eventually dispatch the actual webhook function_name to the state machine.
    # For now, this cycle() function moves from page 1 to page 2, but the state machine
    # events don't return anything, so we have to store our desired messages in an
    # instance var in the state machine.
    ct.send(req.function_name)

    print(f"!!! machine state: {ct.current_state.name}")
    print(f"!!! messages: {ct.messages}")
    return StreamingResponse(
        response_streamer(
            ct.messages, req.function_name, req.tool_call_id, req.arguments
        ),
        media_type="text/event-stream",
    )


@app.get("/")
def homepage():
    return {"hello": "world"}


@modal_app.function(image=image, secrets=[modal.Secret.from_name("my-custom-secret")])
@modal.asgi_app()
def fastapi_app():
    return app
