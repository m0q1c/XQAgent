"""
XQAgent - Agent 核心循环
GenericAgent 的轻量思路 + CowAgent 的协议处理
基于 OpenAI 兼容 API 的 function calling
"""
import json, os, time, traceback, threading
from typing import Generator, Optional
import urllib.request


class LLMClient:
    """OpenAI 兼容 API 客户端，支持流式 function calling"""

    def __init__(self, model: str, api_key: str = "", base_url: str = "https://api.openai.com/v1"):
        self.model = model
        self.api_key = api_key
        self.base_url = base_url.rstrip("/")
        self.history: list = []

    def chat(self, messages: list, tools: list = None, stream: bool = True) -> Generator[dict, None, None]:
        """流式对话，yield 事件"""
        body = {"model": self.model, "messages": messages, "stream": stream}
        if tools:
            body["tools"] = tools

        req = urllib.request.Request(
            f"{self.base_url}/chat/completions",
            data=json.dumps(body).encode("utf-8"),
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Bearer {self.api_key}",
            },
            method="POST"
        )

        try:
            resp = urllib.request.urlopen(req, timeout=120)
        except urllib.error.HTTPError as e:
            err_body = e.read().decode("utf-8", errors="replace")
            yield {"type": "error", "content": f"HTTP {e.code}: {err_body[:200]}"}
            return
        except Exception as e:
            yield {"type": "error", "content": str(e)}
            return

        content_parts = []
        tool_calls_acc = {}

        if stream:
            while True:
                line = resp.readline()
                if not line:
                    break
                line = line.decode("utf-8", errors="replace").strip()
                if not line.startswith("data:"):
                    continue
                json_str = line[5:].strip()
                if json_str == "[DONE]":
                    break
                try:
                    chunk = json.loads(json_str)
                except json.JSONDecodeError:
                    continue
                choices = chunk.get("choices", [])
                if not choices:
                    continue
                delta = choices[0].get("delta", {})
                # Text
                if delta.get("content"):
                    content_parts.append(delta["content"])
                    yield {"type": "delta", "content": delta["content"]}
                # Tool calls
                if delta.get("tool_calls"):
                    for tc in delta["tool_calls"]:
                        idx = tc.get("index", 0)
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc.get("id"):
                            tool_calls_acc[idx]["id"] = tc["id"]
                        if tc.get("function"):
                            fn = tc["function"]
                            if fn.get("name"):
                                tool_calls_acc[idx]["name"] = fn["name"]
                            if fn.get("arguments"):
                                tool_calls_acc[idx]["arguments"] += fn["arguments"]

            final_tool_calls = []
            for idx in sorted(tool_calls_acc.keys()):
                tc = tool_calls_acc[idx]
                try:
                    args = json.loads(tc["arguments"]) if tc["arguments"] else {}
                except json.JSONDecodeError:
                    args = {}
                final_tool_calls.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["name"], "arguments": json.dumps(args)}
                })
            yield {"type": "done", "content": "".join(content_parts), "tool_calls": final_tool_calls}
        else:
            body["stream"] = False
            data = json.dumps(body).encode("utf-8")
            req.data = data
            try:
                resp = urllib.request.urlopen(req, timeout=120)
            except Exception as e:
                yield {"type": "error", "content": str(e)}
                return
            result = json.loads(resp.read().decode("utf-8"))
            choice = result.get("choices", [{}])[0]
            msg = choice.get("message", {})
            msg_tcs = msg.get("tool_calls", [])
            final_tcs = []
            for tc in msg_tcs:
                try:
                    args = json.loads(tc["function"]["arguments"]) if tc["function"].get("arguments") else {}
                except json.JSONDecodeError:
                    args = {}
                final_tcs.append({
                    "id": tc["id"],
                    "type": "function",
                    "function": {"name": tc["function"]["name"], "arguments": json.dumps(args)}
                })
            yield {"type": "done", "content": msg.get("content") or "", "tool_calls": final_tcs}


class Agent:
    """Think → Act → Observe 循环"""

    def __init__(self, tools: list, system_prompt: str = "", max_turns: int = 30):
        self.tools = list(tools)
        self.system_prompt = system_prompt
        self.max_turns = max_turns
        self.tool_map = {t["function"]["name"]: t for t in self.tools}
        self.history = []
        self._abort = False
        self.is_running = False

    def reset(self):
        self.history = []

    def abort(self):
        self._abort = True
        self.is_running = False

    def _get_messages(self):
        msgs = []
        if self.system_prompt:
            msgs.append({"role": "system", "content": self.system_prompt})
        msgs.extend(self.history)
        return msgs

    def run(self, llm: LLMClient, prompt: str, images: list = None) -> Generator[dict, None, None]:
        """运行 agent 循环，yield 事件"""
        self._abort = False
        self.is_running = True
        user_content = prompt
        if images:
            parts = [{"type": "text", "text": prompt}]
            parts.extend(images)
            user_content = parts
        self.history.append({"role": "user", "content": user_content})

        full_response = ""
        turn = 0

        while turn < self.max_turns and not self._abort:
            turn += 1
            messages = self._get_messages()
            tool_calls_in_turn = []

            for event in llm.chat(messages, tools=self.tools, stream=True):
                if self._abort:
                    break
                if event["type"] == "error":
                    yield event
                    break
                elif event["type"] == "delta":
                    full_response += event["content"]
                    yield {"type": "text", "content": event["content"]}
                elif event["type"] == "done":
                    if event.get("tool_calls"):
                        assistant_msg = {"role": "assistant", "content": event["content"] or ""}
                        for tc in event["tool_calls"]:
                            assistant_msg.setdefault("tool_calls", []).append(tc)
                            tool_calls_in_turn.append(tc)
                        self.history.append(assistant_msg)

                        for tc in tool_calls_in_turn:
                            if self._abort:
                                break
                            name = tc["function"]["name"]
                            try:
                                args = json.loads(tc["function"]["arguments"])
                            except json.JSONDecodeError:
                                args = {}
                            yield {"type": "tool_call", "name": name, "args": args, "tool_call_id": tc["id"]}
                            # 工具执行可能耗时较长（如 search_files），用线程执行 + 周期心跳
                            _tool_result = [None]
                            _tool_done = threading.Event()
                            def _run_tool():
                                try:
                                    _tool_result[0] = execute_tool(name, args)
                                except Exception as e:
                                    _tool_result[0] = f"工具 {name} 执行失败: {e}"
                                _tool_done.set()
                            t = threading.Thread(target=_run_tool, daemon=True)
                            t.start()
                            while not _tool_done.wait(timeout=10):
                                if self._abort:
                                    _tool_result[0] = "工具调用已中断"
                                    break
                                yield {"type": "keepalive"}
                            result = _tool_result[0] or ""
                            yield {"type": "tool_result", "name": name, "result": str(result)[:4000], "tool_call_id": tc["id"]}
                            self.history.append({
                                "role": "tool",
                                "content": str(result)[:8000],
                                "tool_call_id": tc["id"]
                            })
                        if tool_calls_in_turn and not self._abort:
                            full_response = ""
                            continue
                    else:
                        self.history.append({"role": "assistant", "content": event["content"] or ""})

            if not tool_calls_in_turn:
                break

        self.is_running = False
        yield {"type": "done", "content": full_response}


def execute_tool(name: str, args: dict) -> str:
    """执行工具，供 agent 循环调用"""
    from tools import execute
    return execute(name, args)


def build_system_prompt() -> str:
    prompt = """你是一个能调用工具的 AI 助手。

## 回复风格
- 自然、直接，像朋友聊天一样
- **不要自我介绍**，直接回答用户的问题
- 用户问什么答什么，别多余铺垫
- 使用工具时先默默执行，执行完直接给结果，不需要汇报过程
- 使用与用户相同的语言回复

## 工作方式
- 根据用户请求判断是否需要调用工具
- 可用工具：read_file, write_file, run_shell, list_files, web_fetch, search_files, get_weather, list_skills, use_skill, read_memory, write_memory, search_memory
- 只能调用上述工具，不要编造不存在的工具名
- 遇到错误分析原因、重试或告知用户

## 记忆系统（必须主动使用）
⚠️ **以下行为是强制性要求，不是建议：**

### 每个对话轮次
- 如果发现用户透露了**偏好、习惯、说话风格、常用路径、项目约定、工作方式**等信息，必须立即用 `write_memory(layer="L2", content=...)` 写入 L2 事实层
- 格式示例：`write_memory(layer="L2", content="用户习惯：说话简洁，偏好表格输出")`
- **不要问用户"要不要我记住"**，直接记住

### 需要记住的内容（不限于此）
- 用户说话风格（简洁/详细/随意/正式）
- 用户对你的称呼偏好
- 用户反复提到的项目、路径、工具
- 用户的工作习惯、常用命令
- 用户明确表达的任何偏好
- 任何你发现的对未来对话有帮助的信息

### 对话开始时
- 自动调用 `read_memory(layer="L1")` 和 `read_memory(layer="L2")` 回忆已记住的信息
- 根据 L1 索引，按需读取相关 L3 记录

### 层级说明
- L1 索引：记录关键词到各层文件的映射（≤30行）
- L2 事实：存储用户偏好、习惯、配置等跨会话持久信息
- L3 记录：详细的项目笔记、技术方案、避坑指南（按文件名组织）
- L4 会话摘要：历史对话摘要（自动生成），新对话开始时会自动注入最近 3 条

## 技能系统
- 使用 `list_skills` 查看有哪些可用技能
- 使用 `use_skill(name)` 按需加载技能，会返回该技能的执行指南
- 加载后按照指南执行，不需要额外解释
"""

    # 注入持久人设（从 config.json 读取）
    try:
        _cfg_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "config.json")
        if os.path.isfile(_cfg_path):
            with open(_cfg_path, "r", encoding="utf-8") as _f:
                _cfg_data = json.load(_f)
            _persona = _cfg_data.get("persona", "").strip()
            if _persona:
                prompt = f"{_persona}\n\n{prompt}"
    except Exception:
        pass

    # 追加技能索引
    try:
        from skill_loader import get_skill_index_prompt
        skill_part = get_skill_index_prompt()
        if skill_part:
            prompt += "\n\n" + skill_part
    except Exception:
        pass
    prompt += f"\n当前时间: {time.strftime('%Y-%m-%d %H:%M:%S %A')}"

    # 注入记忆上下文（排除纯空文件/仅注释头）
    try:
        from memory import read_layer
        l1 = read_layer("L1")
        l2 = read_layer("L2")
        l1_lines = [ln for ln in l1.split("\n") if ln.strip() and not ln.startswith("#")]
        l2_lines = [ln for ln in l2.split("\n") if ln.strip() and not ln.startswith("#")]
        if l1_lines:
            prompt += f"\n\n## 记忆索引 (L1)\n" + "\n".join(l1_lines)
        if l2_lines:
            prompt += f"\n\n## 事实记忆 (L2)\n" + "\n".join(l2_lines)
        # L4 会话摘要（最近 3 条）
        try:
            l4 = read_layer("L4")
            l4_lines = [ln for ln in l4.split("\n---") if ln.strip()]
            if l4_lines:
                prompt += f"\n\n## 近期对话摘要 (L4)\n"
                for entry in l4_lines[-3:]:
                    prompt += entry.strip() + "\n---\n"
        except Exception:
            pass
    except Exception:
        pass

    return prompt
