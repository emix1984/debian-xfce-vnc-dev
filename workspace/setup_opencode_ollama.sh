#!/bin/bash
# setup_opencode_ollama.sh
# 配置 opencode 连接远程 Ollama 服务（100.102.149.107:11434）
# 并导入所有远程模型到 opencode 配置中
#
# 用法: bash setup_opencode_ollama.sh

set -euo pipefail

OLLAMA_HOST="100.102.149.107"
OLLAMA_PORT="11434"
OLLAMA_BASE_URL="http://${OLLAMA_HOST}:${OLLAMA_PORT}"
OPENCODE_CONFIG_DIR="$HOME/.config/opencode"
OPENCODE_CONFIG="$OPENCODE_CONFIG_DIR/opencode.json"

echo "========================================="
echo "  OpenCode 远程 Ollama 配置脚本"
echo "========================================="

# 1. 测试远程 Ollama 连接
echo ""
echo "[1/5] 测试远程 Ollama 连接..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "${OLLAMA_BASE_URL}/api/tags" || echo "000")
if [ "$HTTP_STATUS" != "200" ]; then
    echo "✗ 无法连接到远程 Ollama: ${OLLAMA_BASE_URL} (HTTP $HTTP_STATUS)"
    echo "  请检查:"
    echo "  1. 远程机器是否运行 Ollama 服务"
    echo "  2. Ollama 是否配置为监听 0.0.0.0（OLLAMA_HOST=0.0.0.0）"
    echo "  3. 防火墙是否放行 ${OLLAMA_PORT} 端口"
    exit 1
fi
echo "✓ 连接成功: ${OLLAMA_BASE_URL}"

# 2. 获取远程模型列表
echo ""
echo "[2/5] 获取远程 Ollama 上安装的模型..."
MODELS_JSON=$(curl -s --connect-timeout 10 "${OLLAMA_BASE_URL}/api/tags")
if [ -z "$MODELS_JSON" ]; then
    echo "✗ 无法获取模型列表"
    exit 1
fi

# 解析模型名称
MODEL_NAMES=$(printf '%s' "$MODELS_JSON" | python3 -c '
import json, sys
data = json.load(sys.stdin)
for m in data.get("models", []):
    name = m.get("name", "")
    if name:
        print(name)
')

if [ -z "$MODEL_NAMES" ]; then
    echo "✗ 远程 Ollama 上没有安装任何模型"
    exit 1
fi

MODEL_COUNT=$(echo "$MODEL_NAMES" | wc -l)
echo "✓ 发现 ${MODEL_COUNT} 个模型:"
echo "$MODEL_NAMES" | while IFS= read -r m; do
    echo "  - $m"
done

# 3. 生成 opencode 配置
echo ""
echo "[3/5] 生成 opencode 配置文件..."
mkdir -p "$OPENCODE_CONFIG_DIR"

python3 - "$OPENCODE_CONFIG" "$OLLAMA_HOST" "$OLLAMA_PORT" << 'PYEOF'
import json, os, sys, re

config_path = sys.argv[1]
host = sys.argv[2]
port = sys.argv[3]
base_url = f"http://{host}:{port}/v1"

# 从 Ollama API 获取模型详情
import subprocess, json as j
result = subprocess.run(
    ["curl", "-s", f"http://{host}:{port}/api/tags"],
    capture_output=True, text=True
)
data = j.loads(result.stdout)
model_list = []
for m in data.get("models", []):
    name = m.get("name", "")
    details = m.get("details", {})
    family = details.get("family", "")
    param_size = details.get("parameter_size", "")
    quantization = details.get("quantization_level", "")
    model_list.append({
        "name": name,
        "family": family,
        "param_size": param_size,
        "quantization": quantization
    })

# 加载已有配置（如有）
config = {}
if os.path.exists(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        try:
            text = f.read()
            text = re.sub(r"//.*", "", text)
            config = j.loads(text)
        except Exception as e:
            print(f"  警告: 无法解析现有配置 ({e})，将创建新配置")

if "$schema" not in config:
    config["$schema"] = "https://opencode.ai/config.json"

# 构建 provider 配置
models = {}
for mdl in model_list:
    name = mdl["name"]
    # 生成配置中的键名: 去掉标签版本号，特殊字符转下划线
    key = re.sub(r":.+$", "", name)
    key = re.sub(r"[^0-9a-zA-Z_]+", "_", key).strip("_").lower()
    if not key:
        key = "model"

    entry = {"name": name}

    # 判断模型特性
    lower_name = name.lower()
    lower_family = mdl.get("family", "").lower()

    # Reasoning: qwen3 系列有 reasoning_content 输出
    if "qwen3" in lower_name or "qwq" in lower_name:
        entry["reasoning"] = True
        entry["interleaved"] = {"field": "reasoning_content"}

    # Tool call: qwen2.5 和 qwen3 系列大部分支持
    if "qwen2.5" in lower_name or "qwen3" in lower_name:
        entry["tool_call"] = True

    # 上下文长度估计
    limit = {"output": 8192}
    param_size = (mdl.get("param_size") or "").lower()
    if param_size.startswith("32") or param_size.startswith("30"):
        limit["context"] = 131072
    elif "qwen3" in lower_name:
        limit["context"] = 131072
    else:
        limit["context"] = 32768
    entry["limit"] = limit

    models[key] = entry

# 已去重，确保键唯一
seen = set()
deduped = {}
for k, v in models.items():
    if k in seen:
        suffix = 2
        while f"{k}_{suffix}" in seen:
            suffix += 1
        k = f"{k}_{suffix}"
    seen.add(k)
    deduped[k] = v
models = deduped

# 设置 ollama-remote provider
config["provider"] = config.get("provider", {})
config["provider"]["ollama-remote"] = {
    "npm": "@ai-sdk/openai-compatible",
    "name": f"Ollama (remote: {host}:{port})",
    "options": {
        "baseURL": base_url
    },
    "models": models
}

# 设置默认模型为 qwen3-coder（如存在）
if "qwen3_coder" in models:
    config["model"] = "ollama-remote/qwen3_coder"
elif "qwen2_5_coder" in models:
    config["model"] = "ollama-remote/qwen2_5_coder"
elif models:
    first_key = next(iter(models))
    config["model"] = f"ollama-remote/{first_key}"

with open(config_path, "w", encoding="utf-8") as f:
    j.dump(config, f, indent=2, ensure_ascii=False)

print(f"\n  配置文件写入: {config_path}")
print(f"  默认模型: {config.get('model', '未设置')}")
print(f"  已导入 {len(models)} 个模型:")
for key, entry in models.items():
    features = []
    if entry.get("reasoning"): features.append("reasoning")
    if entry.get("tool_call"): features.append("tool_call")
    feat_str = f" ({', '.join(features)})" if features else ""
    print(f"    - {entry['name']}{feat_str}")

PYEOF

# 4. 验证配置
echo ""
echo "[4/5] 验证配置..."
if [ -f "$OPENCODE_CONFIG" ]; then
    echo "✓ 配置文件已生成: $OPENCODE_CONFIG"
else
    echo "✗ 配置文件生成失败"
    exit 1
fi

# 5. 重启 opencode Web UI
echo ""
echo "[5/5] 重启 opencode Web UI..."

OPENCODE_PATH="${HOME}/.opencode/bin/opencode"
LOG_DIR="${LOG_DIR:-/var/log}"
WEB_PORT="${OPENCODE_WEB_PORT:-4096}"

if [ ! -f "$OPENCODE_PATH" ] && ! command -v opencode &>/dev/null; then
    echo "  ⚠ opencode 未安装或不在 PATH 中，跳过重启"
    echo "  请手动重启 opencode 后使用新配置"
else
    # 确保 PATH 包含 opencode
    export PATH="${HOME}/.opencode/bin:${PATH}"

    # 杀掉已有的 tmux opencode 会话
    if tmux -L opencode has-session -t opencode 2>/dev/null; then
        echo "  - 停止已有 opencode 服务（tmux session: opencode）..."
        tmux -L opencode kill-session -t opencode
        sleep 1
    fi

    # 启动新的 opencode web 服务
    echo "  - 启动 opencode Web UI (端口 ${WEB_PORT})..."
    tmux -L opencode new-session -d -s opencode "opencode web --hostname 0.0.0.0 --port ${WEB_PORT} 2>&1 | tee ${LOG_DIR}/opencode_web.log"
    echo "  ✓ opencode Web UI 已在 tmux session 'opencode' 中启动"
    echo "  - 查看日志: tail -f ${LOG_DIR}/opencode_web.log"
    echo "  - 附加会话: tmux attach -t opencode"
fi

echo ""
echo "========================================="
echo "  配置完成！"
echo "========================================="
echo ""
echo "配置文件中已导入以下模型:"
echo "$MODEL_NAMES" | while IFS= read -r m; do
    echo "    - $m"
done
echo ""
echo "在 opencode 中可通过 ollama-remote/<模型键名> 引用模型"
echo "例如: ollama-remote/qwen3_coder"
