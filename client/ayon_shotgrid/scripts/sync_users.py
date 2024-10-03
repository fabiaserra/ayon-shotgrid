import ayon_api
from ayon_core.lib import Logger

from ayon_shotgrid.lib import credentials


logger = Logger.get_logger(__name__)


def sync_users():
    """
    Synchronize users between ShotGrid and AYON.

    This function retrieves users from both systems, creates new users in AYON
    if they don't exist, and updates access groups for all users.
    """
    ayon_users = ayon_api.get_users(fields={"active", "name", "accessGroups"})
    ayon_user_names = {user["name"] for user in ayon_users}
    ayon_projects = ayon_api.get_projects()
    ayon_project_names = {project["name"] for project in ayon_projects}
    server_api = ayon_api.GlobalServerAPI()

    sg_users = get_shotgrid_users()
    for sg_user in sg_users:
        login = sg_user["login"]
        if login not in ayon_user_names:
            logger.info(f"Creating user: {login}")
            create_new_user_in_ayon(server_api, login, sg_user["email"], sg_user["name"])

        # Define permission group on the user
        logger.info(f"Syncing permission group role for user: {login}")
        permission_group = sg_user["permissionGroup"]
        access_data = {
            "isAdmin": permission_group == "admin",
            "isManager": permission_group in ["executive", "management"],
            "isDeveloper": permission_group == "admin",
        }
        response = server_api.patch(f"users/{login}", data=access_data, active=True)
        if response.status_code != 204:
            logger.error(f"Unable to set access level to user {login}: {response.text}")

        # If user role is not one of 'admin', 'executive' or 'management'
        # we check which projects they are assigned to so we give them access
        # individually. Those roles have access to all projects by default
        # and that's why we don't need to do any granular permission access
        if permission_group not in ["admin", "executive", "management"]:
            logger.info(f"Syncing access project groups for user: {login}")
            access_groups = [
                {"project": project_name, "accessGroups": [sg_user["permissionGroup"]]}
                for project_name in sg_user["projectNames"]
                if project_name in ayon_project_names
            ]
            response = server_api.patch(f"users/{login}/accessGroups", accessGroups=access_groups)
            if response.status_code != 204:
                logger.error(f"Unable to assign access groups to user {login}: {response.text}")


def get_shotgrid_users():
    """
    Retrieve and format active users from ShotGrid.

    Returns:
        list: A list of dictionaries containing user information.
    """
    sg = credentials.get_shotgrid_session()
    sg_users = sg.find(
        "HumanUser",
        [["sg_status_list", "is", "act"]],
        ["login", "name", "email", "projects", "permission_rule_set"],
    )

    users_to_ignore = {"dummy", "root", "support"}
    return [
        {
            "login": sg_user["login"],
            "name": sg_user["name"],
            "email": sg_user["email"],
            "projectNames": [
                ayon_api.slugify_string(project["name"])
                for project in sg_user["projects"]
            ],
            "permissionGroup": sg_user["permission_rule_set"]["name"].lower(),
        }
        for sg_user in sg_users
        if not any(ignore in sg_user["email"] for ignore in users_to_ignore)
    ]


def create_new_user_in_ayon(server_api, login, email, name):
    """
    Create a new user in AYON.

    Args:
        server_api: The AYON server API instance.
        login (str): User's login.
        email (str): User's email.
        name (str): User's full name.
    """
    response = server_api.put(
        f"users/{login}",
        active=True,
        attrib={"fullName": name, "email": email},
        password=login,
    )
    if response.status_code != 200:
        logger.error(f"Unable to create user {login} in AYON! {response.text}")