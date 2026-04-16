"""Development server runner with --env flag support."""

from __future__ import annotations

import argparse

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="HQMTS development server")
    parser.add_argument(
        "--env",
        default="research",
        choices=["research", "backtest", "paper", "live"],
        help="Environment to run in (default: research)",
    )
    parser.add_argument("--host", default="0.0.0.0", help="Bind host")
    parser.add_argument("--port", type=int, default=8000, help="Bind port")
    parser.add_argument("--no-reload", action="store_true", help="Disable auto-reload")
    args = parser.parse_args()

    uvicorn.run(
        "hqmts.api.app:create_app",
        factory=True,
        host=args.host,
        port=args.port,
        reload=not args.no_reload,
        reload_dirs=["src/hqmts"],
        env_override={"HQMTS_ENV": args.env},
    )


if __name__ == "__main__":
    main()
