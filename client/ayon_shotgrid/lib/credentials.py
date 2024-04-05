import os
import getpass
import shotgun_api3

import ayon_api
from ayon_core.lib import Logger

from ayon_shotgrid.version import __version__


logger = Logger.get_logger(__name__)


def create_sg_session(shotgrid_url, username, script_name, api_key, proxy):
    """Attempt to create a Shotgun Session

    Args:
        shotgrid_url (str): The Shotgun server URL.
        username (str): The Shotgrid username to use the Session as.
        script_name (str): The Shotgrid API script name.
        api_key (str): The Shotgrid API key.
        proxy (str): The proxy address to use to connect to SG server.

    Returns:
        session (shotgun_api3.Shotgun): A Shotgrid API Session.

    Raises:
        AuthenticationFault: If the authentication with Shotgrid fails.
    """

    session = shotgun_api3.Shotgun(
        base_url=shotgrid_url,
        script_name=script_name,
        http_proxy=proxy,
        api_key=api_key,
        sudo_as_login=username,
    )

    session.preferences_read()

    return session


### Starts Alkemy-X Override ###
def get_shotgrid_session():
    """Return a Shotgun API session object for the configured ShotGrid server.

    The function reads the ShotGrid server settings from the OpenPype
    configuration file and uses them to create a Shotgun API session object.

    Returns:
        A Shotgun API session object.
    """
    sg_settings = ayon_api.get_addon_settings("shotgrid", __version__)
    sg_url = sg_settings["shotgrid_server"]
    
    sg_script_name = sg_settings["shotgrid_api_name"]
    sg_api_key = sg_settings["shotgrid_api_key"]

    if not sg_script_name and not sg_api_key:
        logger.error(
            "No Shotgrid API credential found, please enter "
            "script name and script key in OpenPype settings"
        )

    user = getpass.getuser()
    proxy = os.environ.get("HTTPS_PROXY", "").replace("https://", "")

    try:
        return create_sg_session(
            sg_url,
            user,
            sg_script_name,
            sg_api_key,
            proxy,
        )
        
    except shotgun_api3.shotgun.AuthenticationFault:
        return create_sg_session(
            sg_url,
            f"{user}@alkemy-x.com",
            sg_script_name,
            sg_api_key,
            proxy,
        )

### Ends Alkemy-X Override ###
