# 构建镜像
docker build -t hs300-analyzer /workspace/share300

# 运行（前台，输出直接打印到终端）
docker run --rm hs300-analyzer

# 后台运行 + 保存结果
docker run --rm -v $(pwd):/app hs300-analyzer

docker build -t hs300-analyzer /workspace/share300 && docker run --rm hs300-analyzer