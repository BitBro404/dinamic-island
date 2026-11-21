"""Páginas de la isla expandida (una por archivo)."""
from .home import HomePage  # noqa: F401
from .wifi import WifiPage  # noqa: F401
from .bluetooth import BluetoothPage  # noqa: F401
from .clipboard import ClipboardPage  # noqa: F401
from .notifications import NotificationsPage  # noqa: F401
from .usb import UsbPage  # noqa: F401
from .timer import TimerPage  # noqa: F401
from .pomodoro import PomodoroPage  # noqa: F401
from .power import PowerPage  # noqa: F401
from .weather import WeatherPage  # noqa: F401
from .github import GitHubPage  # noqa: F401
from .microsoft import MicrosoftPage  # noqa: F401
from .deploys import DeploysPage  # noqa: F401
from .servers import ServersPage  # noqa: F401
from .system import SystemPage  # noqa: F401
from .more import MorePage  # noqa: F401

PAGE_CLASSES = (HomePage, WifiPage, BluetoothPage, ClipboardPage, NotificationsPage, UsbPage, TimerPage, PomodoroPage, PowerPage, WeatherPage, GitHubPage, MicrosoftPage, DeploysPage, ServersPage, SystemPage, MorePage)
