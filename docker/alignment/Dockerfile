FROM debian:bookworm-slim

# 只装最基本的运行时依赖 (系统级的)
RUN apt-get update && apt-get install -y --no-install-recommends \
    libc6 \
    zlib1g \
    libbz2-1.0 \
    liblzma5 \
    libncurses6 \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# 复制本地编译好的生信工具 + 依赖库
COPY tools/bin/ /usr/local/bin/
COPY tools/lib/ /usr/local/lib/
RUN ldconfig

# 复制比对脚本
COPY align.sh /app/align.sh
RUN chmod +x /app/align.sh

# 复制 hg38 参考基因组 + BWA 索引
COPY reference/hg38/genome/ /reference/hg38/genome/

# 数据挂载点
VOLUME ["/data"]

ENV THREADS=0

ENTRYPOINT ["/app/align.sh"]
