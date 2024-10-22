from statemachine import State, StateMachine


class CallTree(StateMachine):
    def __init__(self, patient_name, office_name, surgery, documents):
        self._patient_name = patient_name
        self._office_name = office_name
        self._surgery = surgery
        self._documents = documents
        self.messages = []
        super().__init__()

    def disposition(self, message):
        print(f"!!! DISPOSITION: {message}")

    node_1 = State(initial=True)
    node_2 = State()
    node_3 = State()
    node_4 = State()
    node_5 = State()
    node_6 = State()

    wrong_number = node_1.to(node_2)
    confirmed_office = node_1.to(node_3)
    human_followup = node_3.to(node_4) | node_5.to(node_4)
    correct_person = node_3.to(node_5)
    expected_documents = node_5.to(node_6)

    def on_exit_state(self, event, state):
        self.messages = []

    def on_enter_node_1(self):
        print("!!! Entering node 1")

    def on_enter_node_2(self):
        self.messages = [
            {
                "action": {
                    "service": "tts",
                    "action": "say",
                    "arguments": [
                        {
                            "name": "text",
                            "value": "Sorry for the trouble. Have a nice day!",
                        },
                        {"name": "save", "value": True},
                        {"name": "interrupt", "value": False},
                    ],
                }
            },
        ]
        print("WRONG NUMBER")

    def on_enter_node_3(self):
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
                                    "content": f"""Now that you've confirmed you're speaking to the right office, you need to collect the following medical records:
                                    
                                    {'; '.join(self._documents)}
                                    
                                    If the person you're speaking to can help provide the documents, call the correct_person function. If they say you need to speak to someone else, wait for them to transfer you, confirm the person you're speaking to can help, and then call the correct_person function. If they tell you they can't help, call the human_followup function.
                                    """,
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
                                        "name": "correct_person",
                                        "description": "Call this function when you've confirmed that you're speaking with someone who can provide the requested medical records.",
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
                                        "name": "human_followup",
                                        "description": "Call this function if the user says they are unable to help with your request for medical records.",
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
                            "value": f"I’m a digital assistant calling from Tri-County Medical Services regarding {self._patient_name}, who is scheduled for {self._surgery}. Our office needs some help with some of their medical records. Are you able to assist with that?",
                        },
                        {"name": "save", "value": True},
                        {"name": "interrupt", "value": False},
                    ],
                }
            },
        ]

    def on_enter_node_4(self):
        self.messages = [
            {
                "action": {
                    "service": "tts",
                    "action": "say",
                    "arguments": [
                        {
                            "name": "text",
                            "value": "I understand, thank you for checking. We will have someone from our team follow up with you shortly.",
                        },
                        {"name": "save", "value": True},
                        {"name": "interrupt", "value": False},
                    ],
                }
            },
        ]
        print("CAN'T HELP")

    def on_enter_node_5(self):
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
                                    "content": f"""TASK: 
                                    Now that you've confirmed you're speaking to the right person to help, you need to collect the following medical records:
                                    
                                    {'; '.join(self._documents)}
                                    
                                    The user can provide the records by email or fax. They can email PDFs to documents@tricountymed.com, or they can fax them to 480-348-3345. You should try to get the documents today if you can, but you can wait up to a week if necessary.
                                    
                                    Ask the user how they'd like to send the records, and when they think they'll be able to send them. When you have a method and date, call the expected_documents function. If you're unable to complete the task, call the human_followup function.
                                    """,
                                }
                            ],
                        },
                        {"name": "run_immediately", "value": True},
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
                                        "name": "expected_documents",
                                        "description": "Call this function when you've verified that the user has all the documents you need, and they've told you how and when they are able to send them to you.",
                                        "parameters": {
                                            "type": "object",
                                            "properties": {
                                                "method": {
                                                    "type": "string",
                                                    "description": "How the user plans to send you the documents, such as 'email' or 'fax'.",
                                                },
                                                "date": {
                                                    "type": "string",
                                                    "description": "The expected date you will receive the documents in YYYY-MM-DD format.",
                                                },
                                            },
                                            "required": ["method", "date"],
                                        },
                                    },
                                },
                                {
                                    "type": "function",
                                    "function": {
                                        "name": "human_followup",
                                        "description": "Call this function if the user says they are unable to help with your request for medical records.",
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
                        {"name": "run_immediately", "value": False},
                    ],
                }
            },
        ]

    def on_enter_node_6(self):
        self.messages = [
            {
                "action": {
                    "service": "tts",
                    "action": "say",
                    "arguments": [
                        {
                            "name": "text",
                            "value": "It looks like I have everything I need. Thanks for your help! Goodbye!",
                        },
                        {"name": "save", "value": True},
                        {"name": "interrupt", "value": False},
                    ],
                }
            },
        ]
        print("CAN'T HELP")
