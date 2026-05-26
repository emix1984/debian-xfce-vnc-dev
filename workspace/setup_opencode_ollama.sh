#!/usr/bin/env bash
# setup_opencode_ollama.sh
# 配置 OpenCode 连接远程 Ollama 服务（100.102.149.107:11434）并导入模型
# 用法: bash setup_opencode_ollama.sh

set -euo pipefail

# ---------- 依赖检查 ----------
for cmd in curl jq python3; do
  if ! command -v "$cmd" >/dev/null 2>&1; then
    echo "✗ 缺少必需命令: $cmd，请先在容器中安装 (apt-get update && apt-get install -y $cmd)"
    exit 1
  fi
done

# ---------- 配置变量 ----------
OLLAMA_HOST="100.102.149.107"
OLLAMA_PORT="11434"
OLLAMA_BASE_URL="http://${OLLAMA_HOST}:${OLLAMA_PORT}"
OPENCODE_CONFIG_DIR="$HOME/.config/opencode"
OPENCODE_CONFIG="$OPENCODE_CONFIG_DIR/opencode.json"

echo "========================================="
echo "  OpenCode 远程 Ollama 配置脚本"
echo "========================================="

# ---------- 1. 测试 Ollama 连接 ----------
echo ""
echo "[1/5] 测试远程 Ollama 连接..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" --connect-timeout 5 "${OLLAMA_BASE_URL}/api/tags" || echo "000")
if [ "$HTTP_STATUS" != "200" ]; then
  echo "✗ 无法连接到远程 Ollama: ${OLLAMA_BASE_URL} (HTTP $HTTP_STATUS)"
  echo "  请检查:"
  echo "    1. 远程机器是否运行 Ollama 服务"
  echo "    2. Ollama 是否监听 0.0.0.0（OLLAMA_HOST=0.0.0.0）"
  echo "    3. 防火墙是否放行 ${OLLAMA_PORT} 端口"
  exit 1
fi
echo "✓ 连接成功: ${OLLAMA_BASE_URL}"

# ---------- 2. 获取模型列表 ----------
echo ""
echo "[2/5] 获取远程 Ollama 上安装的模型..."
MODELS_JSON=$(curl -s --connect-timeout 10 "${OLLAMA_BASE_URL}/api/tags")
# 验证返回是否为有效 JSON（避免空或非 JSON 响应导致 json.loads 崩溃）
if [ -z "$MODELS_JSON" ]; then
  echo "✗ 无法获取模型列表（空响应）"
  exit 1
fi
if ! echo "$MODELS_JSON" | jq . > /dev/null 2>&1; then
  echo "✗ Ollama 返回非 JSON 数据，可能是网络错误或服务异常"
  exit 1
fi

# 解析模型名称（完整名称包含标签）
MODEL_NAMES=$(echo "$MODELS_JSON" | jq -r '.models[].name')

if [ -z "$MODEL_NAMES" ]; then
  echo "✗ 远程 Ollama 上没有检测到任何模型（解析结果为空）"
  exit 1
fi

MODEL_COUNT=$(echo "$MODEL_NAMES" | wc -l)
echo "✓ 发现 ${MODEL_COUNT} 个模型:"
while IFS= read -r m; do
  echo "  - $m"
done <<< "$MODEL_NAMES"

# ---------- 3. 生成 OpenCode 配置 ----------
echo ""
echo "[3/5] 生成 OpenCode 配置文件..."
mkdir -p "$OPENCODE_CONFIG_DIR"

python3 - "$OPENCODE_CONFIG" "$OLLAMA_HOST" "$OLLAMA_PORT" <<'PYEOF'
import json, os, sys, re, subprocess
config_path, host, port = sys.argv[1:4]
base_url = f"http://{host}:{port}/v1"
# 从 Ollama 获取模型详情
result = subprocess.run(["curl", "-s", f"http://{host}:{port}/api/tags"], capture_output=True, text=True)
raw = result.stdout
try:
    data = json.loads(raw)
except Exception as e:
    print(f"✗ 读取 Ollama 模型信息失败: {e}")
    sys.exit(1)
model_list = []
for m in data.get('models', []):
    name = m.get('name', '')
    details = m.get('details', {})
    model_list.append({
        'name': name,
        'family': details.get('family', ''),
        'param_size': details.get('parameter_size', ''),
        'quantization': details.get('quantization_level', ''),
    })
# 加载已有配置（如果有）
config = {}
if os.path.exists(config_path):
    try:
        with open(config_path, 'r', encoding='utf-8') as f:
            # 去掉可能的注释
            text = re.sub(r"//.*", "", f.read())
            config = json.loads(text)
    except Exception as e:
        print(f"  警告: 读取现有配置失败 ({e})，将重新创建配置")
if '$schema' not in config:
    config['$schema'] = 'https://opencode.ai/config.json'
# 构建模型映射，保留原始名称（去除标签）作为 key，允许 '-' '.'
models = {}
for mdl in model_list:
    name = mdl['name']
    # 去掉冒号后面的标签（如 :latest）
    key = re.sub(r":.+$", "", name)
    # 将非法字符统一替换为下划线，保留字母数字、点、横杠
    key = re.sub(r"[^0-9A-Za-z_.-]+", "_", key)
    key = key.strip('_').lower()
    if not key:
        key = 'model'
    entry = {'name': name}
    lower_name = name.lower()
    # Reasoning
    if 'qwen3' in lower_name or 'qwq' in lower_name:
        entry['reasoning'] = True
        entry['interleaved'] = {'field': 'reasoning_content'}
    # Tool call
    if 'qwen2.5' in lower_name or 'qwen3' in lower_name:
        entry['tool_call'] = True
    # Context limit
    limit = {'output': 8192}
    param = (mdl.get('param_size') or '').lower()
    if param.startswith('32') or param.startswith('30'):
        limit['context'] = 131072
    elif 'qwen3' in lower_name:
        limit['context'] = 131072
    else:
        limit['context'] = 32768
    entry['limit'] = limit
    models[key] = entry
# 去重（防止同名冲突）
seen = set()
unique_models = {}
for k, v in models.items():
    if k in seen:
        i = 2
        new_k = f"{k}_{i}"
        while new_k in seen:
            i += 1
            new_k = f"{k}_{i}"
        k = new_k
    seen.add(k)
    unique_models[k] = v
models = unique_models
# 写入 provider 配置
config.setdefault('provider', {})['ollama-remote'] = {
    'npm': '@ai-sdk/openai-compatible',
    'name': f'Ollama (remote: {host}:{port})',
    'options': {'baseURL': base_url},
    'models': models,
}
# 设置默认模型（优先 qwen3-coder，其次 qwen2.5-coder）
default_key = None
for cand in ['qwen3_coder', 'qwen2_5_coder']:
    if cand in models:
        default_key = cand
        break
if not default_key and models:
    default_key = next(iter(models))
if default_key:
    config['model'] = f'ollama-remote/{default_key}'
# 写回文件
with open(config_path, 'w', encoding='utf-8') as f:
    json.dump(config, f, indent=2, ensure_ascii=False)
print('\n  配置文件写入:', config_path)
print('  默认模型:', config.get('model', '未设置'))
print(f'  已导入 {len(models)} 个模型:')
for k, e in models.items():
    feats = []
    if e.get('reasoning'): feats.append('reasoning')
    if e.get('tool_call'): feats.append('tool_call')
    feat_str = f" ({', '.join(feats)})" if feats else ''
    print(f"    - {e['name']}{feat_str}")
PYEOF

# ---------- 4. 验证配置 ----------
echo ""
echo "[4/5] 验证配置..."
if [ -f "$OPENCODE_CONFIG" ]; then
  echo "✓ 配置文件已生成: $OPENCODE_CONFIG"
else
  echo "✗ 配置文件未生成，请检查脚本执行日志"
  exit 1
fi

# ---------- 5. 完成 ----------
echo ""
echo "[5/5] 完成！OpenCode 已成功配置远程 Ollama。"
