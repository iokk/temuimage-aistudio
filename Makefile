.PHONY: help install start stop restart logs update clean

DOCKER_COMPOSE := $(shell docker compose version > /dev/null 2>&1 && echo "docker compose" || echo "docker-compose")

help:
	@echo "电商出图工作台 self-hosted 单机版"
	@echo ""
	@echo "make install   完整部署"
	@echo "make start     启动服务"
	@echo "make stop      停止服务"
	@echo "make restart   重启服务"
	@echo "make logs      查看日志"
	@echo "make update    重新构建并启动"
	@echo "make clean     删除本地镜像"

install:
	@./deploy.sh install

start:
	$(DOCKER_COMPOSE) up -d

stop:
	$(DOCKER_COMPOSE) down

restart:
	$(DOCKER_COMPOSE) restart

logs:
	$(DOCKER_COMPOSE) logs -f

update:
	$(DOCKER_COMPOSE) down
	$(DOCKER_COMPOSE) build --no-cache
	$(DOCKER_COMPOSE) up -d

clean:
	$(DOCKER_COMPOSE) down --rmi local

