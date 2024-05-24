import os
import re

from ayon_core.addon import (
    AYONAddon,
    ITrayAddon,
    IPluginPaths,
    click_wrap
)
from ayon_core.lib import Logger

log = Logger.get_logger(__name__)

SHOTGRID_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))


class ShotgridAddon(AYONAddon, ITrayAddon, IPluginPaths):
    name = "shotgrid"
    tray_wrapper = None

    def initialize(self, studio_settings):
        addon_settings = studio_settings[self.name]
        client_login_info = addon_settings["client_login"]

        log.debug(
            f"Initializing {self.name} addon with "
            "settings: {addon_settings}"
        )
        self._shotgrid_server_url = addon_settings["shotgrid_server"]
        self._client_login_type = client_login_info["type"]

        self._shotgrid_api_key = None
        self._shotgrid_script_name = None

        # reconfigure for client user api key since studio might need to
        # use a different api key with different permissions access
        if self._client_login_type in ["env", "tray_api_key"]:
            self._shotgrid_script_name = (
                client_login_info
                [self._client_login_type]
                ["client_sg_script_name"]
            )
            self._shotgrid_api_key = (
                client_login_info
                [self._client_login_type]
                ["client_sg_script_key"]
            )

        self._enable_local_storage = addon_settings.get(
            "enable_shotgrid_local_storage")

        # ShotGrid local storage entry name
        self._local_storage_key = addon_settings.get(
            "shotgrid_local_storage_key")

    def get_sg_url(self):
        return self._shotgrid_server_url or None

    def get_sg_script_name(self):
        return self._shotgrid_script_name or None

    def get_sg_api_key(self):
        return self._shotgrid_api_key or None

    def get_client_login_type(self):
        return self._client_login_type or None

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_ADDON_DIR, "plugins", "publish")
            ]
        }

    def get_launch_hook_paths(self, app):
        return [
            os.path.join(SHOTGRID_ADDON_DIR, "hooks")
        ]
    
    def cli(self, click_group):
        click_group.add_command(cli_main.to_click_obj())

    def is_local_storage_enabled(self):
        return self._enable_local_storage or False

    def get_local_storage_key(self):
        return self._local_storage_key or None

    def create_shotgrid_session(self):
        from .lib import credentials
        kwargs = {
            "shotgrid_url": self._shotgrid_server_url,
        }

        proxy = re.sub(r"https?://", "", os.environ.get("HTTPS_PROXY", ""))
        if proxy:
            kwargs["proxy"] = proxy

        if self._client_login_type == "env":
            log.debug("Logging in to Flow using env")
            sg_username = (
                os.getenv("AYON_SG_USERNAME")
                # TODO: Remove USER env variable in future once ayon-core deadline
                # passing of AYON_SG_USERNAME is solved
                or os.getenv("USER")
            )
            kwargs.update({
                "username": sg_username,
                "api_key": self._shotgrid_api_key,
                "script_name": self._shotgrid_script_name,
            })
        elif self._client_login_type == "tray_pass":
            log.debug("Logging in to Flow using tray pass")
            sg_username, sg_password = credentials.get_local_login()

            if not sg_username or not sg_password:
                return None

            kwargs.update({
                "username": sg_username,
                "password": sg_password
            })

        elif self._client_login_type == "tray_api_key":
            log.debug("Logging in to Flow using tray api key")
            sg_username, _ = credentials.get_local_login()
            kwargs.update({
                "username": sg_username,
                "api_key": self._shotgrid_api_key,
                "script_name": self._shotgrid_script_name,
            })

        return credentials.create_sg_session(**kwargs)

    def tray_init(self):
        # do not initialize tray if client login type is not tray related
        if self._client_login_type == "env":
            return

        from .tray.shotgrid_tray import ShotgridTrayWrapper
        self.tray_wrapper = ShotgridTrayWrapper(self)

    def tray_start(self):
        # do not initialize tray if client login type is not tray related
        if self._client_login_type == "env":
            return

        return self.tray_wrapper.set_username_label()

    def tray_exit(self, *args, **kwargs):
        # do not initialize tray if client login type is not tray related
        if self._client_login_type == "env":
            return

        return self.tray_wrapper

    def tray_menu(self, tray_menu):
        # do not initialize tray if client login type is not tray related
        if self._client_login_type == "env":
            return

        return self.tray_wrapper.tray_menu(tray_menu)

@click_wrap.command("populate_tasks")
@click_wrap.argument("project_code")
def populate_tasks_command(project_code):
    """Given a SG project code, populate the default tasks to all its entities."""
    from ayon_shotgrid.scripts import populate_tasks
    return populate_tasks.populate_tasks(project_code)


@click_wrap.command("create_project")
@click_wrap.argument("project_code")
def create_project_command(project_code):
    """Given a SG project code, populate the default tasks to all its entities."""
    from ayon_shotgrid.scripts import create_project
    return create_project.create_project(project_code)


@click_wrap.group(ShotgridAddon.name, help="Shotgrid CLI")
def cli_main():
    pass


cli_main.add_command(populate_tasks_command)
cli_main.add_command(create_project_command)
