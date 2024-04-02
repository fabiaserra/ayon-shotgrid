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
    SHOTGRID_REMOVED_VALUE
)

from nxtools import logging

def create_ay_entity_from_sg_event(
    sg_event,
    sg_project,
    sg_session,
    ayon_entity_hub,
    sg_enabled_entities,
    project_code_field,
    custom_attribs_map=None,
):
    """Create an AYON entity from a ShotGrid Event.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_project (dict): The ShotGrid project.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_enabled_entities (list[str]): List of entity strings enabled.
        project_code_field (str): The Shotgrid project code field.
        custom_attribs_map (dict): Dictionary that maps a list of attribute names from
            Ayon to Shotgrid.

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
    logging.debug(f"ShotGrid Entity as AYON dict: {sg_ay_dict}")
    if not sg_ay_dict:
        logging.warning(
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
            logging.debug(f"ShotGrid Entity exists in AYON.")
            # Ensure Ayon Entity has the correct ShotGrid ID
            ayon_entity_sg_id = str(
                ay_entity.attribs.get_attribute(SHOTGRID_ID_ATTRIB).value)
            # Ensure Ayon Entity has the correct Shotgrid ID
            ay_shotgrid_id = str(
              sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, ""))
            if ayon_entity_sg_id != ay_shotgrid_id:
                ay_entity.attribs.set(
                    SHOTGRID_ID_ATTRIB,
                    ay_shotgrid_id
                )
                ay_entity.attribs.set(
                    SHOTGRID_TYPE_ATTRIB,
                    sg_ay_dict["type"]
                )
            
            update_ay_entity_custom_attributes(
                ay_entity, sg_ay_dict, custom_attribs_map
            )

            return ay_entity

    if sg_ay_dict["data"][sg_parent_field] is None:
        # Parent is the project
        logging.debug(f"ShotGrid Parent is the Project: {sg_project}")
        ay_parent_entity = ayon_entity_hub.project_entity
    else:
        if sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB] == "Asset" and sg_ay_dict["data"].get("sg_asset_type"):
            logging.debug(f"ShotGrid Parent is an Asset category.")

            ay_parent_entity = get_asset_category(
                ayon_entity_hub,
                ayon_entity_hub.project_entity,
                sg_ay_dict.get("sg_asset_type").lower()
            )

        else:
            # Find parent entity ID
            sg_parent_entity_dict = get_sg_entity_as_ay_dict(
                sg_session,
                sg_ay_dict["data"][sg_parent_field]["type"],
                sg_ay_dict["data"][sg_parent_field]["id"],
                project_code_field,
            )

            logging.debug(f"ShotGrid Parent entity: {sg_parent_entity_dict}")
            ay_parent_entity = ayon_entity_hub.get_or_query_entity_by_id(
                sg_parent_entity_dict["data"].get(CUST_FIELD_CODE_ID),
                ["task" if sg_parent_entity_dict["data"].get(CUST_FIELD_CODE_ID).lower() == "task" else "folder"]
            )

    if not ay_parent_entity:
        # This really should be an edge  ase, since any parent event would
        # happen before this... but hey
        raise ValueError("Parent does not exist in Ayon, try doing a Project Sync.")

    if sg_ay_dict["type"].lower() == "task":
        ay_entity = ayon_entity_hub.add_new_task(
            sg_ay_dict["task_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=ay_parent_entity.id,
            attribs=sg_ay_dict["attribs"]
        )
    else:
        ay_entity = ayon_entity_hub.add_new_folder(
            sg_ay_dict["folder_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=ay_parent_entity.id,
            attribs=sg_ay_dict["attribs"]
        )

    logging.debug(f"Created new AYON entity: {ay_entity}")
    ay_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    ay_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        sg_ay_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB, "")
    )

    try:
        ayon_entity_hub.commit_changes()

        sg_session.update(
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
            sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
            {
                CUST_FIELD_CODE_ID: ay_entity.id
            }
        )
    except Exception as e:
        logging.error(e)
        pass

    return ay_entity


def update_ayon_entity_from_sg_event(
    sg_event,
    sg_session,
    ayon_entity_hub,
    project_code_field,
    custom_attribs_map
):
    """Try to update an entity in Ayon.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
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

    if not sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        logging.warning("ShotGrid Missing Ayon ID")

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
        [sg_ay_dict["type"]]
    )

    if not ay_entity:
        logging.error("Unable to update a non existing entity.")
        raise ValueError("Unable to update a non existing entity.")

    logging.debug(f"Updating Ayon Entity: {ay_entity.name}")
    # Ensure Ayon Entity has the correct ShotGrid ID
    ayon_entity_sg_id = str(
        ay_entity.attribs.get_attribute(SHOTGRID_ID_ATTRIB).value)
    sg_entity_sg_id = str(
        sg_ay_dict["attribs"].get(SHOTGRID_ID_ATTRIB, "")
    )
    if ayon_entity_sg_id != sg_entity_sg_id:
        logging.error("Mismatching ShotGrid IDs, aborting...")
        raise ValueError("Mismatching ShotGrid IDs, aborting...")

    logging.debug("Updating Ayon entity with '%s'" % sg_ay_dict)
    ay_entity.name = sg_ay_dict["name"]
    ay_entity.label = sg_ay_dict["label"]

    # TODO: Only update the updated fields in the event
    update_ay_entity_custom_attributes(
        ay_entity, sg_ay_dict, custom_attribs_map
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

    return ay_entity


def remove_ayon_entity_from_sg_event(
    sg_event,
    sg_session,
    ayon_entity_hub,
    project_code_field
):
    """Try to remove an entity in Ayon.

    Args:
        sg_event (dict): The `meta` key from a ShotGrid Event.
        sg_session (shotgun_api3.Shotgun): The ShotGrid API session.
        ayon_entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        project_code_field (str): The ShotGrid field that contains the Ayon ID.
    """
    sg_ay_dict = get_sg_entity_as_ay_dict(
        sg_session,
        sg_event["entity_type"],
        sg_event["entity_id"],
        project_code_field,
        retired_only=True
    )

    logging.debug(f"ShotGrid Entity as Ay dict: {sg_ay_dict}")
    if not sg_ay_dict:
        logging.warning(
            f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in ShotGrid."
        )
        raise ValueError(
            f"Entity {sg_event['entity_type']} <{sg_event['entity_id']}> "
            "no longer exists in ShotGrid."
        )

    if not sg_ay_dict["data"].get(CUST_FIELD_CODE_ID):
        logging.warning("ShotGrid Missing Ayon ID")
        raise ValueError("ShotGrid Missing Ayon ID")

    ay_entity = ayon_entity_hub.get_or_query_entity_by_id(
        sg_ay_dict["data"].get(CUST_FIELD_CODE_ID),
        ["task" if sg_ay_dict.get("type").lower() == "task" else "folder"]
    )

    if not ay_entity:
        logging.error("Unable to update a non existing entity.")
        raise ValueError("Unable to update a non existing entity.")

    if sg_ay_dict["data"].get(CUST_FIELD_CODE_ID) != ay_entity.id:
        logging.error("Mismatching Shotgrid IDs, aborting...")
        raise ValueError("Mismatching Shotgrid IDs, aborting...")

    if not ay_entity.immutable_for_hierarchy:
        logging.info(f"Deleting AYON entity: {ay_entity}")
        ayon_entity_hub.delete_entity(ay_entity)
    else:
        logging.info("Entity is immutable.")
        ay_entity.attribs.set(SHOTGRID_ID_ATTRIB, SHOTGRID_REMOVED_VALUE)

    ayon_entity_hub.commit_changes()
