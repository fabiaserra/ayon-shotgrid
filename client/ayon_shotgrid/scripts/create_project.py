from openpype import client
from openpype.lib import Logger
from openpype.pipeline import project_folders
from openpype.settings import get_project_settings

from ayon_shotgrid.lib import credentials


logger = Logger.get_logger(__name__)


def create_project(project_code):
    """Create a new project, set up its folders and populate it with the SG info."""

    # Query project in SG to grab its code name and id
    sg = credentials.get_shotgrid_session()
    sg_project = sg.find_one(
        "Project",
        [
            ["sg_code", "is", project_code],
        ],
        ["name", "id"],
    )
    if not sg_project:
        logger.error("Project with 'sg_code' '%s' not found.", project_code)
        return

    project_name = sg_project["name"]

    # Create OP project
    client.create_project(
        project_name,
        project_code,
        library_project=False,
    )

    # Set SG project id on project settings
    project_settings = get_project_settings(project_name)
    project_settings["shotgrid"]["shotgrid_project_id"] = sg_project["id"]

    # Create project folders
    project_folders.create_project_folders(project_name)
