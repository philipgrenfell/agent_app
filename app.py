import asyncio
import concurrent.futures
from threading import Event
from websockets.sync.client import connect as ws_connect

import autogen
from h2o_wave import main, app, Q, ui, data, run_on, on
import os
import glob
from datetime import datetime
from tempfile import TemporaryDirectory

from websockets.sync.client import connect as ws_connect
from autogen.io.websockets import IOWebsockets
from autogen.function_utils import get_function_schema

from utils import (
    #cancel_tasks,
    on_generating,
    on_connect,
    get_latest_png,
    #stop_generating,
    #show_notification,
)

#load .env file 
#def on_startup():
    # TODO: rm, only for development
    #load_dotenv(".env")

temp_work_dir = '/Users/pgrenfell/Documents/DS/temp'

@app("/") #can run on startup if needed
async def serve(q: Q):
    """Route the end user based on how they interacted with the app."""

    if not q.client.initialized:
        await initialize_client(q)

    elif q.events.chatbot:
        label, caption, icon = q.app.suggestions[q.events.chatbot.suggestion]
        q.args.chatbot = label + ' ' + caption
    
    if q.args.chatbot:
        q.page['chatbot_card'].suggestions = []
        # running async functions within the blocking.
        # remove all text from 
        q.page['commentery_card'].content = '''
        *Waiting on analysis from LewisAI*
        '''
        loop = asyncio.get_event_loop()
        # Create an event to use for cancellation.
        q.client.event = Event()
        with concurrent.futures.ThreadPoolExecutor() as pool:
            await q.exec(pool, run, q, loop, q.args.chatbot)
        #update txt box with latest message


    #await run_on(q)  # Route user to the appropriate "on" function
    await q.page.save()  # Update the UI


async def initialize_client(q):
    """Code that is needed for each new browser that visits the app"""
    
    #to do add code that removes all previous files from the temp dir
    file_pattern = os.path.join(temp_work_dir, '*')
    # Use map to delete all files
    list(map(os.remove, filter(os.path.isfile, glob.glob(file_pattern))))


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
        layouts=[ui.layout(breakpoint="xl", width="1200px", zones=[
            ui.zone(name="header", size='75px'),
            ui.zone(name="main", size="700px",direction=ui.ZoneDirection.ROW, zones = [
                ui.zone('chatbot_box', size = '60%'),
                ui.zone('rhs', zones = [
                    ui.zone('img_box', size = '70%'),
                    ui.zone('commentry_box', size = '30%')
                ])
            ]),
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
        title="LewisAi - your friendly analyst",
        subtitle="Basic agent workflow example",
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
        box="chatbot_box",
        name="chatbot",
        data=data(
            fields="content from_user",
            t="list",
            #rows=[[q.client.chatbot.system_prompt, False]]
            rows=[["Welcome, I'm LewisAi please ask me to compelete a task", False]],
        ),
        placeholder="Ask me anything...",
        events=['suggestion'],
        suggestions=[ui.chat_suggestion(name, label=value[0], caption=value[1], icon=value[2])
                     for name, value in q.app.suggestions.items()]
    )

    image, = await q.site.upload(['./static/agent_img2.jpeg'])
    # image, = await q.site.upload(['./static/CBA_stock_price_plot.png'])
    #print('\n image is ', image)
    
    #this is static 
    q.page['image_card'] = ui.image_card(
        box=ui.box(zone='img_box',width='480px', height='480px'),
        title='',
        path=image,
        type='png')
    
    q.page['commentery_card'] = ui.article_card(
        box='commentry_box',
        title='',
        items=[],
        content='''
**Meet LewisAI:** Your expert financial analysis assistant, specializing in delivering actionable insights through advanced data interpretation and visually compelling charts.

- **In-depth financial analysis** tailored to your specific needs.
- **Custom graph generation** to visualize trends, comparisons, and forecasts.
- **Data-driven decision-making support** for businesses and individuals.
        '''
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
            "work_dir": temp_work_dir,
            "use_docker": False,
        },  # Please set use_docker=True if docker is available to run the generated code. Using docker is safer than running the generated code directly.
        human_input_mode="NEVER",
    )

    coder = autogen.AssistantAgent(
        name="Coder",  # the default assistant agent is capable of solving problems with code
        system_message=""" You are an extremely advanced programmer, however you are only able to code in python and if you produce graphs they must be saved into the current working directory, graphs must also be of 480x480 in size.
        You must not ever code plot.show or any other code that forces and image to appear. 

        You are not to comment on any graph produced that is to be completed by the commentary agent.
        """,

        llm_config=llm_config,
    )

    critic = autogen.AssistantAgent(
        name="Critic",
        system_message="""Critic. You are a helpful assistant highly skilled in evaluating the quality of a given visualization code by providing a score from 1 (bad) - 10 (good) while providing clear rationale. YOU MUST CONSIDER VISUALIZATION BEST PRACTICES for each evaluation. Specifically, you can carefully evaluate the code across the following dimensions
    - bugs (bugs):  are there bugs, logic errors, syntax error or typos? Are there any reasons why the code may fail to compile? How should it be fixed? If ANY bug exists, the bug score MUST be less than 5.
    - Visualization type (type): CONSIDERING BEST PRACTICES, is the visualization type appropriate for the data and intent? Is there a visualization type that would be more effective in conveying insights? If a different visualization type is more appropriate, the score MUST BE LESS THAN 5.
    - aesthetics (aesthetics): Are the aesthetics of the visualization appropriate for the visualization type and the data?
    Do not suggest code.
    Finally, based on the critique above, suggest a concrete list of actions that the coder should take to improve the code.
    """,
        llm_config=llm_config,
    )

    # commentary = autogen.AssistantAgent(
    #     name="commentary",
    #     system_message="""commentary. You are a helpful assistant working at a large Australian bank CBA, you are highly skilled in providing financial analysis commentary on data and graphs that have been produced. 
    #     You must always start with that the commentary is provided by the CBA finance team.
    # """,
    #     llm_config=llm_config)


    write_to_txt_schema = get_function_schema(
        write_to_txt,
        name="write_to_txt",
        description="Writes a formatted string to a text file. If the file does not exist, it will be created. If the file does exist, it will be overwritten.",
        )

    commentary = autogen.AssistantAgent(
        name="commentary",
        system_message="""commentary. You are a helpful assistant working at a large Australian bank CBA, you are highly skilled in providing financial analysis commentary on data and graphs that have been produced. 
        You must always start with that the commentary is provided by the CBA finance team.
    """,
        llm_config={
            "config_list": [{"model": "gpt-4o", "api_key": os.environ["OPENAI_API_KEY"]}],
            "tools": [write_to_txt_schema],
        },
    )

    commentary.register_function(
    function_map={
        "write_to_txt": write_to_txt,
    },
    )

    groupchat = autogen.GroupChat(agents=[user_proxy, coder, critic, commentary], messages=[], max_round=10)
    manager = autogen.GroupChatManager(groupchat=groupchat, llm_config=llm_config)

    user_proxy.initiate_chat(
        manager,
        message=initial_msg,
    )

    #can use this to register tools that will write out the feedback
    #https://microsoft.github.io/autogen/docs/notebooks/gpt_assistant_agent_function_call/



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
                    
                        print('updating the chatbot with \n')
                        asyncio.ensure_future(update_ui(q, message), loop=loop)
                        
                        print('updating the png images \n')
                        asyncio.ensure_future(update_png(q), loop=loop)

                        print('updating the txt box \n')
                        asyncio.ensure_future(update_txt(q), loop=loop)


                    # Process the message here
                    except:
                        print("WebSocket connection closed normally.")
                        break
                
                
                    print(message, end="", flush=True)

                    if "TERMINATE" in message:
                        print()
                        print(" - Received TERMINATE message. Exiting.", flush=True)
                        break


#update chabot ui with streamed messages
async def update_ui(q: Q, message):
    print('message is ' + message)
    print('updating chatbot card with ' , len(message))
    if 'EXECUTING' in message:
        message = 'EXECUTING CODE/FUNCTION BLOCK'
    q.page['chatbot_card'].data += [message, False]
    await q.page.save()

#update png image with what has been created
async def update_png(q: Q):
    latest_png = get_latest_png(temp_work_dir)
    #need to add in if none
    print('latest png' + latest_png)
    image, = await q.site.upload([latest_png])
    q.page['image_card'].path = image
    await q.page.save()

async def update_txt(q: Q):
    try:
        with open(os.path.join(temp_work_dir, "final_commentry.txt"), 'r') as file:
            content = file.read()
        q.page['commentery_card'].content = content
        
    except:
        return 




def write_to_txt(content: str, filename: str = "final_commentry.txt"):
    """
    Writes a formatted string to a text file.
    Parameters:

    - content: The formatted string to write.
    - filename: The name of the file to write to. Defaults to "final_commentry.txt".
    """

    #ensure it is saving to the temp dir
    file_path = os.path.join(temp_work_dir, "final_commentry.txt")

    with open(file_path, "w") as file:
        file.write(content)

