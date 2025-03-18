from langchain_mcp_adapters.client import MultiServerMCPClient
from langgraph.prebuilt import create_react_agent
from langchain_openai import ChatOpenAI
import os
from dotenv import load_dotenv
load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ["CHAT_MODEL"],
    base_url=os.environ["OPENAI_API_BASE"],
    streaming=True
)


async def run():
    async with MultiServerMCPClient(
        {
            "hot-topics": {
                "command": "/Users/gitsilence/miniforge3/envs/machine_learning/bin/python",
                "args": ["/Users/gitsilence/PycharmProjects/hot-topic-mcp/main.py"],
                "transport": "stdio"
            },
            "fetch-web-content": {
                "url": "http://localhost:8001/sse/",
                "transport": "sse"
            }
        }
    ) as client:
        tools = client.get_tools()
        print(tools)
        agent = create_react_agent(model=model, tools=tools)
        async for chunk in agent.astream({"messages": "查下当前新浪微博热搜"}):
            if "agent" in chunk and "messages" in chunk["agent"]:
                messages = chunk["agent"]["messages"]
                if messages and hasattr(messages[-1], "content"):
                    content_chunk = messages[-1].content
                    if content_chunk:
                        print(content_chunk, end="", flush=True)
        print()  # 输出完成后换行

        async for chunk in agent.astream({"messages": "网址:https://blog.lacknb.cn/articles/2025/03/09/1741505760838.html，总结一下网页信息"}):
            if "agent" in chunk and "messages" in chunk["agent"]:
                messages = chunk["agent"]["messages"]
                if messages and hasattr(messages[-1], "content"):
                    content_chunk = messages[-1].content
                    if content_chunk:
                        print(content_chunk, end="", flush=True)
        print()  # 输出完成后换行


if __name__ == "__main__":
    import asyncio
    asyncio.run(run())
