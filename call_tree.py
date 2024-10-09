from statemachine import State, StateMachine


class CallTree(StateMachine):
    def __init__(self, name, school):
        self._name = name
        self._school = school
        self.messages = []
        super().__init__()

    def disposition(self, message):
        print(f"!!! DISPOSITION: {message}")

    page_1 = State(initial=True)
    page_2 = State()
    page_3 = State()
    page_4 = State()
    page_7 = State()
    page_8 = State()
    page_11 = State()
    page_17 = State()
    page_26 = State()

    correct_person = page_1.to(page_2)
    not_available_now = page_1.to(page_8)
    wrong_number = page_1.to(page_11)
    why_calling = page_1.to(page_17)

    did_enrollment = page_2.to(page_7)
    no_enrollment_yet = page_2.to(page_3)

    yes_to_transfer = page_3.to(page_4)
    no_to_transfer = page_3.to(page_26)

    def on_exit_state(self, event, state):
        self.messages = []

    def on_enter(self, state):
        print(f"@@@ Entered {state}")

    def on_enter_page_2(self):
        # This page doesn't actually disposition but I needed to demo it
        self.disposition("confirmed identity")
        self.messages = [
            {
                "action": {
                    "service": "llm",
                    "action": "append_to_messages",
                    "arguments": [
                        {
                            "name": "messages",
                            "value": [
                                {
                                    "role": "system",
                                    "content": "Now that you've confirmed you're speaking to the correct person. You need to determine if they have already completed the online enrollment process. If they have, call the did_enrollment function. If they haven't and they are a new prospect, call the no_enrollment_yet function.",
                                }
                            ],
                        },
                        {"name": "run_immediately", "value": False},
                    ],
                }
            },
            {
                "action": {
                    "service": "llm",
                    "action": "set_context",
                    "arguments": [
                        {
                            "name": "tools",
                            "value": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "did_enrollment",
                                        "description": "Call this function when the user confirms they've completed the online enrollment process.",
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
                                        "name": "no_enrollment_yet",
                                        "description": "Call this function when the user says that they haven't completed the online enrollment process yet.",
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
                            ],
                        },
                        {"name": "run_immediately", "value": False},
                    ],
                }
            },
            {
                "action": {
                    "service": "tts",
                    "action": "say",
                    "arguments": [
                        {
                            "name": "text",
                            "value": f"Hi {self._name}, this is Jackie from {self._school} and you can opt out of this and future calls at any time. This call is recorded and I'm calling about your interest in the School Program. Have you already completed the online enrollment process?",
                        },
                        {"name": "save", "value": True},
                        {"name": "interrupt", "value": False},
                    ],
                }
            },
        ]

    def on_enter_page_3(self):
        self.messages = [
            {
                "action": {
                    "service": "llm",
                    "action": "set_context",
                    "arguments": [
                        {
                            "name": "tools",
                            "value": [
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "yes_to_transfer",
                                        "description": "Call this function if the user agrees to be transferred to an admissions specialist.",
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
                                        "name": "no_to_transfer",
                                        "description": "Call this function if the user does not want to speak to an admissions specialist.",
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
                            ],
                        },
                        {"name": "run_immediately", "value": False},
                    ],
                }
            },
            {
                "action": {
                    "service": "tts",
                    "action": "say",
                    "arguments": [
                        {
                            "name": "text",
                            "value": "I would like to transfer you to an Admissions Specialist who can give you some more information about the program and answer any questions you might have. May I do this for you now?",
                        },
                        {"name": "save", "value": True},
                        {"name": "interrupt", "value": False},
                    ],
                }
            },
        ]

    def on_enter_page_11(self):
        self.disposition("confirmed identity")
        self.messages = [
            {
                "action": {
                    "service": "tts",
                    "action": "say",
                    "arguments": [
                        {
                            "name": "text",
                            "value": "Sorry to bother you. Have a great day. Goodbye!",
                        },
                        {"name": "save", "value": True},
                        {"name": "interrupt", "value": False},
                    ],
                }
            },
        ]

    def on_enter_page_26(self):
        self.disposition("Customer interested but refused warm transfer")
        self.messages = [
            {
                "action": {
                    "service": "tts",
                    "action": "say",
                    "arguments": [
                        {
                            "name": "text",
                            "value": "That's okay. Thank you for your time. Have a nice day. Goodbye!",
                        },
                        {"name": "save", "value": True},
                        {"name": "interrupt", "value": False},
                    ],
                }
            },
        ]
