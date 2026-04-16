"""Development server runner."""

import uvicorn


def main():
    uvicorn.run(
        "hqmts.api.app:create_app",
        factory=True,
        host="0.0.0.0",
        port=8000,
        reload=True,
        reload_dirs=["src/hqmts"],
    )


if __name__ == "__main__":
    main()
