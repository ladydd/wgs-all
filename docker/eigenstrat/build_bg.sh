#!/bin/bash
# 后台构建 wgs-all 镜像，写日志 + PID
# 用法:
#   bash docker/eigenstrat/build_bg.sh          # 启动后台构建
#   bash docker/eigenstrat/build_bg.sh status   # 查看状态
#   bash docker/eigenstrat/build_bg.sh log      # 跟随日志 (tail -f)
#   bash docker/eigenstrat/build_bg.sh stop     # 杀掉
#   bash docker/eigenstrat/build_bg.sh clean    # 清理 log / pid (仅在任务结束后)

set -e

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

LOG_FILE="${LOG_DIR}/wgs-all-build.log"
PID_FILE="${LOG_DIR}/wgs-all-build.pid"
DONE_FILE="${LOG_DIR}/wgs-all-build.done"

ACTION=${1:-start}

cmd_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

case "$ACTION" in
    start|"")
        if cmd_running; then
            PID=$(cat "$PID_FILE")
            echo "⚠️  已有构建进程在跑: PID=${PID}"
            echo "   查看日志: bash $0 log"
            exit 0
        fi

        rm -f "$DONE_FILE"
        echo "[$(date '+%F %T')] 启动后台构建..." | tee "$LOG_FILE"
        echo "日志: $LOG_FILE"
        echo "PID:  $PID_FILE"

        # nohup + setsid 脱离终端，把 bash 结束时的 exit code 写到 done 文件
        nohup setsid bash -c "
            set -e
            bash '${SCRIPT_DIR}/build.sh' 2>&1
            echo \"BUILD_EXIT=\$?\" > '${DONE_FILE}'
        " >> "$LOG_FILE" 2>&1 &

        BG_PID=$!
        echo $BG_PID > "$PID_FILE"
        echo "[$(date '+%F %T')] 已启动 (PID=${BG_PID})"
        echo ""
        echo "后续命令:"
        echo "  bash $0 log     # 跟随日志"
        echo "  bash $0 status  # 查看状态"
        echo "  bash $0 stop    # 终止"
        ;;

    status)
        if cmd_running; then
            PID=$(cat "$PID_FILE")
            ELAPSED=$(ps -o etime= -p "$PID" 2>/dev/null | tr -d ' ')
            echo "🟢 运行中: PID=${PID}, 已跑 ${ELAPSED}"
            echo "最近 5 行日志:"
            tail -5 "$LOG_FILE"
        elif [ -f "$DONE_FILE" ]; then
            source "$DONE_FILE"
            if [ "$BUILD_EXIT" = "0" ]; then
                echo "✅ 构建成功完成"
            else
                echo "❌ 构建失败 (exit=${BUILD_EXIT})"
            fi
            echo "最后 10 行日志:"
            tail -10 "$LOG_FILE"
        else
            echo "❓ 无运行中的构建，也无完成标记"
        fi
        ;;

    log|logs|tail)
        if [ ! -f "$LOG_FILE" ]; then
            echo "日志文件不存在: $LOG_FILE"
            exit 1
        fi
        echo "跟随日志 (Ctrl-C 退出): $LOG_FILE"
        echo "=========================================="
        tail -f "$LOG_FILE"
        ;;

    stop|kill)
        if cmd_running; then
            PID=$(cat "$PID_FILE")
            echo "终止进程组 PID=${PID}..."
            kill -TERM "-$PID" 2>/dev/null || kill "$PID" 2>/dev/null || true
            sleep 1
            if kill -0 "$PID" 2>/dev/null; then
                kill -KILL "-$PID" 2>/dev/null || kill -KILL "$PID" 2>/dev/null
            fi
            rm -f "$PID_FILE"
            echo "已终止"
        else
            echo "没有运行中的构建"
        fi
        ;;

    clean)
        if cmd_running; then
            echo "还在跑，先 stop"
            exit 1
        fi
        rm -f "$LOG_FILE" "$PID_FILE" "$DONE_FILE"
        echo "已清理"
        ;;

    *)
        echo "用法: bash $0 [start|status|log|stop|clean]"
        exit 1
        ;;
esac
