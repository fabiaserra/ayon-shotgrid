import os
import click

import ayon_api

from ayon_core.addon import (
    AYONAddon,
    IPluginPaths,
)


SHOTGRID_MODULE_DIR = os.path.dirname(os.path.abspath(__file__))


class ShotgridAddon(AYONAddon, IPluginPaths):
    name = "shotgrid"
    enabled = True

    def initialize(self, modules_settings):
        module_settings = modules_settings.get(self.name, dict())
        self._shotgrid_server_url = module_settings.get("shotgrid_server")
        self._shotgrid_script_name = module_settings["shotgrid_api_name"]
        self._shotgrid_api_key = module_settings["shotgrid_api_key"]
        self._enable_local_storage = module_settings.get("enable_shotgrid_local_storage")
        self._local_storage_key = module_settings.get("local_storage_key")

    def get_sg_url(self):
        return self._shotgrid_server_url if self._shotgrid_server_url else None

    def get_sg_script_name(self):
        return self._shotgrid_script_name if self._shotgrid_script_name else None

    def get_sg_api_key(self):
        return self._shotgrid_api_key if self._shotgrid_api_key else None

    def get_plugin_paths(self):
        return {
            "publish": [
                os.path.join(SHOTGRID_MODULE_DIR, "plugins", "publish")
            ]
        }

    def is_local_storage_enabled(self):
        return self._enable_local_storage if self._enable_local_storage else False

    def get_local_storage_key(self):
        return self._local_storage_key if self._local_storage_key else None

    def create_shotgrid_session(self):
        from .lib import credentials

        sg_username = os.getenv("AYON_SG_USERNAME") or os.getenv("USER")
        proxy = os.environ.get("HTTPS_PROXY", "").replace("https://", "")

        return credentials.create_sg_session(
            self._shotgrid_server_url,
            sg_username,
            self._shotgrid_script_name,
            self._shotgrid_api_key,
            proxy,
        )


@click.command("populate_tasks")
@click.argument("project_code")
def populate_tasks_command(project_code):
    """Given a SG project code, populate the default tasks to all its entities."""
    from ayon_shotgrid.scripts import populate_tasks
    return populate_tasks.populate_tasks(project_code)


@click.command("create_project")
@click.argument("project_code")
def create_project_command(project_code):
    """Given a SG project code, populate the default tasks to all its entities."""
    from ayon_shotgrid.scripts import create_project
    return create_project.create_project(project_code)


@click.group(ShotgridAddon.name, help="Shotgrid CLI")
def cli_main():
    pass


cli_main.add_command(populate_tasks_command)
cli_main.add_command(create_project_command)


if __name__ == "__main__":
    cli_main()
