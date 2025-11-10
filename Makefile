.PHONY: help install dev-install test lint format type-check clean run-check run-fetch

help:
	@echo "PaperGazer 开发命令"
	@echo ""
	@echo "安装:"
	@echo "  make install         安装生产依赖"
	@echo "  make dev-install    安装开发依赖"
	@echo ""
	@echo "开发:"
	@echo "  make test           运行测试"
	@echo "  make lint           代码检查 (ruff)"
	@echo "  make format         代码格式化 (black + isort)"
	@echo "  make type-check     类型检查 (mypy)"
	@echo ""
	@echo "运行:"
	@echo "  make run-check      执行每日巡检"
	@echo "  make run-fetch      按需抓取（需提供 IDENTIFIER=xxx）"
	@echo ""
	@echo "清理:"
	@echo "  make clean          清理临时文件"

install:
	pip install -r requirements.txt

dev-install:
	pip install -r requirements.txt
	pip install -e ".[dev]"

test:
	pytest tests/ -v

lint:
	ruff check papergazer/ tests/

format:
	black papergazer/ tests/
	isort papergazer/ tests/

type-check:
	mypy papergazer/

clean:
	find . -type d -name __pycache__ -exec rm -r {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name "*.pyo" -delete
	find . -type d -name "*.egg-info" -exec rm -r {} +
	rm -rf .pytest_cache .mypy_cache .ruff_cache

run-check:
	python -m papergazer.cli check

run-fetch:
	@if [ -z "$(IDENTIFIER)" ]; then \
		echo "错误: 请提供 IDENTIFIER 参数，例如: make run-fetch IDENTIFIER=10.1038/s41586-xxxx-xxxx-x"; \
		exit 1; \
	fi
	python -m papergazer.cli fetch $(IDENTIFIER)

