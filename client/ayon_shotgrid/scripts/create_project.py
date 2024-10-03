import ayon_api
from ayon_core.lib import Logger
from ayon_core.pipeline import project_folders
from ayon_shotgrid.lib import credentials

# Initialize logger
logger = Logger.get_logger(__name__)

class ProjectNotFound(Exception):
    """Exception raised when a project is not found in ShotGrid."""
    pass

def get_sg_project(project_code):
    """
    Retrieve project information from ShotGrid using the project code.

    Args:
        project_code (str): The ShotGrid project code to search for.

    Returns:
        dict: ShotGrid project information containing 'name' and 'id'.

    Raises:
        ProjectNotFound: If the project with the specified code is not found in ShotGrid.
    """
    sg = credentials.get_shotgrid_session()
    sg_project = sg.find_one(
        "Project",
        [["sg_code", "is", project_code]],
        ["name", "id"]
    )
    if not sg_project:
        msg = f"Project with 'sg_code':'{project_code}' not found."
        logger.error(msg)
        raise ProjectNotFound(msg)
    
    return sg_project

def create_project(project_code):
    """
    Create a new project in AYON, set up its folders, and synchronize with ShotGrid.

    This function retrieves the ShotGrid project, creates a corresponding AYON project,
    and sets up its folders and attributes. Additionally, it updates ShotGrid to enable auto-sync.

    Args:
        project_code (str): The ShotGrid project code to create and sync.

    Raises:
        ValueError: If the project creation in AYON fails.
    """
    sg_project = get_sg_project(project_code)
    project_name = sg_project["name"]

    # Create the AYON project
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

    # Update AYON project anatomy with ShotGrid id and enable push sync
    ayon_api.update_project(
        project_name=project_name,
        attrib={
            "shotgridId": sg_project["id"],
            "shotgridType": "Project",
            "shotgridPush": True,
        }
    )

    # Set up project folders in AYON
    project_folders.create_project_folders(project_name)

    # Enable auto-sync from AYON to ShotGrid in the Shotgrid project
    sg = credentials.get_shotgrid_session()
    sg.update(
        "Project",
        sg_project["id"],
        {
            "sg_ayon_auto_sync": True
        }
    )

def sync_shotgrid_to_ayon(project_code):
    """
    Trigger synchronization of a ShotGrid project to AYON.

    This function spawns an event to sync the project from ShotGrid to AYON.

    Args:
        project_code (str): The ShotGrid project code to sync.

    Logs:
        Success message upon successful synchronization event spawn.
    """
    sg_project = get_sg_project(project_code)
    project_name = sg_project["name"]

    server_api = ayon_api.GlobalServerAPI()
    dispatch_event = server_api.post(
        "events",
        topic="shotgrid.event.project.sync",
        project=project_name,
        description=f"Synchronize Project '{project_name}' from ShotGrid.",
        payload={
            "action": "sync-from-shotgrid",
            "project_name": project_name,
            "project_code": project_code,
            "project_code_field": "sg_code",
        },
        finished=True,
        store=True,
    )

    if dispatch_event.status_code == 200:
        logger.info(f"Successfully spawned event: {dispatch_event.data['id']}")

def sync_ayon_to_shotgrid(project_code):
    """
    Trigger synchronization of an AYON project to ShotGrid.

    This function spawns an event to sync the project from AYON to ShotGrid.

    Args:
        project_code (str): The ShotGrid project code to sync.

    Logs:
        Success message upon successful synchronization event spawn.
    """
    sg_project = get_sg_project(project_code)
    project_name = sg_project["name"]

    server_api = ayon_api.GlobalServerAPI()
    dispatch_event = server_api.post(
        "events",
        topic="shotgrid.event.project.sync",
        project=project_name,
        description=f"Synchronize Project '{project_name}' from AYON.",
        payload={
            "action": "sync-from-ayon",
            "project_name": project_name,
            "project_code": project_code,
            "project_code_field": "sg_code",
        },
        finished=True,
        store=True,
    )

    if dispatch_event.status_code == 200:
        logger.info(f"Successfully spawned event: {dispatch_event.data['id']}")
