import pyblish.api


class CollectShotgridShot(pyblish.api.InstancePlugin):
    """Collect proper Shotgrid entity according to the current asset name"""

    order = pyblish.api.CollectorOrder + 0.4999
    label = "Collect Shotgrid Shot"
    hosts = ["hiero"]
    families = ["plate", "take", "reference"]

    def process(self, instance):
        context = instance.context

        self.log.info("Looking for shot associated with clip name")
        
        sg_session = context.data.get("shotgridSession")
        anatomy_data = instance.data.get("anatomyData", {})
        sg_shot = _get_shotgrid_shot(
            sg_session, anatomy_data["project"]["name"], anatomy_data["asset"]
        )
        if sg_shot:
            instance.data["shotgridEntity"] = sg_shot
            self.log.info(
                "Overriding entity with corresponding shot for clip: {}".format(sg_shot)
            )
        else:
            raise Exception(
                "No Shotgrid shot found under clip name: {}".format(
                    anatomy_data["asset"]
                )
            )


def _get_shotgrid_shot(sg_session, project_name, shot_name):
    # OP project name/code isn't always sg_code. This approach gives a sure fire way
    # to match to a SG project
    filters = [
        [
            "project.Project.name",
            "is",
            [project_name],
        ],
        ["code", "is", shot_name],
    ]
    sg_shot = sg_session.find_one("Shot", filters, ["code"])

    return sg_shot
