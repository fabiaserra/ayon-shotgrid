"""Module that handles creation, update or removal of AYON entities
based on ShotGrid Events.

The updates come through `meta` dictionaries such as:
"meta": {
    "id": 1274,
    "type": "entity_retirement",
    "entity_id": 1274,
    "class_name": "Shot",
    "entity_type": "Shot",
    "display_name": "bunny_099_012",
    "retirement_date": "2023-03-31 15:26:16 UTC"
}

And most of the times it fetches the ShotGrid entity as an Ayon dict like:
{
    "label": label,
    "name": name,
    SHOTGRID_ID_ATTRIB: ShotGrid id,
    CUST_FIELD_CODE_ID: ayon id stored in ShotGrid,
    CUST_FIELD_CODE_SYNC: sync status stored in ShotGrid,
    "type": the entity type,
}

"""
import shotgun_api3
import ayon_api
from typing import Dict, List, Optional

from utils import (
    get_asset_category,
    get_sg_entity_as_ay_dict,
    get_sg_entity_parent_field,
    update_ay_entity_custom_attributes,
)
from constants import (
    CUST_FIELD_CODE_ID,  # ShotGrid Field for the Ayon ID.
    SHOTGRID_ID_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_TYPE_ATTRIB,  # Ayon Entity Attribute.
    SHOTGRID_REMOVED_VALUE,  # Value for removed entities.
    SG_RESTRICTED_ATTR_FIELDS,
)

from utils import get_logger


log = get_logger(__file__)


def create_ay_entity_from_sg_event(
    sg_event: Dict,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_enabled_entities: List[str],
    project_code_field: str,
    custom_attribs_map: Optional[Dict[str, str]] = None
):
    """Create an AYON entity from a ShotGrid Event.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_enabled_entities (list[str]): List of entity strings enabled.
        project_code_field (str): The Shotgrid project code field.
        custom_attribs_map (Optional[dict]): A dictionary that maps ShotGrid
            attributes to Ayon attributes.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The newly
            created entity.
    """
    sg_parent_field = get_sg_entity_parent_field(
        sg_session,
        sg_project,
        sg_event["entity_type"],
        sg_enabled_entities,
    )
    extra_fields = [sg_parent_field]

    if sg_event["entity_type"] == "Asset":
        extra_fields.append("sg_asset_type")
        sg_parent_field = "sg_asset_type"

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        custom_attribs_map=custom_attribs_map,
        extra_fields=extra_fields,
    )
    log.debug(f"ShotGrid Entity as AYON dict: {sg_ay_dict}")
    if not sg_ay_dict:
        log.warning(
            "Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in ShotGrid, aborting..."
        )
        return

    if sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        # Revived entity, check if it's still in the Server
        ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
            sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
            [sg_ay_dict["type"]]
        )

        if ay_entity:
            log.debug("ShotGrid Entity exists in AYON.")
            # Ensure Ayon Entity has the correct ShotGrid ID
            ayon_entity_sg_id = str(
                ay_entity.attribs.get(SHOTGRID_ID_ATTRIB, "")
            )
            sg_entity_sg_id = str(
              sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
            )
            if ayon_entity_sg_id != sg_entity_sg_id:
                ay_entity.attribs.set(
                    SHOTGRID_ID_ATTRIB,
                    sg_entity_sg_id
                )
                ay_entity.attribs.set(
                    SHOTGRID_TYPE_ATTRIB,
                    sg_ay_dict["type"]
                )

            update_ay_entity_custom_attributes(
                ay_entity,
                sg_ay_dict,
                custom_attribs_map,
                ay_project=ayon_entity_hub.project_entity
            )

            return ay_entity

    # INFO: Parent entity might not be added in SG so this needs to be handled
    #       with optional way.
    if sg_ay_dict["data"].get(sg_parent_field) is None:
        # Parent is the project
        log.debug(f"ShotGrid Parent is the Project: {sg_project}")
        ay_parent_entity = ayon_entity_hub.project_entity
    elif (
        sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB] == "Asset"
        and sg_ay_dict["data"].get("sg_asset_type")
    ):
        log.debug("ShotGrid Parent is an Asset category.")
        ay_parent_entity = get_asset_category(
            ayon_entity_hub,
            ayon_entity_hub.project_entity,
            sg_ay_dict,
        )

    else:
        # Find parent entity ID
        sg_parent_entity_dict = get_sg_entity_as_ay_dict(
            sg_session,
            sg_ay_dict["data"][sg_parent_field]["type"],
            sg_ay_dict["data"][sg_parent_field]["id"],
            project_code_field,
        )

        log.debug(f"ShotGrid Parent entity: {sg_parent_entity_dict}")
        ay_parent_entity = ayon_entity_hub.get_or_query_entity_by_id(
            sg_parent_entity_dict["data"].get(CUST_FIELD_CODE_ID),
            [
                (
                    "task"
                    if sg_parent_entity_dict["type"] == "task"
                    else "folder"
                )
            ],
        )

    if not ay_parent_entity:
        # This really should be an edge  ase, since any parent event would
        # happen before this... but hey
        raise ValueError(
            "Parent does not exist in Ayon, try doing a Project Sync.")

    if sg_ay_dict["type"].lower() == "task":
        ay_entity = ayon_entity_hub.add_new_task(
            sg_ay_dict["task_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=ay_parent_entity.id,
            attribs=sg_ay_dict["attribs"]
        )
    elif sg_ay_dict["type"].lower() == "folder":
        ay_entity = ayon_entity_hub.add_new_folder(
            sg_ay_dict["folder_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=ay_parent_entity.id,
            attribs=sg_ay_dict["attribs"]
        )

    if not ay_entity:
        return
    
    log.debug(f"Created new AYON entity: {ay_entity}")
    ay_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    ay_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB, "")
    )

    status = sg_ay_dict.get("status")
    if status:
        # Entity hub expects the statuses to be provided with the `name` and
        # not the `short_name` (which is what we get from SG) so we convert
        # the short name back to the long name before setting it
        status_mapping = {
            status.short_name: status.name
            for status in ayon_entity_hub.project_entity.statuses
        }
        new_status_name = status_mapping.get(status)
        if not new_status_name:
            log.warning(
                "Status with short name '%s' doesn't exist in project", status
            )
        else:
            try:
                # INFO: it was causing error so trying to set status directly
                ay_entity.status = new_status_name
            except ValueError as e:
                # `ValueError: Status ip is not available on project.`
                # NOTE: this doesn't really raise exception?
                log.warning(f"Status sync not implemented: {e}")

    assignees = sg_ay_dict.get("assignees")
    if assignees:
        try:
            # INFO: it was causing error so trying to set status directly
            ay_entity.assignees = assignees
        except ValueError as e:
            log.warning(f"Assignees sync not implemented: {e}")

    tags = sg_ay_dict.get("tags")
    if tags:
        try:
            # INFO: it was causing error so trying to set status directly
            ay_entity.tags = [tag["name"] for tag in tags]
        except ValueError as e:
            log.warning(f"Tags sync not implemented: {e}")

    try:
        ayon_entity_hub.commit_changes()

        sg_session.update(
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
            sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
            {
                CUST_FIELD_CODE_ID: ay_entity.id
            }
        )
    except Exception:
        log.error("AYON Entity could not be created", exc_info=True)

    return ay_entity


def update_ayon_entity_from_sg_event(
    sg_event: Dict,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    sg_enabled_entities: List[str],
    project_code_field: str,
    custom_attribs_map: Optional[Dict[str, str]] = None
):
    """Try to update an entity in Ayon.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_enabled_entities (list[str]): List of entity strings enabled.
        project_code_field (str): The ShotGrid project code field.
        custom_attribs_map (dict): A dictionary that maps ShotGrid
            attributes to Ayon attributes.

    Returns:
        ay_entity (ayon_api.entity_hub.EntityHub.Entity): The modified entity.

    """
    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        custom_attribs_map=custom_attribs_map
    )

    if not sg_ay_dict:
        log.warning(
            f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in ShotGrid, aborting..."
        )
        return

    # if the entity does not have an Ayon ID, try to create it
    # and no need to update
    if not sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        log.debug(f"Creating AYON Entity: {sg_ay_dict}")
        try:
            create_ay_entity_from_sg_event(
                sg_event,
                sg_project,
                sg_session,
                ayon_entity_hub,
                sg_enabled_entities,
                project_code_field,
                custom_attribs_map
            )
        except Exception:
            log.error("AYON Entity could not be created", exc_info=True)
        return

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
        [sg_ay_dict["type"]]
    )

    if not ay_entity:
        raise ValueError("Unable to update a non existing entity.")

    # make sure the entity is not immutable
    if (
        ay_entity.immutable_for_hierarchy
        and sg_event["attribute_name"] in SG_RESTRICTED_ATTR_FIELDS
    ):
        raise ValueError("Entity is immutable, aborting...")

    # Ensure Ayon Entity has the correct ShotGrid ID
    ayon_entity_sg_id = str(
        ay_entity.attribs.get(SHOTGRID_ID_ATTRIB, "")
    )
    sg_entity_sg_id = str(
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    log.debug(f"Updating Ayon Entity: {ay_entity.name}")

    if ayon_entity_sg_id and ayon_entity_sg_id != sg_entity_sg_id:
        log.error(
            "Mismatching ShotGrid IDs ('%s' (AYON) != '%s' (SG)), aborting...",
            ayon_entity_sg_id, sg_entity_sg_id
        )
        raise ValueError("Mismatching ShotGrid IDs, aborting...")

    ay_entity.name = sg_ay_dict["name"]
    ay_entity.label = sg_ay_dict["label"]

    # TODO: Only update the updated fields in the event
    update_ay_entity_custom_attributes(
        ay_entity,
        sg_ay_dict,
        custom_attribs_map,
        ay_project=ayon_entity_hub.project_entity
    )

    ayon_entity_hub.commit_changes()

    if sg_ay_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        sg_session.update(
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
            sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
            {
                CUST_FIELD_CODE_ID: ay_entity.id
            }
        )
    
    ay_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    ay_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB, "")
    )

    return ay_entity


def remove_ayon_entity_from_sg_event(
    sg_event: Dict,
    sg_session: shotgun_api3.Shotgun,
    ayon_entity_hub: ayon_api.entity_hub.EntityHub,
    project_code_field: str,
):
    """Try to remove an entity in Ayon.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        project_code_field (str): The ShotGrid field that contains the Ayon ID.
    """
    # for now we are ignoring Task type entities
    # TODO: Handle Task entities
    # if sg_event["entity_type"] == "Task":
    #     log.info("Ignoring Task entity.")
    #     return

    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        retired_only=True
    )

    if not sg_ay_dict:
        sg_ay_dict = get_sg_entity_as_ay_dict(
            sg_session,
            sg_event["entity_type"],
            sg_event["entity_id"],
            project_code_field,
            retired_only=False,
        )
        if sg_ay_dict:
            log.info(
                f"No need to remove entity {sg_event['entity_type']} "
                f"<{sg_event['entity_id']}>, it's not retired anymore."
            )
            return
        else:
            log.warning(
                f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
                "no longer exists in ShotGrid."
            )

    if not sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        log.warning(
            "Entity does not have an Ayon ID, aborting..."
        )
        return

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
        ["task" if sg_ay_dict.get("type").lower() == "task" else "folder"]
    )

    if not ay_entity:
        raise ValueError("Unable to update a non existing entity.")

    if sg_ay_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        raise ValueError("Mismatching ShotGrid IDs, aborting...")

    if not ay_entity.immutable_for_hierarchy:
        log.info(f"Deleting AYON entity: {ay_entity}")
        ayon_entity_hub.delete_entity(ay_entity)
    else:
        log.info("Entity is immutable.")
        ay_entity.attribs.set(SHOTGRID_ID_ATTRIB, SHOTGRID_REMOVED_VALUE)

    ayon_entity_hub.commit_changes()


def sync_user(
    sg_user_id: int,
    sg_session: shotgun_api3.Shotgun
):
    """
    Synchronize a ShotGrid user with the AYON system, including their permissions and project access.

    Args:
        sg_user_id (int): The ShotGrid user ID to be synced.
        sg_session (shotgun_api3.Shotgun): The authenticated ShotGrid session.

    Logs:
        Logs success and failure of various synchronization steps.

    Steps:
        1. Fetch the user data from ShotGrid.
        2. Check if the user exists in AYON. If not, create a new user.
        3. Synchronize user permissions (admin, manager, developer).
        4. If the user is not an admin, manager, or executive, synchronize their project-specific access.
    
    Returns:
        None. Logs errors and early exits if user is not found or API calls fail.
    """
    
    # Fetch user data from ShotGrid
    sg_user = sg_session.find_one(
        "HumanUser",
        [["id", "is", sg_user_id]],
        ["login", "name", "email", "projects", "permission_rule_set"],
    )
    if not sg_user:
        log.error(f"Unable to find user with id '{sg_user_id}' in ShotGrid.")
        return
    
    login = sg_user["login"]
    server_api = ayon_api.GlobalServerAPI()

    # Check if the user already exists in AYON
    ayon_user = ayon_api.get_user(username=login)
    if not ayon_user:
        create_new_user_in_ayon(server_api, login, sg_user["email"], sg_user["name"])

    # Log permission group syncing process
    log.info(f"Syncing permission group role for user: {login}")
    permission_group = sg_user["permission_rule_set"]["name"].lower()

    # Map permission group to access data
    access_data = {
        "isAdmin": permission_group == "admin",
        "isManager": permission_group in ["executive", "management", "lead"],
        "isDeveloper": permission_group == "admin",
    }

    # Update user's access data in AYON
    response = server_api.patch(f"users/{login}", data=access_data, active=True)
    if response.status_code != 204:
        log.error(f"Unable to set access level for user {login}: {response.text}")
        return

    # If the user is an artist sync project-specific access groups
    if permission_group == "artist":
        log.info(f"Syncing project access groups for user: {login}")
        
        # Get existing AYON projects and ShotGrid projects the user is assigned to
        ayon_projects = ayon_api.get_projects()
        ayon_project_names = {project["name"] for project in ayon_projects}
        sg_project_names = {
            ayon_api.slugify_string(project["name"]) for project in sg_user["projects"]
        }
        
        # Assign access groups to matching projects in AYON
        access_groups = [
            {"project": project_name, "accessGroups": [permission_group]}
            for project_name in sg_project_names
            if project_name in ayon_project_names
        ]
        response = server_api.patch(f"users/{login}/accessGroups", accessGroups=access_groups)
        if response.status_code != 204:
            log.error(f"Unable to assign access groups to user {login}: {response.text}")


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
        log.error(f"Unable to create user {login} in AYON! {response.text}")
