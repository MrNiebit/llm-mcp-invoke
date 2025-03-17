import os
import json
from datetime import datetime
from openai import OpenAI
from dotenv import load_dotenv
import logging
import sys
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client

server_params = StdioServerParameters(
    command="/Users/gitsilence/miniforge3/envs/machine_learning/bin/python",
    args=["/Users/gitsilence/PycharmProjects/hot-topic-mcp/main.py"]
)

async def call_tool(name, args):
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化
            print(await session.initialize())
            result = await session.list_tools()
            print(result)

            result = await session.call_tool(name="sina_weibo_hot_topic", arguments={"top": 5, "type": "all"})
            print(result)
    pass


# 设置OpenAI的调试日志
# logging.basicConfig(level=logging.DEBUG)
load_dotenv(".env")

# 初始化OpenAI客户端
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), base_url=os.environ.get("OPENAI_API_BASE"))

# 定义一个示例工具函数
def get_current_weather(location):
    """获取指定位置的当前天气"""
    # 这里应该是实际的天气API调用
    # 为了演示，返回模拟数据
    return {
        "location": location,
        "temperature": "22°C",
        "forecast": ["sunny", "windy"],
        "timestamp": datetime.now().isoformat()
    }

# 定义可用的函数
available_functions = {
    "get_current_weather": get_current_weather
}


def stream_output(text):
    """流式输出文本"""
    for char in text:
        sys.stdout.write(char)
        sys.stdout.flush()
    sys.stdout.write('\n')

async def build_openai_tools(tools_ori):
    tools = []
    for tool in tools_ori:
        tools.append({
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description,
                "parameters": tool.inputSchema
            }
        })
    return tools

async def main():
    print("欢迎使用基于OpenAI的聊天机器人！输入'退出'结束对话。")
    
    # 保存对话历史
    messages = [
        {"role": "system", "content": "你是一个有帮助的助手，可以回答问题并调用工具获取信息。"}
    ]
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化
            print(await session.initialize())
            tools_ori = await session.list_tools()
            # print(tools_ori.tools)
            tools = await build_openai_tools(tools_ori.tools)
            while True:
                # print(tools)
                user_input = input("\n用户: ")
                if user_input.lower() in ['退出', 'exit', 'quit']:
                    print("再见！")
                    break
                
                # 添加用户消息到历史
                messages.append({"role": "user", "content": user_input})
                
                # 调用OpenAI API（第一次调用不使用流式输出）
                response = client.chat.completions.create(
                    model=os.environ.get("CHAT_MODEL"),
                    messages=messages,
                    tools=tools,
                    tool_choice="auto",
                    # 不使用stream=True
                )
                # print(response)
                response_message = response.choices[0].message
                
                # 检查是否需要调用工具
                if response_message.tool_calls:
                    # 处理工具调用
                    print("\n[系统] 检测到工具调用，正在处理...")
                    
                    # 将AI回复添加到消息历史
                    messages.append(response_message)
                    
                    # 处理每个工具调用
                    # tool_calls=[ChatCompletionMessageToolCall(id='call_6ffjtt37', function=Function(arguments='{"location":"杭州"}', name='get_current_weather'), type='function', index=0)])
                    for tool_call in response_message.tool_calls:
                        function_name = tool_call.function.name
                        function_args = json.loads(tool_call.function.arguments)
                        
                        print(f"[系统] 调用函数: {function_name}({function_args})")
                        
                        function_response = await session.call_tool(function_name, function_args)
                        response_str_list = [resp.text for resp in function_response.content]
                        print(f"[系统] 函数调用结果: {response_str_list}")
                        # 调用相应的函数
                        # 将函数调用结果添加到消息历史
                        messages.append({
                            "tool_call_id": tool_call.id,
                            "role": "tool",
                            "name": function_name,
                            "content": json.dumps(response_str_list, ensure_ascii=False)
                        })
                    
                    # 再次调用API获取基于工具结果的回复（流式输出）
                    print("\n[系统] 处理完成，生成最终回复...")
                    sys.stdout.write("助手: ")
                    
                second_stream = client.chat.completions.create(
                    model=os.environ.get("CHAT_MODEL"),
                    messages=messages,
                    stream=True
                )
                
                second_full_response = ""
                for chunk in second_stream:
                    if chunk.choices[0].delta.content:
                        content_chunk = chunk.choices[0].delta.content
                        second_full_response += content_chunk
                        sys.stdout.write(content_chunk)
                        sys.stdout.flush()
                
                sys.stdout.write('\n')
                
                # 将最终回复添加到消息历史
                messages.append({"role": "assistant", "content": second_full_response})


if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
