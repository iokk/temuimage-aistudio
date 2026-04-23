"""Desktop window shell helpers."""


def pywebview_available() -> bool:
    try:
        import webview  # type: ignore  # noqa: F401

        return True
    except Exception:
        return False


def open_desktop_window(
    url: str,
    title: str = "电商出图工作台",
    width: int = 1440,
    height: int = 960,
) -> bool:
    try:
        import webview  # type: ignore
    except Exception:
        return False
    try:
        webview.create_window(title, url=url, width=width, height=height)
        webview.start()
        return True
    except Exception:
        return False
