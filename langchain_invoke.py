from langchain_openai import ChatOpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
import os
from dotenv import load_dotenv
load_dotenv(".env")

model = ChatOpenAI(
    model=os.environ["CHAT_MODEL"],
    base_url=os.environ["OPENAI_API_BASE"],
    streaming=True
)

server_params = StdioServerParameters(
    command="/Users/gitsilence/miniforge3/envs/machine_learning/bin/python",
    args=["/Users/gitsilence/PycharmProjects/hot-topic-mcp/main.py"]
)
async def run():
    async with stdio_client(server_params) as (read_stream, write_stream):
        async with ClientSession(read_stream=read_stream, write_stream=write_stream) as session:
            await session.initialize()

            # Get tools
            tools = await load_mcp_tools(session)

            # Create the agent
            agent = create_react_agent(model, tools)
            
            # 创建交互式聊天循环
            print("欢迎使用AI助手，请输入您的问题（输入'退出'结束对话）：")
            while True:
                user_input = input("用户: ")
                if user_input.lower() in ["退出", "exit", "quit"]:
                    print("感谢使用，再见！")
                    break
                
                print("AI思考中...")
                # 使用流式输出替代一次性输出
                print("AI: ", end="", flush=True)
                async for chunk in agent.astream({"messages": user_input}):
                    # print("chunk: ", chunk)
                    # message = chunk["messages"][:-1]
                    # 从正确的嵌套结构中提取消息内容
                    if "agent" in chunk and "messages" in chunk["agent"]:
                        messages = chunk["agent"]["messages"]
                        if messages and hasattr(messages[-1], "content"):
                            content_chunk = messages[-1].content
                            if content_chunk:
                                print(content_chunk, end="", flush=True)
                print()  # 输出完成后换行

if __name__ == '__main__':
    import asyncio
    asyncio.run(run())
