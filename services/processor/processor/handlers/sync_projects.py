"""Sync Projects - A `processor.handler` to ensure two Projects
are in sync between AYON and Shotgrid, uses the `AyonShotgridHub`.
"""
from ayon_shotgrid_hub import AyonShotgridHub


REGISTER_EVENT_TYPE = ["sync-from-shotgrid", "sync-from-ayon"]


def process_event(
    sg_processor,
    event,
):
    """Synchronize a project between AYON and Shotgrid.

    Events with the action `sync-from-shotgrid` or `sync-from-ayon` will
    trigger this function, where we traverse a whole project, either in
    Shotgrid or AYON, and replicate it's structure in the other platform.
    """
    hub = AyonShotgridHub(
        sg_processor.get_sg_connection(),
        event.get("project_name"),
        event.get("project_code"),
        sg_project_code_field=sg_processor.sg_project_code_field,
        custom_attribs_map=sg_processor.custom_attribs_map,
        custom_attribs_types=sg_processor.custom_attribs_types,
        sg_enabled_entities=sg_processor.sg_enabled_entities,
    )

    # This will ensure that the project exists in both platforms.
    hub.create_project()
    sync_source = (
        "ayon" if event.get("action") == "sync-from-ayon" else "shotgrid")
    hub.synchronize_projects(source=sync_source)
