from app.api.app import create_app
from app.core.config import get_settings

import uvicorn


def main() -> None:
    settings = get_settings()
    app = create_app()
    uvicorn.run(
        app,
        host=settings.api_host,
        port=settings.api_port,
        log_level="info",
    )


if __name__ == "__main__":
    main()
