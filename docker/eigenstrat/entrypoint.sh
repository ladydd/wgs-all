#!/bin/bash
# wgs-all 镜像统一入口
#
# 支持子命令:
#   align <sample_id> <r1> <r2> [threads]   — 比对 FASTQ → BAM (沿用老 wgs-align 行为)
#   bam-to-eigenstrat [args...]              — 批量 BAM → EIGENSTRAT (新能力)
#   cli <subcommand> [args...]               — 透传到 python -m app.cli <...>
#   shell                                     — 进 bash 交互
#   help                                      — 显示帮助
#
# 环境变量:
#   THREADS / SORT_MEM / MAX_MEM_GB / SAFE_MODE — 比对相关 (align 子命令)
#   WGS_REFERENCE_DIR=/reference — 参考数据根
#   WGS_DATA_DIR=/data          — 数据挂载点

set -e

CMD=${1:-help}
shift || true

# 修复输出文件权限：自动检测挂载目录的属主，输出文件跟随
# 用户也可通过 HOST_UID/HOST_GID 环境变量覆盖
fix_permissions() {
    local dir="$1"
    [ -d "$dir" ] || return 0
    local uid="${HOST_UID:-$(stat -c '%u' "$dir" 2>/dev/null)}"
    local gid="${HOST_GID:-$(stat -c '%g' "$dir" 2>/dev/null)}"
    # 如果目录属于 root (uid=0)，说明不是用户挂载的，跳过
    [ "$uid" = "0" ] && return 0
    find "$dir" -user root -exec chown ${uid}:${gid} {} + 2>/dev/null || true
}

# 在脚本退出时自动修复常见输出目录的权限
trap 'fix_permissions /data; fix_permissions /output' EXIT

case "$CMD" in
    align)
        # hg38 比对 (沿用原 wgs-align 的 align.sh)
        exec /app/align.sh "$@"
        ;;

    align-hg19|align-hs37d5|align-grch37)
        # hg19/hs37d5/GRCh37 比对
        exec /app/align-hg19.sh "$@"
        ;;

    align-t2t|align-chm13)
        # T2T/CHM13v2 比对
        exec /app/align-t2t.sh "$@"
        ;;

    bam-to-eigenstrat|eigenstrat|bte)
        # 批量 BAM → EIGENSTRAT 数据集
        cd /app
        exec python -m app.cli bam-to-eigenstrat "$@"
        ;;

    analyze-y|yleaf|y-haplogroup)
        # Y 单倍群分析
        cd /app
        exec python -m app.cli analyze-y "$@"
        ;;

    analyze-mt|haplogrep|mt-haplogroup)
        # MT 单倍群分析
        cd /app
        exec python -m app.cli analyze-mt "$@"
        ;;

    extract-chr)
        # 提取 chrY/chrM
        cd /app
        exec python -m app.cli extract-chr "$@"
        ;;

    extract-chip)
        # 芯片格式导出
        cd /app
        exec python -m app.cli extract-chip "$@"
        ;;

    extract-1240k)
        # 1240K 位点提取
        cd /app
        exec python -m app.cli extract-1240k "$@"
        ;;

    detect-bam)
        # BAM 参考版本识别
        cd /app
        exec python -m app.cli detect-bam "$@"
        ;;

    admixture-calc|calculator|calc)
        # 常染色体祖源计算器
        cd /app
        exec python -m app.cli admixture-calc "$@"
        ;;

    pca)
        # PCA 分析
        cd /app
        exec python -m app.cli pca "$@"
        ;;

    g25)
        # G25 距离计算
        cd /app
        exec python -m app.cli g25 "$@"
        ;;

    report)
        # HTML 报告生成
        cd /app
        exec python -m app.cli report "$@"
        ;;

    full-pipeline|full|all)
        # 一键全流程
        cd /app
        exec python -m app.cli full-pipeline "$@"
        ;;

    cli)
        # 透传到 app.cli 的其他子命令 (如 detect-bam, extract-1240k, ...)
        cd /app
        exec python -m app.cli "$@"
        ;;

    shell|bash|sh)
        exec /bin/bash "$@"
        ;;

    help|--help|-h|"")
        cat <<EOF
wgs-all v1.3.0 — WGS 分析一体化镜像

包含能力:
  • hg38 FASTQ → BAM 比对         (来自 wgs-align 基础层)
  • hg19 FASTQ → BAM 比对         (hs37d5 参考, 无 chr 前缀)
  • T2T  FASTQ → BAM 比对         (CHM13v2 参考, chr 前缀)
  • hg38 BAM → EIGENSTRAT 数据集  (古 DNA 交付格式, 可选回换 hg19 坐标)
  • 全套 app.cli 工具 (detect-bam, extract-chip, extract-1240k, analyze-y, ...)

常用命令:
  # 比对 (三套参考基因组)
  docker run --rm -v /data:/data wgs-all align SAMPLE R1.fq.gz R2.fq.gz
  docker run --rm -v /data:/data wgs-all align-hg19 SAMPLE R1.fq.gz R2.fq.gz
  docker run --rm -v /data:/data wgs-all align-t2t SAMPLE R1.fq.gz R2.fq.gz

  # Y/MT 单倍群
  docker run --rm -v /data:/data wgs-all analyze-y /data/x.chrY.bam -o /data/yleaf
  docker run --rm -v /data:/data wgs-all analyze-mt /data/x.chrM.vcf.gz -o /data/mt.txt

  # EIGENSTRAT 导出
  docker run --rm -v /data:/data wgs-all bam-to-eigenstrat \\
      --bam /data/x.bam -p Pop -o /data/out -n dataset --deliver-hg19

  # 芯片格式 (11 种)
  docker run --rm -v /data:/data wgs-all extract-chip /data/x.bam -o /data/chip -s SAMPLE

  # 祖源计算器 (28 个)
  docker run --rm -v /data:/data wgs-all admixture-calc /data/chip/x_23andMe_V5.txt -c E11,K36

  # G25 距离计算
  docker run --rm wgs-all g25 --coords "0.02,-0.015,..." --top 20

  # HTML 报告
  docker run --rm -v /data:/data wgs-all report -s SAMPLE -o /data/report.html \\
      --y-hg "N1a2a" --mt-hg "A11" --eigen-snps 1231730

  # 一键全流程
  docker run --rm -v /data:/data wgs-all full-pipeline --bam /data/x.bam -o /data/results

  # 交互式 shell
  docker run --rm -it -v /data:/data wgs-all shell

挂载:
  /data       — 数据读写 (必须挂, 输入 BAM + 输出)
  /reference  — 镜像自带, 一般不需要挂载 (除非覆盖)

文件权限:
  容器默认以 root 运行，输出文件属于 root。
  如需修复权限，加环境变量: -e HOST_UID=$(id -u) -e HOST_GID=$(id -g)

bam-to-eigenstrat 参数详解:
EOF
        cd /app 2>/dev/null && python -m app.cli bam-to-eigenstrat --help 2>&1 | tail -n +2
        ;;

    *)
        # 默认情况: 第一个参数看起来像 CLI 子命令？ 透传
        # 否则报错
        if [ -n "$CMD" ]; then
            echo "[wgs-all] 未知子命令: $CMD"
            echo "运行 'docker run wgs-all help' 查看用法"
            exit 1
        fi
        ;;
esac
