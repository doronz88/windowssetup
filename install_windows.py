import logging
import os
import sys
from pathlib import Path
from typing import Callable, List

import click
import coloredlogs
import inquirer3
from plumbum import ProcessExecutionError, local
from plumbum.commands.base import BoundCommand

coloredlogs.install(level=logging.DEBUG)

DEV_PATH = Path('~/dev').expanduser()
VSCODE_EXTENSION_IDS = [
    'atommaterial.a-file-icon-vscode', 'ms-python.autopep8', 'ms-vscode.cpptools-extension-pack',
    'ms-vscode.cpptools-themes', 'llvm-vs-code-extensions.vscode-clangd', 'ms-vscode.cmake-tools',
    'qingpeng.common-lisp', 'github.vscode-github-actions', 'eamodio.gitlens', 'ms-python.isort', 'mattn.Lisp',
    'zhuangtongfa.material-theme', 'ms-python.vscode-pylance', 'ms-python.python', 'infosec-intern.yara',
    'ms-vscode.vscode-typescript-next']
VSCODE_SETTINGS_FILE = Path('~/AppData/Roaming/Code/User/settings.json').expanduser()

VSCODE_DEFAULT_SETTINGS = """
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
    "python.analysis.diagnosticSeverityOverrides": {
    },
    "python.analysis.inlayHints.functionReturnTypes": true,
    "python.analysis.inlayHints.pytestParameters": true,
    "python.analysis.inlayHints.variableTypes": true,
    "python.analysis.typeCheckingMode": "basic",
    "workbench.colorTheme": "One Dark Pro Darker",
    "autopep8.args": [
        "--max-line-length",
        "120",
        "--experimental"
    ],
    "isort.args": [
        "-m",
        "HANGING_INDENT",
        "-l",
        "120"
    ],
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
        "**/__pycache__": true,
    },
    "files.autoSave": "afterDelay"
}
"""

cmd = local['cmd']
python3 = local[sys.executable]
git = local['git']

logger = logging.getLogger(__name__)

AUTOMATION_MODE = False


def confirm_install(component: str, installer: Callable):
    if AUTOMATION_MODE or inquirer3.confirm(f'To {component}?', default=False):
        installer()


def insert_number_install(message: str, installer: BoundCommand, default_number: int):
    installer[default_number if AUTOMATION_MODE else inquirer3.text(message, default=str(default_number))]()


def git_clone(repo_url: str, branch='master'):
    try:
        git('clone', '--recurse-submodules', '-b', branch, repo_url)
    except ProcessExecutionError as e:
        if 'already exists and is not an empty directory' not in e.stderr:
            raise
        cwd = os.getcwd()
        os.chdir(repo_url.rsplit('/', 1)[1].rsplit('.git', 1)[0])
        try:
            git('pull', 'origin', branch)
        except ProcessExecutionError as e:
            if ('Please commit your' not in e.stderr) and ('You have unstaged' not in e.stderr) and (
                    'Need to specify' not in e.stderr):
                raise
            logger.warning(f'failed to pull {repo_url}')
        os.chdir(cwd)


def install_winget_packages(disable: List[str]):
    logger.info('installing winget packages')

    for package in ['difftastic', 'coreutils', 'Microsoft.VisualStudioCode']:
        try:
            confirm_install(f'install {package}', cmd['/c', f'winget install {package}'])
        except ProcessExecutionError as e:
            if 'Found an existing package already installed.' not in e.stdout:
                raise


def install_python_packages():
    logger.info('installing python packages')

    confirm_install('upgrade pip', python3['-m', 'pip', 'install', '-U', 'pip'])
    confirm_install('install pipx', python3['-m', 'pip', 'install', '-U', 'pipx'])

    python_packages = ['pymobiledevice3', 'harlogger', 'cfprefsmon', 'pychangelog2', 'isort', 'flake8']

    for package in python_packages:
        confirm_install(f'install {package}', python3['-m', 'pipx', 'install', package])


def install_xonsh():
    logger.info('installing xonsh')

    confirm_install('upgrade pip', python3['-m', 'pip', 'install', '-U', 'pip'])

    python3('-m', 'pip', 'install', '-U', 'pipx')
    python3('-m', 'pipx', 'install', 'xonsh[full]')

    # xontribs
    python3('-m', 'pipx', 'runpip', 'xonsh', 'install', '-U', 'xontrib-argcomplete',
            'xontrib-fzf-widgets', 'xontrib-z', 'xontrib-up', 'xontrib-vox', 'xontrib-jedi')

    # required by the global xonshrc
    python3('-m', 'pipx', 'runpip', 'xonsh', 'install', '-U', 'pygments', 'plumbum')

    try:
        confirm_install('install/reinstall fzf', cmd['/c', 'winget', 'install', 'fzf'])
    except ProcessExecutionError as e:
        if 'Found an existing package already installed.' not in e.stdout:
            raise

    def set_xonshrc():
        DEV_PATH.mkdir(parents=True, exist_ok=True)

        os.chdir(DEV_PATH)
        git_clone('git@github.com:doronz88/windowssetup.git', 'master')
        Path('~/.xonshrc').expanduser().write_bytes((Path(__file__).parent / 'worksetup/.xonshrc').read_bytes())

    confirm_install('set ready-made .xonshrc file', set_xonshrc)


def overwrite_vscode_settings_file() -> None:
    VSCODE_SETTINGS_FILE.write_text(VSCODE_DEFAULT_SETTINGS)


def configure_vscode() -> None:
    logger.info('configuring vscode')
    for ext_id in VSCODE_EXTENSION_IDS:
        local['cmd']('/c', 'code', '--install-extension', ext_id)

    confirm_install('overwrite vscode settings file', overwrite_vscode_settings_file)


def set_automation(ctx, param, value):
    if value:
        global AUTOMATION_MODE
        AUTOMATION_MODE = True


class BaseCommand(click.Command):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.params[:0] = [
            click.Option(('-a', '--automated'), is_flag=True, callback=set_automation, expose_value=False,
                         help='do everything without prompting (unless certain removals are required)')]


@click.group()
def cli():
    """ Automate selected installs """
    pass


@cli.command('python-packages', cls=BaseCommand)
def cli_python_packages():
    """ Install selected python packages """
    install_python_packages()


@cli.command('xonsh', cls=BaseCommand)
def cli_xonsh():
    """ Install xonsh """
    install_xonsh()


@cli.command('configure-vscode', cls=BaseCommand)
def cli_configure_vscode():
    """ Configure vscode """
    configure_vscode()


@cli.command('everything', cls=BaseCommand)
@click.option('-d', '--disable', multiple=True)
def cli_everything(disable: List[str]):
    """ Install everything """
    install_winget_packages(disable)
    configure_vscode()
    install_python_packages()
    install_xonsh()


if __name__ == '__main__':
    cli()
