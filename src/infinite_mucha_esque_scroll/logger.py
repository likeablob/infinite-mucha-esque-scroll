from enum import Enum

from rich.console import Console
from rich.theme import Theme

# FIXME: logging module is just enough, maybe


class LogLevel(str, Enum):
    INFO = "info"
    WARNING = "warning"
    DANGER = "danger"


custom_theme = Theme(
    {
        LogLevel.INFO: "dim cyan",
        LogLevel.WARNING: "magenta",
        LogLevel.DANGER: "bold red",
    }
)


logger = Console(theme=custom_theme, stderr=True)
