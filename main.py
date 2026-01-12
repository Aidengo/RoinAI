from flask import Flask, request, jsonify
from flask_cors import CORS
import requests
import json

app = Flask(__name__)
CORS(app, origins="*", supports_credentials=True)

# ========== 百炼OpenAI兼容接口配置 ==========
ALIYUN_API_KEY = "sk-7a60986ab6334b928d7bf01b937aef38"  # 你的API Key
BAILIAN_COMPATIBLE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1/chat/completions"
MODEL_NAME = "qwen-turbo"

# 全局对话历史（保存所有用户+AI的对话）
conversation_history = []


def init_ai_identity():
    """服务启动时初始化AI身份，告知其名称为RoinAI"""
    global conversation_history
    # 初始化指令消息
    init_message = {
        "role": "system",
        "content": "你叫RoinAI，在后续的所有对话中，都要记住自己的名字是RoinAI，并且在合适的场景下主动提及自己的名字"
    }
    # 将初始化指令加入对话历史
    conversation_history.append(init_message)

    # 可选：发送测试消息确认AI已接收指令（如果不需要验证可注释这部分）
    test_payload = {
        "model": MODEL_NAME,
        "messages": conversation_history,
        "temperature": 0.0,
        "max_tokens": 100,
        "stream": False
    }
    headers = {
        "Authorization": f"Bearer {ALIYUN_API_KEY}",
        "Content-Type": "application/json; charset=utf-8"
    }

    try:
        response = requests.post(
            url=BAILIAN_COMPATIBLE_URL,
            headers=headers,
            data=json.dumps(test_payload, ensure_ascii=False),
            timeout=20,
            verify=False
        )
        if response.status_code == 200:
            print("✅ AI身份初始化成功，已告知其名称为RoinAI")
        else:
            print(f"⚠️ AI身份初始化请求失败，状态码：{response.status_code}")
    except Exception as e:
        print(f"⚠️ AI身份初始化时发生错误：{str(e)}")


# 启动时执行AI身份初始化
init_ai_identity()


@app.route('/api/chat', methods=['POST'])
def chat():
    # 关键修复：声明使用全局变量
    global conversation_history

    try:
        print("收到前端请求：", request.get_json())
        data = request.get_json()
        user_message = data.get('message', '').strip()

        if not user_message:
            return jsonify({"success": False, "error": "消息不能为空"}), 400

        # 1. 添加当前用户消息到历史（OpenAI格式）
        conversation_history.append({"role": "user", "content": user_message})
        print(f"当前对话历史（共{len(conversation_history)}条）：", conversation_history)

        # 2. 构造请求：传递完整的对话历史上下文
        payload = {
            "model": MODEL_NAME,
            "messages": conversation_history,  # 关键：传递所有历史消息（包含初始化指令）
            "temperature": 0.7,
            "max_tokens": 1000,
            "stream": False
        }

        headers = {
            "Authorization": f"Bearer {ALIYUN_API_KEY}",
            "Content-Type": "application/json; charset=utf-8"
        }

        # 调用百炼API
        response = requests.post(
            url=BAILIAN_COMPATIBLE_URL,
            headers=headers,
            data=json.dumps(payload, ensure_ascii=False),
            timeout=20,
            verify=False
        )

        print(f"响应状态码：{response.status_code}")

        if response.status_code != 200:
            raise Exception(f"接口调用失败：状态码{response.status_code}，响应：{response.text[:200]}")

        # 解析响应
        response_data = response.json()
        if not response_data.get("choices"):
            raise Exception(f"无回复内容：{response_data}")

        # 3. 提取AI回复并添加到历史
        ai_response = response_data["choices"][0]["message"]["content"]
        conversation_history.append({"role": "assistant", "content": ai_response})

        # 可选：限制历史长度（避免token超限），保留最近10轮对话（包含系统指令）
        if len(conversation_history) > 201:  # 10轮=20条（用户+AI各1条）+1条系统指令
            # 保留第一条系统指令，删除后面的旧消息
            conversation_history = [conversation_history[0]] + conversation_history[-200:]

        return jsonify({
            "success": True,
            "reply": ai_response,
            "history": conversation_history  # 返回完整历史（前端可选使用）
        })

    except Exception as e:
        print(f"后端错误详情：{str(e)}")
        return jsonify({
            "success": False,
            "error": f"服务调用失败：{str(e)}"
        }), 200


@app.route('/api/clear', methods=['POST'])
def clear_history():
    """清空对话历史（保留系统初始化指令）"""
    global conversation_history
    # 清空时保留第一条系统指令，只删除用户和AI的对话记录
    if conversation_history and conversation_history[0]["role"] == "system":
        conversation_history = [conversation_history[0]]
    else:
        conversation_history = []
        # 如果清空后没有系统指令，重新初始化
        init_ai_identity()
    return jsonify({
        "success": True,
        "message": "对话历史已清空（保留AI身份初始化指令）"
    }), 200


@app.route('/api/test', methods=['GET'])
def test():
    return jsonify({
        "success": True,
        "message": "后端服务正常（端口8888）",
        "history_count": len(conversation_history),  # 显示当前历史条数
        "ai_identity": conversation_history[0]["content"] if (
                    conversation_history and conversation_history[0]["role"] == "system") else "未初始化"
    }), 200


if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=8888)