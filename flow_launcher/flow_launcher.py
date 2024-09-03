import sys
try:
    from urlparse import parse_qs
except ImportError:
    from urllib.parse import parse_qs

import ayon_api
from ayon_applications import utils
from ayon_shotgrid.lib import credentials
from ayon_core.addon import AddonsManager


def main(args):
    """
    Launch AYON managed applications through Flow.

    This function processes a URL passed as a command-line argument. The URL is expected 
    to be in the format of a Shotgrid/Flow protocol query from an action menu item. The function 
    parses the URL to extract the relevant task information, retrieves the corresponding 
    AYON data, and launches the appropriate application.

    Args:
        args (list): Command-line arguments passed to the script, where the last argument 
                     is a URL in the format:
                     "flow-launcher://app_name?project_name=<project>&ids=<task_id>&other_param=value"

    Returns:
        None: Exits the script with a status code.
    """
    
    print("Running custom AYON Flow launcher")

    # Ensure the last argument contains a ':' symbol, indicating a valid URL format
    if ":" not in args[-1]:
        sys.exit("The argument is a URL and requires the symbol ':'")

    # Split the argument on the first occurrence of ':'
    _, full_path = args[-1].split(":", 1)

    # Check if there is a query string in the URL, and parse it if present
    if "?" in full_path:
        path, query_string = full_path.split("?", 1)
        action = path.strip("/")
        params = parse_qs(query_string)
    else:
        action = full_path.strip("/")
        params = {}

    # Establish a ShotGrid session
    sg = credentials.get_shotgrid_session()

    # Extract the project name from the parameters
    project_name = params.get("project_name", [None])[0]

    if not project_name:
        sys.exit("Project name is missing in the URL parameters.")

    # Iterate over the selected task IDs
    task_ids = params.get("ids", [""])[0].split(",")
    for sg_id in task_ids:
        sg_task = sg.find_one(
            "Task",
            [["id", "is", int(sg_id)]],
            ["sg_ayon_id"],
        )
        ayon_id = sg_task.get("sg_ayon_id")
        if not ayon_id:
            print(f"No 'sg_ayon_id' found for task with id {sg_id}")
            continue

        # Retrieve the task and folder entities from AYON
        task_entity = ayon_api.get_task_by_id(project_name, ayon_id, fields={"name", "folderId"})
        folder_entity = ayon_api.get_folder_by_id(
            project_name, task_entity["folderId"], fields={"path"}
        )

        # Get applications available for the current context
        applications = utils.get_applications_for_context(
            project_name, folder_entity, task_entity
        )

        # Filter and find the application that matches the action
        matching_apps = [app for app in applications if action == app.split("/")[0]]

        if not matching_apps:
            print(f"No matching applications found for action: {action}")
            continue

        # Get the latest version of the application
        latest_version_app = max(matching_apps)

        # Launch the application using the AddonsManager
        manager = AddonsManager()
        app_addon = manager.get("applications")
        app_addon.launch_application(
            latest_version_app, project_name, folder_entity["path"], task_entity["name"]
        )


if __name__ == '__main__':
    sys.exit(main(sys.argv[1:]))