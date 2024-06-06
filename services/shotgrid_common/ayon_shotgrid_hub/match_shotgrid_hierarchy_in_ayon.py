import collections
import shotgun_api3
from typing import Dict, List, Union

import ayon_api
from ayon_api.entity_hub import (
    ProjectEntity,
    FolderEntity,
)

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

from utils import get_logger


log = get_logger(__file__)


def match_shotgrid_hierarchy_in_ayon(
    entity_hub: ayon_api.entity_hub.EntityHub,
    sg_project: Dict,
    sg_session: shotgun_api3.Shotgun,
    sg_enabled_entities: List[str],
    project_code_field: str,
    custom_attribs_map: Dict[str, str]
):
    """Replicate a Shotgrid project into AYON.

    This function creates a "deck" which we keep increasing while traversing
    the Shotgrid project and finding new children, this is more efficient than
    creating a dictionary with the while Shotgrid project structure since we
    `popleft` the elements when processing them.

    Args:
        entity_hub (ayon_api.entity_hub.EntityHub): The AYON EntityHub.
        sg_project (dict): The Shotgrid project.
        sg_project (shotgun_api3.Shotgun): The Shotgrid session.
        project_code_field (str): The Shotgrid project code field.
    """
    log.info("Getting Shotgrid entities.")
    sg_ay_dicts, sg_ay_dicts_parents = get_sg_entities(
        sg_session,
        sg_project,
        sg_enabled_entities,
        project_code_field,
        custom_attribs_map,
    )

    sg_ay_dicts_deck = collections.deque()

    # Append the project's direct children.
    for sg_ay_dict_child_id in sg_ay_dicts_parents[sg_project["id"]]:
        sg_ay_dicts_deck.append(
            (entity_hub.project_entity, sg_ay_dict_child_id)
        )

    sg_project_sync_status = "Synced"
    processed_ids = set()

    while sg_ay_dicts_deck:
        (ay_parent_entity, sg_ay_dict_child_id) = sg_ay_dicts_deck.popleft()
        sg_ay_dict = sg_ay_dicts[sg_ay_dict_child_id]
        sg_entity_id = sg_ay_dict["attribs"][SHOTGRID_ID_ATTRIB]
        if sg_entity_id in processed_ids:
            msg = (
                f"Entity {sg_entity_id} already processed, skipping..."
                f"Sg Ay Dict: {sg_ay_dict} - "
                f"Ay Parent Entity: {ay_parent_entity}"
            )
            log.warning(msg)
            continue

        processed_ids.add(sg_entity_id)

        log.debug(f"Deck size: {len(sg_ay_dicts_deck)}")

        ay_entity = None
        sg_entity_sync_status = "Synced"

        ay_id = sg_ay_dict["data"].get(CUST_FIELD_CODE_ID)
        if ay_id:
            ay_entity = entity_hub.get_or_query_entity_by_id(
                ay_id, [sg_ay_dict["type"]])

        # If we haven't found the ay_entity by its id, check by its name
        # to avoid creating duplicates and erroring out
        if ay_entity is None:
            # Use min_length=0 so names like '_edit_shot' don't become 'edit_shot'
            name = slugify_string(sg_ay_dict["name"], min_length=0)
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
                    sg_ay_dict
                )

            # We only create new entities for Folders/Tasks entities
            # For Version entities we only try update the status if it already exists
            if not ay_entity and sg_ay_dict["type"] != "version":
                ay_entity = _create_new_entity(
                    entity_hub,
                    ay_parent_entity,
                    sg_ay_dict
                )
        else:
            ay_sg_id_attrib = ay_entity.attribs.get(
                SHOTGRID_ID_ATTRIB
            )

            # If the ShotGrid ID in AYON doesn't match the one in ShotGrid
            if str(ay_sg_id_attrib) != str(sg_entity_id):  # noqa
                log.error(
                    f"The AYON entity {ay_entity.name} <{ay_entity.id}> has the "  # noqa
                    f"ShotgridId {ay_sg_id_attrib}, while the ShotGrid ID "  # noqa
                    f"should be {sg_entity_id}"
                )
                sg_entity_sync_status = "Failed"
                sg_project_sync_status = "Failed"
            else:
                update_ay_entity_custom_attributes(
                    ay_entity,
                    sg_ay_dict,
                    custom_attribs_map,
                    ay_project=entity_hub.project_entity
                )

        # skip if no ay_entity is found
        # perhaps due Task with project entity as parent
        if not ay_entity:
            log.error(f"Entity {sg_ay_dict} not found in AYON.")
            continue

        # Update SG entity with new created data
        sg_ay_dict["data"][CUST_FIELD_CODE_ID] = ay_entity.id
        sg_ay_dicts[sg_entity_id] = sg_ay_dict

        # If the entity is not a "Folder" or "AssetCategory" we update the
        # entity ID and sync status in Shotgrid and AYON
        if (
            sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB] not in [
                "Folder", "AssetCategory"
            ]
            and (
                sg_ay_dict["data"][CUST_FIELD_CODE_ID] != ay_entity.id
                or sg_ay_dict["data"][CUST_FIELD_CODE_SYNC] != sg_entity_sync_status  # noqa
            )
        ):
            log.debug(
                "Updating AYON entity ID and sync status in SG and AYON")
            update_data = {
                CUST_FIELD_CODE_ID: ay_entity.id,
                CUST_FIELD_CODE_SYNC: sg_entity_sync_status
            }
            # Update Shotgrid entity with Ayon ID and sync status
            sg_session.update(
                sg_ay_dict["attribs"][SHOTGRID_TYPE_ATTRIB],
                sg_entity_id,
                update_data
            )
            ay_entity.data.update(update_data)

        # If the entity has children, add it to the deck
        for sg_child_id in sg_ay_dicts_parents.get(sg_entity_id, []):
            sg_ay_dicts_deck.append((ay_entity, sg_child_id))

    try:
        entity_hub.commit_changes()
    except Exception:
        log.error(
            "Unable to commit all entities to AYON!", exc_info=True)

    log.info(
        "Processed entities successfully!. "
        f"Amount of entities: {len(processed_ids)}"
    )
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

        if attrib_value is None:
            continue

        entity_hub.project_entity.attribs.set(
            ay_attrib,
            attrib_value
        )

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


def _create_new_entity(
    entity_hub: ayon_api.entity_hub.EntityHub,
    parent_entity: Union[ProjectEntity, FolderEntity],
    sg_ay_dict: Dict
):
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
        # only create if parent_entity type is not project
        if parent_entity.entity_type == "project":
            log.warning(
                f"Can't create task '{sg_ay_dict['name']}' under project "
                "'{parent_entity.name}'. Parent should not be project it self!"
            )
            return

        ay_entity = entity_hub.add_new_task(
            sg_ay_dict["task_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=parent_entity.id,
            attribs=sg_ay_dict["attribs"],
            data=sg_ay_dict["data"],
        )
    elif sg_ay_dict["type"].lower() == "folder":
        ay_entity = entity_hub.add_new_folder(
            sg_ay_dict["folder_type"],
            name=sg_ay_dict["name"],
            label=sg_ay_dict["label"],
            entity_id=sg_ay_dict["data"][CUST_FIELD_CODE_ID],
            parent_id=parent_entity.id,
            attribs=sg_ay_dict["attribs"],
            data=sg_ay_dict["data"],
        )

    status = sg_ay_dict.get("status")
    if status:
        # Entity hub expects the statuses to be provided with the `name` and
        # not the `short_name` (which is what we get from SG) so we convert
        # the short name back to the long name before setting it
        status_mapping = {
            status.short_name: status.name for status in entity_hub.project_entity.statuses
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
        ay_entity.tags = [tag["name"] for tag in tags]

    log.info(f"Created new entity: {ay_entity.name} ({ay_entity.id})")
    return ay_entity
