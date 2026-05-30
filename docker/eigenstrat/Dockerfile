# wgs-all: 全能 WGS 分析镜像
#
# 继承 wgs-align:latest (已含 hg38 参考 + bwa + samtools)
# 在其上增加:
#   - Python 3 + pyliftover + pydantic 等
#   - pileupCaller (sequencetools)
#   - EIGENSTRAT 位点文件 (hg38 liftOver 版 + AADR 原版 hg19)
#   - hg19ToHg38 chain 文件
#   - app/ 项目代码 + 统一入口 entrypoint.sh
#
# 使用:
#   docker run --rm -v /data:/data wgs-all:latest align sampleA R1.fq R2.fq
#   docker run --rm -v /data:/data wgs-all:latest bam-to-eigenstrat --bam-list bams.txt --deliver-hg19 -o /data/out -n mydataset
#   docker run --rm -it wgs-all:latest shell

FROM wgs-align:latest

# ===== 系统级 Python 环境 =====
# debian slim 默认无 Python，装最小集。pyliftover 是纯 Python，pydantic 有 C 扩展但 pip 会装 wheel
RUN apt-get update && apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        python3-venv \
        ca-certificates \
        openjdk-17-jre-headless \
        git \
        libcurl4 \
        bcftools \
        tabix \
        samtools \
    && rm -rf /var/lib/apt/lists/* \
    && ln -sf /usr/bin/python3 /usr/local/bin/python \
    && rm -f /usr/local/bin/samtools /usr/local/lib/libtinfow* /usr/local/lib/libncursesw*

# ===== Python 包 =====
# 用 --break-system-packages 绕过 PEP 668 限制 (容器里就是系统环境)
# 先装运行 bam-to-eigenstrat 必需的最小集，再装完整 requirements (含 fastapi/uvicorn)
COPY requirements.txt /tmp/requirements.txt
COPY admix_repo/ /tmp/admix_repo/
RUN pip install --no-cache-dir --break-system-packages \
        pyliftover \
        pydantic \
        pydantic-settings \
        pandas \
        numpy \
    && pip install --no-cache-dir --break-system-packages -r /tmp/requirements.txt \
    && pip install --no-cache-dir --break-system-packages /tmp/admix_repo \
    && pip install --no-cache-dir --break-system-packages git+https://github.com/genid/Yleaf.git \
    && rm -rf /tmp/requirements.txt /tmp/admix_repo

# ===== pileupCaller + smartpca + ADMIXTOOLS + 依赖库 =====
# bcftools/tabix 已通过 apt 安装
COPY tools/pileupCaller /usr/local/bin/pileupCaller
COPY tools/smartpca /usr/local/bin/smartpca
COPY tools/qpAdm /usr/local/bin/qpAdm
COPY tools/convertf /usr/local/bin/convertf
COPY tools/mergeit /usr/local/bin/mergeit
COPY tools/plink /usr/local/bin/plink
COPY tools/admixture /usr/local/bin/admixture
COPY tools/lib/ /usr/local/lib/
RUN ldconfig && chmod +x /usr/local/bin/pileupCaller \
    /usr/local/bin/smartpca /usr/local/bin/qpAdm /usr/local/bin/convertf /usr/local/bin/mergeit \
    /usr/local/bin/plink /usr/local/bin/admixture

# ===== hg19 参考基因组 (hs37d5) + BWA 索引 =====
COPY reference/hg19/genome/ /reference/hg19/genome/

# ===== T2T 参考基因组 (CHM13v2) + BWA 索引 =====
COPY reference/t2t/genome/ /reference/t2t/genome/

# ===== 比对脚本 =====
COPY align-hg19.sh /app/align-hg19.sh
COPY align-t2t.sh /app/align-t2t.sh
RUN chmod +x /app/align-hg19.sh /app/align-t2t.sh

# ===== 芯片模板 + SNP 注释 + 1240K 位点 =====
COPY reference/microarray/ /reference/microarray/
COPY reference/hg38/1240k/ /reference/hg38/1240k/

# ===== 参考数据：hg38 EIGENSTRAT 位点 + AADR 原版 hg19 snp + chain =====
# /reference/population/eigenstrat/v42.4.1240K.hg38.{snp,pos,chr.pos,liftover_log.tsv}
COPY reference/population/eigenstrat/ /reference/population/eigenstrat/

# /reference/aadr_positions/{v42.4.1240K.snp, v42.4.1240K.pos, v42.4.hg19.pos, v66.2M.aadr.snp, v66.2M.aadr.pos}
# (AADR 原版，hg19 坐标，--deliver-hg19 时查 rsID→hg19 坐标用)
COPY reference/aadr_positions/ /reference/aadr_positions/

# /reference/liftover/hg19ToHg38.over.chain.gz (未来 liftover 任务用)
COPY reference/liftover/ /reference/liftover/

# ===== yleaf v4 Y 单倍群 (pip 安装，含数据) =====
# yleaf 通过 pip 安装，不需要 COPY


# ===== Haplogrep3 MT 单倍群分析工具 =====
COPY reference/tools/haplogrep/ /reference/tools/haplogrep/
# ===== G25 参考坐标 =====
COPY reference/population/g25/ /reference/population/g25/

# ===== 项目代码 =====
# /app/app/ = Python 包，/app/ 是导入根路径
COPY app/ /app/app/

# ===== 统一入口 =====
COPY entrypoint.sh /app/entrypoint.sh
RUN chmod +x /app/entrypoint.sh

# ===== 环境变量 (默认指向容器内路径) =====
ENV PYTHONPATH=/app \
    WGS_REFERENCE_DIR=/reference \
    WGS_DATA_DIR=/data \
    WGS_LOG_DIR=/data/logs \
    THREADS=0 \
    YLEAF_REF_DIR=/reference/yleaf_ref

# Yleaf 参考基因组符号链接 (避免重复下载)
RUN mkdir -p /reference/yleaf_ref \
    && ln -s /reference/hg38/genome/hs38.fa /reference/yleaf_ref/hg38.fa \
    && ln -s /reference/hg19/genome/hs37d5.fa /reference/yleaf_ref/hg19.fa \
    && ln -s /reference/t2t/genome/chm13v2.fa /reference/yleaf_ref/t2t.fa

# /data 继承自 wgs-align (VOLUME /data)
WORKDIR /app

ENTRYPOINT ["/app/entrypoint.sh"]
CMD ["help"]
