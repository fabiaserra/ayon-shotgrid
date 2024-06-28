import ayon_api

from ayon_core.lib import Logger
from ayon_core.pipeline import project_folders

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

    # Create AYON project
    try:
        ayon_api.create_project(
            project_name,
            project_code,
            library_project=False,
        )
    except ValueError as e:
        logger.warning(
            "Project with code '%s' couldn't be created due to:\n%s", project_code, e
        )

    # Update project anatomy with SG id and enable push sync
    ayon_api.update_project(
        project_name=project_name,
        attrib={
            "shotgridId": sg_project["id"],
            "shotgridType": "Project",
            "shotgridPush": True,
        }
    )

    # Create project folders
    project_folders.create_project_folders(project_name)

    # Update SG project AYON auto-sync to True so it keeps it up to date
    sg.update(
        "Project",
        sg_project["id"],
        {
            "sg_ayon_auto_sync": True
        }
    )