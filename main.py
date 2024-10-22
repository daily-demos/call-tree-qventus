import json
import os
import uuid
from typing import Annotated

import aiohttp
import modal
from dotenv import load_dotenv
from fastapi import FastAPI, Header
from pydantic import BaseModel
from starlette.responses import StreamingResponse
from starlette.middleware import Middleware
from starlette.middleware.cors import CORSMiddleware

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


app = FastAPI(
    middleware=[
        Middleware(
            CORSMiddleware,
            allow_origins=["*"],
            allow_credentials=True,
            allow_methods=["*"],
            allow_headers=["*"],
        )
    ]
)
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
                                            "text": """Conversational Style:
                                            
                                            Make sure to ONLY ASK ONE QUESTION at a time to not overwhelm the user and KEEP YOUR questions SHORT. Your communication style should be proactive and lead the conversation, asking targeted questions. Ensure your responses are concise, clear, and maintain a conversational tone. If the user only partially answers a question, RE-ASK the part that they forgot to answer.
                                            
                                            Approach the conversation with a professional and courteous tone and be friendly with them.
                                            
                                            Ask for information in a clear and concise manner, ensuring not to overwhelm the office staff.
                                            
                                            Be patient and give the person on the other end time to respond to your requests.
                                            
                                            If the office staff needs time to locate the information, offer to hold or suggest a callback time.
                                            
                                            If the office cannot find the patient or encounters any issues, apologize and inform them that someone from the hospital will follow up.
                                            
                                            TASK: 
                                            Today, you are tasked with calling Dr. Carlson's office to collect specific medical information about their patient Alice Adams scheduled for knee replacement surgery. 
                                            
                                            Start by confirming you are speaking to the correct office. If this is Dr. Carlson's office, call the 'confirmed_office' function. If it's not, call the 'wrong_number' function.""",
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
                                        "name": "confirmed_office",
                                        "description": "Call this function when the user confirms they're with Dr. Carlson's office.",
                                        "parameters": {
                                            "type": "object",
                                            "properties": {
                                                "office": {
                                                    "type": "string",
                                                    "description": "The name of the office you're calling.",
                                                },
                                            },
                                            "required": ["office"],
                                        },
                                    },
                                },
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "wrong_number",
                                        "description": "Call this function if the user says you've called the wrong number.",
                                        "parameters": {
                                            "type": "object",
                                            "properties": {
                                                "office": {
                                                    "type": "string",
                                                    "description": "The name of the office you're calling.",
                                                },
                                            },
                                            "required": ["office"],
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
        call_trees[conversation_id] = CallTree(
            patient_name="Alice Adams",
            office_name="Dr. Carlson's office",
            surgery="knee replacement",
            documents=[
                "Knee X-ray taken on October 8",
                "Lab tests performed on October 10",
            ],
        )
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
