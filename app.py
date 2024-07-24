import asyncio
import concurrent.futures
from threading import Event
from websockets.sync.client import connect as ws_connect

import autogen

from dotenv import load_dotenv
from autogen.io.websockets import IOWebsockets
from openai import OpenAI
from h2o_wave import main, app, Q, ui, data, run_on, on
import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from IPython.display import Image
import os
from datetime import datetime
from tempfile import TemporaryDirectory

from websockets.sync.client import connect as ws_connect

import autogen
from autogen.io.websockets import IOWebsockets

from utils import (
    #cancel_tasks,
    on_generating,
    on_connect,
    #stop_generating,
    #show_notification,
)

#load .env file 
def on_startup():
    # TODO: rm, only for development
    load_dotenv(".env")


@app("/", on_startup=on_startup)
async def serve(q: Q):
    """Route the end user based on how they interacted with the app."""

    if not q.client.initialized:
        initialize_client(q)

    elif q.events.chatbot:
        label, caption, icon = q.app.suggestions[q.events.chatbot.suggestion]
        q.args.chatbot = label + ' ' + caption
    
    if q.args.chatbot:
        #chat_bot_handling(q)
        q.page['chatbot_card'].suggestions = []
        #await on_generating(q, q.args.chatbot)
        # running async functions within the blocking.
        loop = asyncio.get_event_loop()
        # Create an event to use for cancellation.
        q.client.event = Event()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await q.exec(pool, run, q, loop, q.args.chatbot)


    #await run_on(q)  # Route user to the appropriate "on" function
    await q.page.save()  # Update the UI


def initialize_client(q):
    """Code that is needed for each new browser that visits the app"""

    if not q.app.suggestions:
        q.app.suggestions = {
            'sug1': ["Explain CPI", "and what it means", "Edit"],
            'sug2': ["CBA analysis", "recent profit insights", "Airplane"],
            'sug3': ["Mortgages rates", "analyse trends for me", "Lightbulb"],
            'sug4': ["write code", "to analyse sales", "Code"]
        }

    q.page["meta"] = ui.meta_card(
        box="",
        title="Chatbot | H2O.ai",
        layouts=[ui.layout(breakpoint="xs", width="900px", zones=[
            ui.zone(name="header"),
            ui.zone(name="main", size="1"),
            ui.zone(name="footer")
        ])],
        stylesheet=ui.inline_stylesheet("""
            [data-test="footer_card"] a {color: #0000EE !important;}
                
            [data-test="source_code"], [data-test="app_store"],[data-test="support"] {
                color: #000000 !important; background-color: #FFE600 !important
            } 
        """),
    )

    q.page["header_card"] = ui.header_card(
        box="header",
        title="CBA Financial Analyst Agent",
        subtitle="Basic agent workflow",
        image="https://h2o.ai/company/brand-kit/_jcr_content/root/container/section/par/advancedcolumncontro/columns1/advancedcolumncontro/columns0/image.coreimg.svg/1697220254347/h2o-logo.svg",
        items=[
            ui.button(
                name="source_code",
                icon="Code",
                path="https://github.com/h2oai/genai-app-store-apps/tree/main/template-chatbot",
                tooltip="View the source code",
            ),
            ui.button(
                name="app_store",
                icon="Shop",
                path="https://genai.h2o.ai",
                tooltip="Visit the App Store",
            ),
            ui.button(
                name="support",
                icon="Help",
                path="https://support.h2o.ai/support/tickets/new",
                tooltip="Get help",
            ),
        ],
    )

    q.page["chatbot_card"] = ui.chatbot_card(
        box="main",
        name="chatbot",
        data=data(
            fields="content from_user",
            t="list",
            #rows=[[q.client.chatbot.system_prompt, False]]
            rows=[["Welcome to CBA Finacial analysis agent, please ask me to compelete a task", False]],
        ),
        placeholder="Ask me anything...",
        events=['suggestion'],
        suggestions=[ui.chat_suggestion(name, label=value[0], caption=value[1], icon=value[2])
                     for name, value in q.app.suggestions.items()]
    )
    q.page["footer_card"] = ui.footer_card(
        box="footer",
        caption="Made with [Wave](https://wave.h2o.ai), [h2oGPTe](https://h2o.ai/platform/enterprise-h2ogpte), and "
        "💛 by the Makers at H2O.ai.<br />Find more in the [H2O GenAI App Store](https://genai.h2o.ai/).",
    )
    
    q.client.initialized = True


def on_connect(iostream: IOWebsockets) -> None:
    print(f" - on_connect(): Connected to client using IOWebsockets {input}", flush=True)

    print(" - on_connect(): Receiving message from client.", flush=True)

    # 1. Receive Initial Message
    #initial_msg = input
    initial_msg = iostream.input()
    print("input "+ initial_msg)

    llm_config = {"config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}]}

    user_proxy = autogen.UserProxyAgent(
        name="User_proxy",
        system_message="A human admin.",
        code_execution_config={
            "last_n_messages": 3,
            "work_dir": "/Users/pgrenfell/Documents/DS/temp",
            "use_docker": False,
        },  # Please set use_docker=True if docker is available to run the generated code. Using docker is safer than running the generated code directly.
        human_input_mode="NEVER",
    )

    coder = autogen.AssistantAgent(
        name="Coder",  # the default assistant agent is capable of solving problems with code
        llm_config=llm_config,
    )

    critic = autogen.AssistantAgent(
        name="Critic",
        system_message="""Critic. You are a helpful assistant highly skilled in evaluating the quality of a given visualization code by providing a score from 1 (bad) - 10 (good) while providing clear rationale. YOU MUST CONSIDER VISUALIZATION BEST PRACTICES for each evaluation. Specifically, you can carefully evaluate the code across the following dimensions
    - bugs (bugs):  are there bugs, logic errors, syntax error or typos? Are there any reasons why the code may fail to compile? How should it be fixed? If ANY bug exists, the bug score MUST be less than 5.
    - Data transformation (transformation): Is the data transformed appropriately for the visualization type? E.g., is the dataset appropriated filtered, aggregated, or grouped  if needed? If a date field is used, is the date field first converted to a date object etc?
    - Goal compliance (compliance): how well the code meets the specified visualization goals?
    - Visualization type (type): CONSIDERING BEST PRACTICES, is the visualization type appropriate for the data and intent? Is there a visualization type that would be more effective in conveying insights? If a different visualization type is more appropriate, the score MUST BE LESS THAN 5.
    - Data encoding (encoding): Is the data encoded appropriately for the visualization type?
    - aesthetics (aesthetics): Are the aesthetics of the visualization appropriate for the visualization type and the data?

    YOU MUST PROVIDE A SCORE for each of the above dimensions.
    {bugs: 0, transformation: 0, compliance: 0, type: 0, encoding: 0, aesthetics: 0}
    Do not suggest code.
    Finally, based on the critique above, suggest a concrete list of actions that the coder should take to improve the code.
    """,
        llm_config=llm_config,
    )


    commentary = autogen.AssistantAgent(
        name="commentary",
        system_message="""commentary. You are a helpful assistant working at a large Australian bank CBA, you are highly skilled in providing financial analysis commentary on data and graphs that have been produced. 
        You must always start with that the commentary is provided by the CBA finance team.
    """,
        llm_config=llm_config,
    )

    groupchat = autogen.GroupChat(agents=[user_proxy, coder, critic, commentary], messages=[], max_round=30)
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    user_proxy.initiate_chat(
        manager,
        message=initial_msg,
    )



def run(q: Q, loop: asyncio.AbstractEventLoop, input):
    with IOWebsockets.run_server_in_thread(on_connect=on_connect, port=8667) as uri:
        print(f" - test_setup() with websocket server running on {uri}.", flush=True)

        with ws_connect(uri) as websocket:
            print(f" - Connected to server on {uri}", flush=True)

            print(" - Sending message to server.", flush=True)
            # websocket.send("2+2=?")
            websocket.send(input)

            while True:
                    try:
                        message = websocket.recv()
                        print(f"Received message this is everything: {message}")
                        message = message.decode("utf-8") if isinstance(message, bytes) else message
                        # Assume you are able to emit some kind of progress.
                    
                        print('updating the ui with')
                        #print("length of message " +len(message))
                        #print(message)
                        asyncio.ensure_future(update_ui(q, message), loop=loop)
                    # Process the message here
                    except:
                        print("WebSocket connection closed normally.")
                        break
                
                
                    print(message, end="", flush=True)

                    if "TERMINATE" in message:
                        print()
                        print(" - Received TERMINATE message. Exiting.", flush=True)
                        break


async def update_ui(q: Q, message):
    print('message is ' + message)
    print('updating chatbot card with ' , len(message))
    if 'EXECUTING CODE BLOCK' in message:
        message = 'EXECUTING CODE BLOCK'
    q.page['chatbot_card'].data += [message, False]
    await q.page.save()