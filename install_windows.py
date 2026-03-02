# /// script
# dependencies = [
#   "plumbum",
#   "typer",
#   "coloredlogs",
#   "inquirer3",
# ]
# ///

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Optional

import click
import coloredlogs
import inquirer3
import typer
from plumbum import ProcessExecutionError, local
from typer.core import TyperCommand

coloredlogs.install(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Paths & constants
# ---------------------------------------------------------------------------

DEV_PATH = Path("~/dev").expanduser()
VSCODE_SETTINGS_FILE = Path("~/AppData/Roaming/Code/User/settings.json").expanduser()

WINGET_PACKAGES: list[str] = [
    "difftastic",
    "coreutils",
    "Microsoft.VisualStudioCode",
    "BurntSushi.ripgrep.MSVC",
    "gnuwin32.grep",
    "chocolatey",
    "gnuwin32.tar",
    "gnuwin32.zip",
    "gnuwin32.unzip",
    "gnuwin32.findutils",
    "ajeetdsouza.zoxide",
]

PYTHON_PACKAGES: list[str | list[str]] = [
    ["pymobiledevice3", "--python", "3.12"],
    ["harlogger", "--python", "3.12"],
    ["cfprefsmon", "--python", "3.12"],
    "pychangelog2",
]

VSCODE_EXTENSION_IDS: list[str] = [
    "atommaterial.a-file-icon-vscode",
    "ms-python.autopep8",
    "ms-vscode.cpptools-extension-pack",
    "ms-vscode.cpptools-themes",
    "llvm-vs-code-extensions.vscode-clangd",
    "ms-vscode.cmake-tools",
    "qingpeng.common-lisp",
    "github.vscode-github-actions",
    "eamodio.gitlens",
    "ms-python.isort",
    "mattn.Lisp",
    "zhuangtongfa.material-theme",
    "ms-python.vscode-pylance",
    "ms-python.python",
    "infosec-intern.yara",
    "ms-vscode.vscode-typescript-next",
]

VSCODE_DEFAULT_SETTINGS = """\
{
    "editor.cursorBlinking": "smooth",
    "security.workspace.trust.untrustedFiles": "open",
    "git.openRepositoryInParentFolders": "always",
    "files.associations": {
        "*.sb": "commonlisp"
    },
    "cmake.configureOnOpen": true,
    "python.analysis.autoFormatStrings": true,
    "python.analysis.autoImportCompletions": true,
    "python.analysis.diagnosticSeverityOverrides": {},
    "python.analysis.inlayHints.functionReturnTypes": true,
    "python.analysis.inlayHints.pytestParameters": true,
    "python.analysis.inlayHints.variableTypes": true,
    "python.analysis.typeCheckingMode": "basic",
    "workbench.colorTheme": "One Dark Pro Darker",
    "autopep8.args": ["--max-line-length", "120", "--experimental"],
    "isort.args": ["-m", "HANGING_INDENT", "-l", "120"],
    "autopep8.showNotifications": "always",
    "window.zoomLevel": 0.7,
    "workbench.iconTheme": "a-file-icon-vscode",
    "gitlens.hovers.enabled": false,
    "files.exclude": {
        "**/.git": true,
        "**/.svn": true,
        "**/.hg": true,
        "**/CVS": true,
        "**/.DS_Store": true,
        "**/Thumbs.db": true,
        "**/__pycache__": true
    },
    "files.autoSave": "afterDelay"
}
"""

# ---------------------------------------------------------------------------
# plumbum commands
# ---------------------------------------------------------------------------

cmd = local["cmd"]
git = local["git"]
uv = local["uv"]


# ---------------------------------------------------------------------------
# Context / state
# ---------------------------------------------------------------------------


@dataclass
class Context:
    """Holds runtime configuration passed through the CLI."""
    automated: bool = False
    disabled_packages: list[str] = field(default_factory=list)

    def confirm(self, label: str, action: Callable[[], None]) -> None:
        """Prompt the user (or auto-confirm) before running *action*."""
        if self.automated or inquirer3.confirm(f"Install/configure {label}?", default=False):
            action()


def _store_automated(ctx: click.Context, _param: click.Parameter, value: bool) -> None:
    """Stash the flag in ctx.obj so _is_automated() can read it without the
    function receiving it as a kwarg (expose_value=False)."""
    if ctx.obj is None:
        ctx.obj = {}
    ctx.obj["automated"] = value


def _is_automated() -> bool:
    ctx = click.get_current_context()
    return (ctx.obj or {}).get("automated", False)


def _make_ctx(disabled: tuple[str, ...] = ()) -> Context:
    return Context(automated=_is_automated(), disabled_packages=list(disabled))


# ---------------------------------------------------------------------------
# Git helpers
# ---------------------------------------------------------------------------


def git_clone(repo_url: str, branch: str = "master") -> None:
    """Clone *repo_url* or pull the latest changes if it already exists."""
    try:
        git("clone", "--recurse-submodules", "-b", branch, repo_url)
    except ProcessExecutionError as e:
        if "already exists and is not an empty directory" not in e.stderr:
            raise

        repo_dir = repo_url.rsplit("/", 1)[1].removesuffix(".git")
        original_cwd = Path.cwd()
        os.chdir(repo_dir)
        try:
            git("pull", "origin", branch)
        except ProcessExecutionError as pull_err:
            dirty_markers = ("Please commit your", "You have unstaged", "Need to specify")
            if not any(m in pull_err.stderr for m in dirty_markers):
                raise
            logger.warning("Skipping pull for %s — working tree is dirty", repo_url)
        finally:
            os.chdir(original_cwd)


# ---------------------------------------------------------------------------
# Installers
# ---------------------------------------------------------------------------


def install_winget_packages(ctx: Context) -> None:
    """Install common Windows packages via winget, skipping already-installed ones."""
    logger.info("Installing winget packages")
    existing = cmd("/c", "winget", "list").lower()

    for pkg in WINGET_PACKAGES:
        if pkg in ctx.disabled_packages:
            logger.debug("Skipping disabled package: %s", pkg)
            continue
        if pkg.lower() in existing:
            logger.debug("Already installed, skipping: %s", pkg)
            continue
        ctx.confirm(pkg, lambda p=pkg: cmd("/c", "winget", "install", p))


def install_python_packages(ctx: Context) -> None:
    """Install Python tools via uv tool install."""
    logger.info("Installing Python packages")
    for entry in PYTHON_PACKAGES:
        pkg, *extra_args = entry if isinstance(entry, list) else [entry]
        ctx.confirm(pkg, lambda p=pkg, args=extra_args: uv("tool", "install", p, *args))


def install_xonsh(ctx: Context) -> None:
    """Install xonsh with extensions and optional dotfile setup."""
    logger.info("Installing xonsh")
    uv(
        "tool", "install", "xonsh[full]",
        # xpip
        '--with', 'pip',

        # xontribs
        '--with', 'xontrib-argcomplete',
        '--with', 'xontrib-fzf-widgets',
        '--with', 'xontrib-zoxide',
        '--with', 'xontrib-uvox',
        '--with', 'xontrib-jedi',

        # globalrc
        '--with', 'pygments',
        '--with', 'plumbum',

        '--python', '3.14'
    )

    for tool in ("fzf", "zoxide"):
        try:
            ctx.confirm(f"Install/Reinstall {tool}", lambda t=tool: cmd("/c", "winget", "install", t))
        except ProcessExecutionError as e:
            if "Found an existing package already installed." not in e.stdout:
                raise

    def set_xonshrc() -> None:
        DEV_PATH.mkdir(parents=True, exist_ok=True)
        os.chdir(DEV_PATH)
        git_clone("git@github.com:doronz88/windowssetup.git", "master")
        xonshrc_src = Path(__file__).parent / ".xonshrc"
        Path("~/.xonshrc").expanduser().write_bytes(xonshrc_src.read_bytes())

    ctx.confirm("set ready-made .xonshrc file", set_xonshrc)


def _write_vscode_settings() -> None:
    VSCODE_SETTINGS_FILE.write_text(VSCODE_DEFAULT_SETTINGS, encoding="utf-8")


def configure_vscode(ctx: Context) -> None:
    """Install VSCode extensions and optionally overwrite settings."""
    logger.info("Configuring VSCode")
    for ext_id in VSCODE_EXTENSION_IDS:
        logger.debug("Installing extension: %s", ext_id)
        cmd("/c", "code", "--install-extension", ext_id)

    ctx.confirm("overwrite VSCode settings", _write_vscode_settings)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


class AutomatedCommand(TyperCommand):
    """-a/--automated declared once here with expose_value=False + callback.
    expose_value=False means Click will NOT pass it as a kwarg to the function.
    The callback stashes the value in ctx.obj so _is_automated() can read it.
    """

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.params[:0] = [
            click.Option(
                ("-a", "--automated"),
                is_flag=True,
                default=False,
                expose_value=False,
                callback=_store_automated,
                help="Run without interactive prompts (auto-confirm everything).",
            )
        ]


cli = typer.Typer(help="Automate Windows machine setup")


@cli.command("winget-packages", cls=AutomatedCommand)
def cli_winget_packages(
        disable: Optional[list[str]] = typer.Option(None, "-d", "--disable"),
) -> None:
    """Install common packages via winget."""
    install_winget_packages(_make_ctx(tuple(disable or [])))


@cli.command("python-packages", cls=AutomatedCommand)
def cli_python_packages() -> None:
    """Install Python tools via uv."""
    install_python_packages(_make_ctx())


@cli.command("xonsh", cls=AutomatedCommand)
def cli_xonsh() -> None:
    """Install xonsh shell and extensions."""
    install_xonsh(_make_ctx())


@cli.command("configure-vscode", cls=AutomatedCommand)
def cli_configure_vscode() -> None:
    """Install VSCode extensions and apply default settings."""
    configure_vscode(_make_ctx())


@cli.command("everything", cls=AutomatedCommand)
def cli_everything(
        disable: Optional[list[str]] = typer.Option(None, "-d", "--disable"),
) -> None:
    """Run all setup steps in sequence."""
    ctx = _make_ctx(tuple(disable or []))
    install_winget_packages(ctx)
    configure_vscode(ctx)
    install_python_packages(ctx)
    install_xonsh(ctx)


if __name__ == "__main__":
    cli()
