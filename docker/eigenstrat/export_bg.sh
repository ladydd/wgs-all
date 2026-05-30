#!/bin/bash
# 后台导出 wgs-all:latest → tar.gz
#
# 用法:
#   bash docker/eigenstrat/export_bg.sh          # 启动导出
#   bash docker/eigenstrat/export_bg.sh status   # 查看状态
#   bash docker/eigenstrat/export_bg.sh log      # 跟随日志
#   bash docker/eigenstrat/export_bg.sh stop     # 终止
#   bash docker/eigenstrat/export_bg.sh clean    # 清理 log/pid

set -e

IMAGE="wgs-all:latest"
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
PROJECT_DIR="$(cd "${SCRIPT_DIR}/../.." && pwd)"
LOG_DIR="${PROJECT_DIR}/logs"
mkdir -p "${LOG_DIR}"

OUTPUT_TAR="${PROJECT_DIR}/wgs-all.tar.gz"
LOG_FILE="${LOG_DIR}/wgs-all-export.log"
PID_FILE="${LOG_DIR}/wgs-all-export.pid"
DONE_FILE="${LOG_DIR}/wgs-all-export.done"

ACTION=${1:-start}

cmd_running() {
    [ -f "$PID_FILE" ] && kill -0 "$(cat "$PID_FILE")" 2>/dev/null
}

human_size() {
    local f="$1"
    [ -f "$f" ] && du -h "$f" 2>/dev/null | cut -f1 || echo "?"
}

case "$ACTION" in
    start|"")
        if cmd_running; then
            PID=$(cat "$PID_FILE")
            echo "⚠️  已有导出进程在跑: PID=${PID}"
            echo "   查看日志: bash $0 log"
            exit 0
        fi

        if ! docker image inspect "$IMAGE" >/dev/null 2>&1; then
            echo "❌ 镜像不存在: $IMAGE"
            exit 1
        fi

        # 如果已存在同名 tar，先挪走
        if [ -f "$OUTPUT_TAR" ]; then
            mv "$OUTPUT_TAR" "${OUTPUT_TAR}.$(date +%s).old"
            echo "已把旧文件挪到: ${OUTPUT_TAR}.*.old"
        fi

        rm -f "$DONE_FILE"
        echo "[$(date '+%F %T')] 启动后台导出..." | tee "$LOG_FILE"
        echo "输出: ${OUTPUT_TAR}" | tee -a "$LOG_FILE"
        echo "镜像: ${IMAGE}" | tee -a "$LOG_FILE"
        echo "" | tee -a "$LOG_FILE"

        # docker save | gzip，管道里用 pv 的话能显示进度，这里简单用
        # SIGPIPE 安全: 整个命令放一个 bash -c 里以便原子退出
        nohup setsid bash -c "
            set -e -o pipefail
            START=\$(date +%s)
            echo \"[开始 \$(date '+%T')] docker save | gzip ...\"
            docker save '${IMAGE}' | gzip -c > '${OUTPUT_TAR}'
            END=\$(date +%s)
            ELAPSED=\$((END - START))
            SIZE=\$(du -h '${OUTPUT_TAR}' | cut -f1)
            echo \"\"
            echo \"[完成 \$(date '+%T')] 耗时 \${ELAPSED}s, 大小 \${SIZE}\"
            echo \"EXPORT_EXIT=\$?\" > '${DONE_FILE}'
            echo \"ELAPSED_SEC=\${ELAPSED}\" >> '${DONE_FILE}'
            echo \"TAR_SIZE=\${SIZE}\" >> '${DONE_FILE}'
        " >> "$LOG_FILE" 2>&1 &

        BG_PID=$!
        echo $BG_PID > "$PID_FILE"
        echo "[$(date '+%F %T')] 已启动 (PID=${BG_PID})"
        echo ""
        echo "预计 5-15 分钟 (gzip CPU 瓶颈)"
        echo ""
        echo "后续命令:"
        echo "  bash $0 log     # 跟随日志"
        echo "  bash $0 status  # 查看状态和当前 tar 大小"
        echo "  bash $0 stop    # 终止"
        ;;

    status)
        if cmd_running; then
            PID=$(cat "$PID_FILE")
            ELAPSED=$(ps -o etime= -p "$PID" 2>/dev/null | tr -d ' ')
            CUR_SIZE=$(human_size "$OUTPUT_TAR")
            echo "🟢 运行中: PID=${PID}, 已跑 ${ELAPSED}"
            echo "   当前 tar 大小: ${CUR_SIZE}"
            echo ""
            echo "最近 5 行日志:"
            tail -5 "$LOG_FILE"
        elif [ -f "$DONE_FILE" ]; then
            source "$DONE_FILE"
            if [ "$EXPORT_EXIT" = "0" ]; then
                echo "✅ 导出成功"
                echo "   文件: $OUTPUT_TAR"
                echo "   大小: $(human_size "$OUTPUT_TAR")"
                [ -n "$ELAPSED_SEC" ] && echo "   耗时: ${ELAPSED_SEC}s"
                echo ""
                echo "迁移方法:"
                echo "  scp $OUTPUT_TAR user@target:/path/"
                echo "  # 目标机器:"
                echo "  gunzip -c wgs-all.tar.gz | docker load"
                echo "  # 或"
                echo "  docker load < wgs-all.tar.gz"
            else
                echo "❌ 导出失败 (exit=${EXPORT_EXIT})"
                echo "最后 20 行日志:"
                tail -20 "$LOG_FILE"
            fi
        else
            echo "❓ 无运行中的导出，也无完成标记"
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
            # 清理不完整 tar
            if [ -f "$OUTPUT_TAR" ]; then
                echo "删除不完整 tar: $OUTPUT_TAR"
                rm -f "$OUTPUT_TAR"
            fi
            echo "已终止"
        else
            echo "没有运行中的导出"
        fi
        ;;

    clean)
        if cmd_running; then
            echo "还在跑，先 stop"
            exit 1
        fi
        rm -f "$LOG_FILE" "$PID_FILE" "$DONE_FILE"
        echo "已清理日志和 PID (tar 文件未动)"
        ;;

    *)
        echo "用法: bash $0 [start|status|log|stop|clean]"
        exit 1
        ;;
esac
