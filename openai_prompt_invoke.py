#!/usr/bin/python3
# --*-- coding: utf-8 --*--
# @Author: gitsilence
# @Time: 2025/3/18 15:59

from openai import OpenAI
from dotenv import load_dotenv
import os
from mcp import ClientSession, StdioServerParameters, types
from mcp.client.stdio import stdio_client
import sys
from textwrap import dedent
import json
import re


server_params = StdioServerParameters(
    command="/Users/gitsilence/miniforge3/envs/machine_learning/bin/python",
    args=["/Users/gitsilence/PycharmProjects/hot-topic-mcp/main.py"]
)

load_dotenv(".env")
client = OpenAI(api_key=os.environ.get("OPENAI_API_KEY"), base_url=os.environ.get("OPENAI_API_BASE"))

SYSTEM_PROMPT = """
# 角色
你是一个智能助手，可以根据问题选择最合适的工具进行处理。请严格按照以下要求响应：

## 可用工具列表
%s

## 响应要求
1. 仔细分析用户问题是否需要使用工具
2. 必须使用以下JSON格式响应：
{
    "reasoning": "思考过程分析", 
    "action": {
        "type": "tool_call" | "direct_answer",
        "tool_name": "工具名称（可选）",
        "parameters": {参数键值对（可选）}
    }
}

## 工具详细信息
按此格式描述每个工具：
%s

## 响应示例
示例1：
用户：北京现在气温多少度？
{
    "reasoning": "用户询问城市天气，需要调用天气查询工具",
    "action": {
        "type": "tool_call",
        "tool_name": "get_weather",
        "parameters": {"city": "北京"}
    }
}

示例2：
用户：帮我计算(3+5)*2的值
{
    "reasoning": "需要进行数学计算，调用计算器工具",
    "action": {
        "type": "tool_call",
        "tool_name": "calculator",
        "parameters": {"expression": "(3+5)*2"}
    }
}

示例3：
用户：你好吗？
{
    "reasoning": "问候不需要使用工具",
    "action": {
        "type": "direct_answer"
    }
}

## 当前用户问题
%s

请严格遵循上述格式，不要添加任何额外内容！
"""


def extract_json(text: str, trigger: str = "</think>") -> dict:
    json_content = None
    try:
        # Locate trigger and extract content
        if trigger in text:
            start_idx = text.index(trigger) + len(trigger)
            json_content = text[start_idx:].strip()
        else:
            json_content = text
        # Remove code block markers
        json_content = json_content.lstrip("```json").rstrip("```").strip()

        # Handle escaped newlines if needed
        json_content = json_content.replace(r"\n", "")

        return json.loads(json_content)

    except ValueError as e:
        raise ValueError(f"Trigger '{trigger}' not found in text") from e
    except json.JSONDecodeError as e:
        print(f"Invalid JSON content: {json_content}")
        raise


async def main():
    print("欢迎使用基于OpenAI的聊天机器人！输入'退出'结束对话。")

    # 保存对话历史
    messages = [
        {"role": "system", "content": "你是一个有帮助的助手，你可以通过上下文内容来回答用户的问题"}
    ]
    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            # 初始化
            print(await session.initialize())
            tools_ori = await session.list_tools()
            tools_list_str = "\n".join([f"- {tool.name}" for tool in tools_ori.tools])
            tools_list_detail = "\n".join([dedent(f"""
                <tool>
                名称：{tool.name}
                描述：{tool.description}
                参数格式：
                {tool.inputSchema}
                </tool>
            """) for tool in tools_ori.tools])
            while True:
                # print(tools)
                user_input = input("\n用户: ")
                if user_input.lower() in ['退出', 'exit', 'quit']:
                    print("再见！")
                    break
                prompt = SYSTEM_PROMPT % (tools_list_str, tools_list_detail, user_input)
                print(prompt)
                # 添加用户消息到历史
                # messages.append({"role": "user", "content": user_input})

                # 调用OpenAI API（第一次调用不使用流式输出）
                response = client.chat.completions.create(
                    model=os.environ.get("CHAT_MODEL"),
                    messages=[{"role": "system", "content": prompt}, {"role": "user", "content": user_input}],
                    # 不使用stream=True
                )
                response_message = response.choices[0].message
                print(response_message)
                try:
                    json_data = extract_json(response_message.content)
                    print("json_data:", json_data)
                    if not json_data:
                        json_data = json.load(response_message.content)
                    # 使用正则表达式查找JSON部分
                    # 检查是否需要调用工具
                    if "direct_answer" != json_data.get("action").get("type"):
                        # 处理工具调用
                        print("\n[系统] 检测到工具调用，正在处理...")
                        function_name = json_data.get("action").get("tool_name")
                        function_args = json_data.get("action").get("parameters")

                        # 处理每个工具调用
                        # tool_calls=[ChatCompletionMessageToolCall(id='call_6ffjtt37', function=Function(arguments='{"location":"杭州"}', name='get_current_weather'), type='function', index=0)])
                        print(f"[系统] 调用函数: {function_name}({function_args})")

                        function_response = await session.call_tool(function_name, function_args)
                        response_str_list = [resp.text for resp in function_response.content]
                        print(f"[系统] 函数调用结果: {response_str_list}")
                        # 调用相应的函数
                        # 将函数调用结果添加到消息历史
                        messages.append({
                            "role": "assistant",
                            "name": function_name,
                            "content": json.dumps(response_str_list, ensure_ascii=False)
                        })

                        # 再次调用API获取基于工具结果的回复（流式输出）
                        print("\n[系统] 处理完成，生成最终回复...")
                        sys.stdout.write("助手: ")
                except:
                    pass
                messages.append({"role": "user", "content": user_input})
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
