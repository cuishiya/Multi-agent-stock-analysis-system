#!/bin/bash
# 一键启动脚本：自动管理 vLLM 服务生命周期
# 用法: ./run.sh "分析平安银行(000001)"
#       ./run.sh              (交互模式)

PROJECT_DIR="/home/ubuntu/桌面/cui/面向A股市场的多 Agent 协同股票分析系统"
PYTHON="/home/ubuntu/miniconda3/envs/cui_sft/bin/python"
VLLM="/home/ubuntu/miniconda3/envs/cui_sft/bin/vllm"
MODEL_PATH="/home/ubuntu/桌面/model_download/Qwen3-8B"
VLLM_PORT=8000

cleanup() {
    echo ""
    echo "正在关闭 vLLM 服务..."
    if [ -n "$VLLM_PID" ]; then
        kill $VLLM_PID 2>/dev/null
        wait $VLLM_PID 2>/dev/null
    fi
    # 确保彻底清理
    pkill -f "vllm serve.*Qwen3-8B" 2>/dev/null
    echo "vLLM 服务已关闭，GPU 显存已释放。"
    exit 0
}

trap cleanup EXIT INT TERM

# 检查 vLLM 是否已在运行
if curl -s http://localhost:${VLLM_PORT}/v1/models 2>/dev/null | grep -q "Qwen3-8B"; then
    echo "vLLM 服务已在运行，跳过启动。"
else
    echo "正在启动 vLLM 服务（Qwen3-8B）..."
    CUDA_VISIBLE_DEVICES=0 $VLLM serve "$MODEL_PATH" \
        --served-model-name Qwen3-8B \
        --host 0.0.0.0 \
        --port ${VLLM_PORT} \
        --trust-remote-code \
        --max-model-len 8192 \
        --disable-custom-all-reduce \
        --enable-auto-tool-choice \
        --tool-call-parser hermes \
        --enable-lora \
        --max-lora-rank 16 \
        --lora-modules sentiment="${PROJECT_DIR}/qwen_sentiment_model" risk="${PROJECT_DIR}/qwen_risk_model" &
    VLLM_PID=$!

    echo "等待 vLLM 就绪..."
    for i in $(seq 1 60); do
        if curl -s http://localhost:${VLLM_PORT}/v1/models 2>/dev/null | grep -q "Qwen3-8B"; then
            echo "vLLM 服务已就绪！"
            break
        fi
        sleep 5
        echo "  等待中... ($i)"
    done
fi

# 运行主程序
echo "=========================================="
echo "启动金融分析智能体系统..."
echo "=========================================="
cd "${PROJECT_DIR}/Financial-MCP-Agent"

if [ -n "$1" ]; then
    $PYTHON -m src.main --command "$1"
else
    $PYTHON -m src.main
fi

echo ""
echo "分析完成，vLLM 服务将自动关闭。"
# cleanup 会在 EXIT trap 中自动执行
