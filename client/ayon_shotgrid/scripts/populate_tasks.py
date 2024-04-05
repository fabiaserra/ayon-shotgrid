from ayon_core.lib import Logger

from ayon_shotgrid.lib import credentials


logger = Logger.get_logger(__name__)


# Dictionary that maps task names that we use with the SG step code
# corresponding to that task
TASK_NAME_TO_STEP_MAP = {
    "2dtrack": "2dTrk",
    "3dtrack": "3dTrk"
}


def add_tasks_to_sg_entities(project, sg_entities, entity_type, tasks):
    """Add given tasks to the SG entities of the specified entity type.

    Args:
        project (dict): A dictionary representing the SG project to which the
            tasks will be added.
        sg_entities (list): A list of dictionaries representing the SG entities
            to which the tasks will be added.
        entity_type (str): A string representing the type of SG entity to which
            the tasks will be added.
    """
    sg = credentials.get_shotgrid_session()

    # Create list of dictionaries with the common data we will be using to
    # create all tasks
    # NOTE: we do this outside of the other for loop as we don't want to query
    # the pipeline step for each single entity
    tasks_data = []
    for task_name, step_name in tasks.items():

        # Override step name if it's on the name -> step dictionary
        if task_name in TASK_NAME_TO_STEP_MAP:
            step_name = TASK_NAME_TO_STEP_MAP[task_name]

        step = sg.find_one(
            "Step",
            [["code", "is", step_name], ["entity_type", "is", entity_type]],
            ["code"]
        )
        # There may not be a task step for this entity_type or task_name
        if not step:
            logger.info(
                "No step found for entity type '%s' with step type '%s'", entity_type, step_name
                )
            continue

        # Create a task for this entity
        task_data = {
            "project": project,
            "content": task_name,
            "step": step,
        }
        tasks_data.append(task_data)

    # Loop through each entity and create the task
    for sg_entity in sg_entities:
        for task_data in tasks_data:
            task_data["entity"] = sg_entity
            # Need to compare against step code as steps don't always have the
            # same code when applied through SG
            existing_task = sg.find(
                "Task",
                [
                    ["entity", "is", sg_entity],
                    ["content", 'is', task_data["content"]],
                    ["step.Step.code", 'is', task_data["step"]["code"]],
                ]
            )
            if existing_task:
                logger.info(
                    "Task '%s' already existed at '%s'.",
                    task_data["content"], sg_entity["code"]
                )
                continue
            sg.create("Task", task_data)
            logger.info(
                "Task '%s' created at '%s'", task_data["content"], sg_entity["code"]
            )


def populate_tasks(project_code):
    """Populate default tasks for all episodes, sequences, shots and assets in the
        given SG project.

    Args:
        project_code (str): A string representing the code name of the SG
            project to which the tasks will be added.
    """
    sg = credentials.get_shotgrid_session()

    # Dictionary of tasks -> pipeline step that we want created on all
    # entities of a project
    # NOTE: Currently the task names and the pipeline step names are
    # matching but that wouldn't necessarily be the case for all
    default_tasks = {
        "edit": "Edit",
        "generic": "Generic",
    }

    # Find the project with the given code
    project = sg.find_one("Project", [["sg_code", "is", project_code]], ["name"])
    if not project:
        logger.error("Project with 'sg_code' %s not found.", project_code)
        return

    # Try add tasks to all Episodes
    episodes = sg.find("Episode", [["project", "is", project]], ["id", "code"])
    if episodes:
        add_tasks_to_sg_entities(project, episodes, "Episode", default_tasks)

    # Try add tasks to all Sequences
    sequences = sg.find("Sequence", [["project", "is", project]], ["id", "code"])
    if sequences:
        add_tasks_to_sg_entities(project, sequences, "Sequence", default_tasks)

    # For child entities we ignore "generic" task
    default_tasks.pop("generic")

    # Try add tasks to all Shots
    shots = sg.find("Shot", [["project", "is", project]], ["id", "code"])
    shot_names = {shot["code"] for shot in shots}

    # Create generic shots used on start of the project to set up templates

    # If no generic edit shot exists on the project, create it
    if "_edit_shot" not in shot_names:
        logger.info("Generic '_edit_shot' doesn't exist in project yet, creating it.")
        _edit_shot = sg.create(
            "Shot",
            {
                "project": project,
                "code": "_edit_shot",
                "description": "Generic shot used for edit to conform"
            }
        )
        # Add 'edit' task to edit_shot
        add_tasks_to_sg_entities(project, [_edit_shot], "Shot", {"edit": "Edit"})
    else:  # Remove _edit_shot from list of shots so we don't add default tasks
        shots = [item for item in shots if item.get("code") != "_edit_shot"]

    # If no generic 2d shot exists on the project, create it
    if "_2d_shot" not in shot_names:
        logger.info("Generic '_2d_shot' doesn't exist in project yet, creating it.")
        _2d_shot = sg.create(
            "Shot",
            {
                "project": project,
                "code": "_2d_shot",
                "description": "Generic shot used for 2D to start doing lookdev without shots created."
            }
        )
        # Add 'comp' task to 2d_shot
        add_tasks_to_sg_entities(project, [_2d_shot], "Shot", {"comp": "Comp"})
    else:  # Remove _2d_shot from list of shots so we don't add default tasks
        shots = [item for item in shots if item.get("code") != "_2d_shot"]

    # If no generic 3d shot exists on the project, create it
    if "_3d_shot" not in shot_names:
        logger.info("Generic '_3d_shot' doesn't exist in project yet, creating it.")
        _3d_shot = sg.create(
            "Shot",
            {
                "project": project,
                "code": "_3d_shot",
                "description": "Generic shot used for 3D to start doing lookdev without shots created."
            }
        )
        # Add 'generic' task to 3d_shot
        add_tasks_to_sg_entities(project, [_3d_shot], "Shot", {"generic": "Generic"})
    else:
        shots = [item for item in shots if item.get("code") != "_3d_shot"]

    # Add default tasks to all remaining shots that aren't the generic ones
    if shots:
        add_tasks_to_sg_entities(project, shots, "Shot", default_tasks)

    # Try add tasks to all Assets
    assets = sg.find("Asset", [["project", "is", project]], ["id", "code"])
    if assets:
        add_tasks_to_sg_entities(project, assets, "Asset", default_tasks)
