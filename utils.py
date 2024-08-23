import asyncio
#from concurrent.futures import ThreadPoolExecutor
import os
import markdown
import autogen
from h2o_wave import Q, ui


async def on_generating(q, question_prompt, collection_id=None):
    q.page["chatbot_card"].data += [question_prompt, True]
    await generating_true(q)
    output = await q.run(on_connect, q)
    q.client.task = asyncio.create_task(stream_chat_message(q, output))
    q.client.generating = True


async def generating_true(q):
    q.client.generating = True
    q.page["chatbot_card"].data += [
        "<img src='{}' height='40px'/>".format(q.app.loader),
        False,
    ]
    await q.page.save()


async def stream_chat_message(q, output):
    stream = ""
    final_output = f"""{output} <br/>"""
    # convert to markdown
    final_output = markdown.markdown(final_output)
    # remove the last line
    q.page["chatbot_card"].data[-1] = [stream, False]
    # Show the "Stop generating" button
    q.page["chatbot_card"].generating = True
    q.client.generating = True
    for w in final_output.split():
        await asyncio.sleep(0.1)
        stream += w + " "
        q.page["chatbot_card"].data[-1] = [stream, False]
        await q.page.save()

    # Hide the "Stop generating" button
    q.page["chatbot_card"].generating = False
    q.client.generating = False
    await q.page.save()


#run agents function 
async def on_connect(q:Q) -> None:

    # 1. Receive Initial Message
    initial_msg = q.args.chatbot

    # 2. Instantiate ConversableAgent
    agent = autogen.ConversableAgent(
        name="chatbot",
        system_message="Complete a task given to you and reply TERMINATE when the task is done. If asked about the weather, use tool 'weather_forecast(city)' to get the weather forecast for a city.",
        llm_config={"config_list": [{"model": "gpt-3.5-turbo", "api_key": os.environ.get("OPENAI_API_KEY")}],"stream": True}
    )

    # 3. Define UserProxyAgent
    user_proxy = autogen.UserProxyAgent(
        name="user_proxy",
        system_message="A proxy for the user.",
        is_termination_msg=lambda x: x.get("content", "") and x.get("content", "").rstrip().endswith("TERMINATE"),
        human_input_mode="NEVER",
        max_consecutive_auto_reply=2,
        code_execution_config=False,
    )

    # 4. Define Agent-specific Functions
    def weather_forecast(city: str) -> str:
        return f"The weather forecast for {city} at {datetime.now()} is sunny."

    autogen.register_function(
        weather_forecast, caller=agent, executor=user_proxy, description="Weather forecast for a city"
    )

    # 5. Initiate conversation
    print(
        f" - on_connect(): Initiating chat with agent {agent} using message '{initial_msg}'",
        flush=True,
    )

    stream = user_proxy.initiate_chat(  # noqa: F704
        agent,
        message=initial_msg,
    )
    for chunk in stream:
        if chunk.choices[0].delta.content is not None:
            print(chunk.choices[0].delta.content, end="")


def get_latest_png(folder_path):
    latest_file = None
    latest_time = None

    for file_name in os.listdir(folder_path):
        if file_name.lower().endswith('.png'):
            file_path = os.path.join(folder_path, file_name)
            file_time = os.path.getmtime(file_path)
            
            if latest_time is None or file_time > latest_time:
                latest_file = file_path
                latest_time = file_time

    return latest_file