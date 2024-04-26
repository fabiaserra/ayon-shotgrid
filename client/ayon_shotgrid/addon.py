import os

from ayon_core.addon import (
    AYONAddon,
    IPluginPaths,
    click_wrap
)


SHOTGRID_ADDON_DIR = os.path.dirname(os.path.abspath(__file__))


class ShotgridAddon(AYONAddon, IPluginPaths):
    name = "shotgrid"

    def initialize(self, studio_settings):
        addon_settings = studio_settings.get(self.name, dict())
        self._shotgrid_server_url = addon_settings.get("shotgrid_server")
        self._shotgrid_script_name = addon_settings["shotgrid_api_name"]
        self._shotgrid_api_key = addon_settings["shotgrid_api_key"]
        self._enable_local_storage = addon_settings.get("enable_shotgrid_local_storage")
        self._local_storage_key = addon_settings.get("local_storage_key")

    def get_sg_url(self):
        return self._shotgrid_server_url if self._shotgrid_server_url else None

    def get_sg_script_name(self):
        return self._shotgrid_script_name if self._shotgrid_script_name else None

    def get_sg_api_key(self):
        return self._shotgrid_api_key if self._shotgrid_api_key else None

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_ADDON_DIR, "plugins", "publish")
            ]
        }

    def cli(self, click_group):
        click_group.add_command(cli_main.to_click_obj())

    def is_local_storage_enabled(self):
        return self._enable_local_storage if self._enable_local_storage else False

    def get_local_storage_key(self):
        return self._local_storage_key if self._local_storage_key else None

    def create_shotgrid_session(self):
        from .lib import credentials

        sg_username = os.getenv("AYON_SG_USERNAME")
        proxy = os.environ.get("HTTPS_PROXY", "").replace("https://", "")

        return credentials.create_sg_session(
            self._shotgrid_server_url,
            sg_username,
            self._shotgrid_script_name,
            self._shotgrid_api_key,
            proxy,
        )


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
