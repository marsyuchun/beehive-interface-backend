# beehive-interface-backend

接口自动化测试平台后端，提供项目、环境、用例、版本和执行记录 API，并包含 pytest 执行引擎与本地 Mock 服务。

## 技术栈

- FastAPI
- SQLAlchemy
- Alembic
- pytest
- Flask Mock API
- SQLite（默认，可通过环境变量切换）

## 环境要求

- Python 3.11+

## 安装

```bash
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
```

## 初始化数据库

```bash
alembic upgrade head
python -m app.seed
```

默认数据库文件为 `api_pilot.db`。可通过 `DATABASE_URL` 修改数据库连接。

## 启动服务

```bash
uvicorn app.main:app --host 127.0.0.1 --port 8000 --reload
```

健康检查地址：

```text
http://127.0.0.1:8000/api/v1/health
```

## 启动本地 Mock API

```bash
flask --app mock_server.app:create_app run --host 127.0.0.1 --port 5001
```

如需让演示数据使用该端口：

```bash
DEMO_BASE_URL=http://127.0.0.1:5001 python -m app.seed
```

## 测试

```bash
pytest
```

测试报告、执行事件和本地数据库文件不会提交到 Git 仓库。
