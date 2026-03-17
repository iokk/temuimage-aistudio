.PHONY: help install start stop restart logs update clean build

# 自动检测docker compose命令
DOCKER_COMPOSE := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

# 默认目标
help:
	@echo "🍌 TEMU 电商智能作图系统 V15.3.0"
	@echo ""
	@echo "使用方法: make [命令]"
	@echo ""
	@echo "命令:"
	@echo "  install  - 完整安装部署"
	@echo "  start    - 启动服务"
	@echo "  stop     - 停止服务"
	@echo "  restart  - 重启服务"
	@echo "  logs     - 查看日志"
	@echo "  update   - 更新并重启"
	@echo "  clean    - 清理镜像（保留数据）"
	@echo "  build    - 仅构建镜像"
	@echo ""
	@echo "当前使用: $(DOCKER_COMPOSE)"

# 完整安装
install:
	@./deploy.sh install

# 启动
start:
	$(DOCKER_COMPOSE) up -d

# 停止
stop:
	$(DOCKER_COMPOSE) down

# 重启
restart:
	$(DOCKER_COMPOSE) restart

# 日志
logs:
	$(DOCKER_COMPOSE) logs -f

# 更新
update:
	$(DOCKER_COMPOSE) down
	$(DOCKER_COMPOSE) build --no-cache
	$(DOCKER_COMPOSE) up -d

# 清理
clean:
	$(DOCKER_COMPOSE) down --rmi local

# 仅构建
build:
	$(DOCKER_COMPOSE) build --no-cache
