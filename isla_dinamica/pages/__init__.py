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
from .servers import ServersPage  # noqa: F401
from .system import SystemPage  # noqa: F401
from .network import NetworkPage  # noqa: F401
from .downloads import DownloadsPage  # noqa: F401
from .reminders import RemindersPage  # noqa: F401
from .fx import FxPage  # noqa: F401
from .record import RecordPage  # noqa: F401
from .projects import ProjectsPage  # noqa: F401
from .presence import PresencePage  # noqa: F401
from .tasks import TasksPage  # noqa: F401
from .more import MorePage  # noqa: F401

PAGE_CLASSES = (HomePage, WifiPage, BluetoothPage, ClipboardPage, NotificationsPage, UsbPage, TimerPage, PomodoroPage, PowerPage, WeatherPage, GitHubPage, MicrosoftPage, ServersPage, SystemPage, NetworkPage, DownloadsPage, RemindersPage, FxPage, RecordPage, ProjectsPage, PresencePage, TasksPage, MorePage)
