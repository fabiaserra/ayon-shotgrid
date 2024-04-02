import collections

from ayon_api import slugify_string

from constants import (
    CUST_FIELD_CODE_ID,
    CUST_FIELD_CODE_SYNC,
    SHOTGRID_ID_ATTRIB,
    SHOTGRID_TYPE_ATTRIB,
)

from utils import (
    get_sg_entities,
    get_asset_category,
    update_ay_entity_custom_attributes,
)

from nxtools import logging, log_traceback


def match_shotgrid_hierarchy_in_ayon(
    entity_hub,
    sg_project,
    sg_session,
    sg_enabled_entities,
    project_code_field,
    custom_attribs_map,
):
    """Replicate a Shotgrid project into AYON.

    This function creates a "deck" which we keep increasing while traversing
    the Shotgrid project and finding new childrens, this is more efficient than
    creating a dictionary with the whle Shotgrid project structure since we
    `popleft` the elements when procesing them.

    Args:
        entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_project (shotgun_api3.Shotgun): The Shotgrid session.
        project_code_field (str): The Shotgrid project code field.
    """
    logging.info("Getting Shotgrid entities.")
    sg_ay_dicts, sg_ay_dicts_parents = get_sg_entities(
        sg_session,
        sg_project,
        sg_enabled_entities,
        project_code_field,
        custom_attribs_map,
    )

    sg_ay_dicts_deck = collections.deque()

    # Append the project's direct children.
    for sg_ay_dict_child in sg_ay_dicts_parents[sg_project["id"]]:
        sg_ay_dicts_deck.append((entity_hub.project_entity, sg_ay_dict_child))

    sg_project_sync_status = "Synced"

    while sg_ay_dicts_deck:
        (ay_parent_entity, sg_ay_dict) = sg_ay_dicts_deck.popleft()
        logging.debug(f"Processing {sg_ay_dict} with parent {ay_parent_entity}")

        ay_entity = None
        sg_entity_sync_status = "Synced"

        ay_id = sg_ay_dict["data"].get(CUST_FIELD_CODE_ID)
        if ay_id:
            ay_entity = entity_hub.get_or_query_entity_by_id(
                ay_id, [sg_ay_dict["type"]])

        # If we haven't found the ay_entity by its id, check by its name
        # to avoid creating duplicates and erroring out
        if ay_entity is None:
            name = slugify_string(sg_ay_dict["name"])
            for child in ay_parent_entity.children:
                if child.name.lower() == name.lower():
                    ay_entity = child
                    break

        # If we couldn't find it we create it.
        if ay_entity is None:
            if sg_ay_dict["attribs"].get(SHOTGRID_TYPE_ATTRIB) == "AssetCategory":  # noqa
                ay_entity = get_asset_category(
                    entity_hub,
                    ay_parent_entity,
                    sg_ay_dict["name"]
                )

            if not ay_entity:
                ay_entity = _create_new_entity(
                    entity_hub,
                    ay_parent_entity,
                    sg_ay_dict
                )
        else:
            logging.debug(
                f"Entity {ay_entity.name} <{ay_entity.id}> exists in AYON. "
                "Making sure the stored Shotgrid Data matches."
            )

            ay_sg_id_attrib = ay_entity.attribs.get(
                SHOTGRID_ID_ATTRIB
            )

            if ay_sg_id_attrib != str(sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]): # noqa
                logging.error(
                    f"The AYON entity {ay_entity.name} <{ay_entity.id}> has the "  # noqa
                    f"ShotgridId {ay_sg_id_attrib}, while the Shotgrid ID "  # noqa
                    f"should be {sg_ay_dict['attribs'][SHOTGRID_ID_ATTRIB]}"
                )
                sg_entity_sync_status = "Failed"
                sg_project_sync_status = "Failed"
            else:
                update_ay_entity_custom_attributes(
                    ay_entity, sg_ay_dict, custom_attribs_map
                )

        # Update SG entity with new created data
        sg_ay_dict["data"][CUST_FIELD_CODE_ID] = ay_entity.id
        sg_ay_dicts[sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]] = sg_ay_dict

        entity_id = sg_ay_dict["name"]

        if sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB] not in [
                "Folder", "AssetCategory"]:
            if (
                sg_ay_dict["data"][CUST_FIELD_CODE_ID] != ay_entity.id
                or sg_ay_dict["data"][CUST_FIELD_CODE_SYNC] != sg_entity_sync_status  # noqa
            ):
                update_data = {
                    CUST_FIELD_CODE_ID: ay_entity.id,
                    CUST_FIELD_CODE_SYNC: sg_ay_dict["data"][CUST_FIELD_CODE_SYNC]  # noqa
                }
                sg_session.update(
                    sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
                    sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB],
                    update_data
                )

            entity_id = sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]

        try:
            entity_hub.commit_changes()
        except Exception as e:
            logging.error(f"Unable to create entity {sg_ay_dict} in AYON!")
            log_traceback(e)

        # If the entity has children, add it to the deck
        for sg_child in sg_ay_dicts_parents.get(entity_id, []):
            sg_ay_dicts_deck.append((ay_entity, sg_child))

    # Sync project attributes from Shotgrid to AYON
    entity_hub.project_entity.attribs.set(
        SHOTGRID_ID_ATTRIB,
        sg_project["id"]
    )
    entity_hub.project_entity.attribs.set(
        SHOTGRID_TYPE_ATTRIB,
        "Project"
    )
    for ay_attrib, sg_attrib in custom_attribs_map.items():
        attrib_value = sg_project.get(sg_attrib) \
            or sg_project.get(f"sg_{sg_attrib}")
        
        logging.debug(f"Checking {sg_attrib} -> {attrib_value}")
        if attrib_value is None:
            continue

        entity_hub.project_entity.attribs.set(
            ay_attrib,
            attrib_value
        )

    # Hard-code the query of status for SG project as it's different
    # than the other entities
    entity_hub.project_entity.status = sg_project.get("sg_status")

    entity_hub.commit_changes()

    # Update Shotgrid project with Ayon ID and sync status
    sg_session.update(
        "Project",
        sg_project["id"],
        {
            CUST_FIELD_CODE_ID: entity_hub.project_entity.id,
            CUST_FIELD_CODE_SYNC: sg_project_sync_status
        }
    )


def _create_new_entity(entity_hub, parent_entity, sg_ay_dict):
    """Helper method to create entities in the EntityHub.

    Task Creation:
        https://github.com/ynput/ayon-python-api/blob/30d702618b58676c3708f09f131a0974a92e1002/ayon_api/entity_hub.py#L284

    Folder Creation:
        https://github.com/ynput/ayon-python-api/blob/30d702618b58676c3708f09f131a0974a92e1002/ayon_api/entity_hub.py#L254


    Args:
        entity_hub (ayon_api.EntityHub): The project's entity hub.
        parent_entity: Ayon parent entity.
        sg_ay_dict (dict): Ayon ShotGrid entity to create.
    """
    if sg_ay_dict["type"].lower() == "task":
        ay_entity = entity_hub.add_new_task(
            sg_ay_dict["task_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=parent_entity.id,
            attribs=sg_ay_dict["attribs"],
            data=sg_ay_dict["data"],
        )
    else:
        ay_entity = entity_hub.add_new_folder(
            sg_ay_dict["folder_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=parent_entity.id,
            attribs=sg_ay_dict["attribs"],
            data=sg_ay_dict["data"],
        )

    logging.debug(f"Created new entity: {ay_entity.name} ({ay_entity.id})")
    logging.debug(f"Parent is: {parent_entity.name} ({parent_entity.id})")
    return ay_entity
