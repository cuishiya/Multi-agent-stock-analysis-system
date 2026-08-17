"""本地启动股票分析 Agent 系统 Web 应用。"""

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="股票分析 Agent 系统 Web 服务")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=8000)
    parser.add_argument("--reload", action="store_true")
    args = parser.parse_args()

    uvicorn.run(
        "src.web.app:app",
        host=args.host,
        port=args.port,
        reload=args.reload,
    )


if __name__ == "__main__":
    main()
