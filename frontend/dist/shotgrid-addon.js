let addonName = null
let addonVersion = null
let accessToken = null
let projectName = null
let addonScope = null
let addonSettings = null
let sgAccessToken = null
let ayonAPI = null
let ayonProjects = []; // Declare ayonProjects globally


function slugify(inputString) {
  return inputString
      .trim()                         // Remove leading and trailing whitespaces
      .replace(/^\W+/, '')            // Remove non-alphanumeric characters from the beginning
      .replace(/\s+/g, '')            // Remove all whitespaces
      .replace(/[-/]/g, '_');         // Replace all hyphens and '/' with '_'
}


const init = () => {
 /* When the addon page is loaded, it receive a message with context and
  additional data (accessToken, addon version...). When the context is changed,
  a message is re-broadcasted, so the page can react to changes in selection etc.  */

  window.onmessage = async (e) => {
    const context = e.data.context
    addonName = e.data.addonName
    addonVersion = e.data.addonVersion
    accessToken = e.data.accessToken
    addonScope = e.data.scope

    ayonAPI = axios.create({
      baseUrl: `${e.origin}/api/`,
      headers: {"Authorization": `Bearer ${accessToken}`}
    })

    addonSettings = await ayonAPI
      .get(`/api/addons/${addonName}/${addonVersion}/settings`)
      .then((result) => result.data);

    addonSecrets = await ayonAPI
      .get(`/api/secrets/${addonSettings.service_settings.script_key}`)
      .then((result) => result.data);

    addonSettings.shotgrid_api_key = addonSecrets.value

    ayonProjects = await getAyonProjects();

    await populateTable();
  } // end of window.onmessage
} // end of init


const populateTable = async () => {
  /* Get all the projects from AYON and Shotgrid, then populate the table with their info
  and a button to Synchronize if they pass the requirements */
  sgProjects = await getShotgridProjects();

  // Wait until ayonProjects is populated
  if (ayonProjects.length === 0) {
    console.log("Waiting for ayonProjects to be populated...");
    await new Promise((resolve) => setTimeout(resolve, 1000)); // Wait for 1 second
    if (ayonProjects.length === 0) {
      alert("AYON Projects are not yet loaded. Please try again later.");
      return;
    }
  }

  const allProjects = [...ayonProjects]; // Clone to avoid modifying the global array

  sgProjects.forEach((sg_project) => {
    let already_exists = false
    allProjects.forEach((project) => {
      if (sg_project.name == project.ayonId) {
          already_exists = true
          project.shotgridId = sg_project.shotgridId
      }
    })
    if (!already_exists) {
      sg_project.ayonId = null
      allProjects.push(sg_project)
    }
  })

  allProjects.sort((a, b) => a.name.toLowerCase().localeCompare(b.name.toLowerCase()));

  const ProjectsTable = document.getElementById("sg-addon-projects-table")
  const ProjectsTableHeader = document.getElementById("sg-addon-projects-table-header")
  const ProjectsTableBody = document.getElementById("sg-addon-projects-table")
  ProjectsTableBody.innerHTML = '';
  ProjectsTableBody.appendChild(ProjectsTableHeader);

  allProjects.forEach((project) => {
    var tableRow = document.createElement('tr')

    var nameCell = document.createElement('td')
    nameCell.innerText = project.name
    tableRow.appendChild(nameCell)

    var codeCell = document.createElement('td')
    codeCell.innerText = project.code
    tableRow.appendChild(codeCell)

    var ayonCell = document.createElement('td')
    ayonCell.innerText = project.ayonId ? 'Yes' : 'No';
    tableRow.appendChild(ayonCell)

    var sgCell = document.createElement('td')
    sgCell.innerText = project.shotgridId ? 'Yes' : 'No';
    tableRow.appendChild(sgCell)

    var syncCell = document.createElement('td')

    var sgSyncButton = document.createElement('button')
    sgSyncButton.innerText = `Shotgrid -> AYON`
    sgSyncButton.disabled = true;

    if (project.shotgridId && project.code) {
      if (/^[a-zA-Z][a-zA-Z0-9]+/.test(project.code)) {
        // Only Enable button if its a valid name and code
        sgSyncButton.disabled = false;
        sgSyncButton.setAttribute("data-ayon-name", project.name);
        sgSyncButton.setAttribute("data-ayon-code", project.code);

        sgSyncButton.addEventListener('click', function () {
          syncShotgridToAyon(this.attributes["data-ayon-name"].value, this.attributes["data-ayon-code"].value)
        }, false);
      }
    }
    syncCell.appendChild(sgSyncButton)

    var ayonSyncButton = document.createElement('button')
    ayonSyncButton.innerText = `AYON -> Shotgrid`
    ayonSyncButton.disabled = project.ayonId ? false : true;
    ayonSyncButton.setAttribute("data-ayon-name", project.name);
    ayonSyncButton.setAttribute("data-ayon-code", project.code);
    ayonSyncButton.addEventListener('click', function () {
          syncAyonToShotgrid(this.attributes["data-ayon-name"].value, this.attributes["data-ayon-code"].value)
        }, false);
    syncCell.appendChild(ayonSyncButton)

    tableRow.appendChild(syncCell)

    ProjectsTableBody.appendChild(tableRow)
  });
}


const syncUsers = async () => {
  /* Get all the Users from AYON and Shotgrid, then populate the table with their info
  and a button to Synchronize if they pass the requirements */

  // Wait until ayonProjects is populated
  if (ayonProjects.length === 0) {
    console.log("Waiting for ayonProjects to be populated...");
    await new Promise((resolve) => setTimeout(resolve, 1000)); // Wait for 1 second
    if (ayonProjects.length === 0) {
      alert("AYON Projects are not yet loaded. Please try again later.");
      return;
    }
  }

  console.log("Syncing Shotgrid users to Ayon");
  const ayonUsers = await getAyonUsers();
  const sgUsers = await getShotgridUsers();

  const ayonUserNames = new Set(ayonUsers.map(user => user.name));
  const promises = [];

  sgUsers.forEach((sg_user) => {
    const already_exists = ayonUserNames.has(sg_user.login);

    if (!already_exists) {
      promises.push(
        createNewUserInAyon(sg_user.login, sg_user.email, sg_user.name).catch(error => {
          console.error(`Failed to create user ${sg_user.login}:`, error);
        })
      );
    }
  
    console.log("Trying to sync user " + sg_user.login);
    const accessGroups = {};

    ayonProjects.forEach((ayon_project) => {
      sg_user.projectNames.forEach((project_name) => {
        if (ayon_project.name === project_name) {
          accessGroups[project_name] = [sg_user.permissionGroup];
        }
      });
    });

    // Collect promises for assigning users to projects
    promises.push(
      assignUserToProjects(sg_user.login, accessGroups, sg_user.permissionGroup).catch(error => {
        console.error(`Failed to assign user ${sg_user.login} to projects:`, error);
      })
    );

  });

  // Wait for all promises to resolve
  await Promise.all(promises);
};



const getShotgridUsers = async () => {
  /* Query Shotgrid for all active users. */
  const sgBaseUrl = `${addonSettings.shotgrid_server.replace(/\/+$/, '')}/api/v1`
  sgAuthToken = await axios
    .post(`${sgBaseUrl}/auth/access_token`, {
        client_id: `${addonSettings.service_settings.script_name}`,
        client_secret: addonSettings.shotgrid_api_key,
        grant_type: "client_credentials",
    }, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
      }
    })
    .then((result) => result.data.access_token)
    .catch((error) => {
      console.log("Unable to Acquire the Shotgrid Authorization Token!")
      console.log(error)
    });

    sgUsers = await axios
      .get(`${sgBaseUrl}/entity/human_users?filter[sg_status_list]=act&fields=login,name,email,projects,permission_rule_set`, {
        headers: {
            'Authorization': `Bearer ${sgAuthToken}`,
            'Accept': 'application/json'
        }
      })
      .then((result) => result.data.data)
      .catch((error) => {
        console.log("Unable to Fetch Shotgrid Users!")
        console.log(error)
      });
    
    /* Do some extra clean up on the users returned. */
    var sgUsersConformed = []
    users_to_ignore = ["dummy", "root", "support"]
    if (sgUsers) {
      sgUsers.forEach((sg_user) => {
        if (
          !users_to_ignore.some(item => sg_user.attributes.email.includes(item))
        ) {
          /* Need to slugify the Shotgrid project name as AYON doesn't support the same
          characters and so if it's been synced in the past it was slugified already*/
          var projectNames = sg_user.relationships.projects.data.map(
            project => slugify(project["name"])
          );
          sgUsersConformed.push({
            "login": sg_user.attributes.login,
            "name": sg_user.attributes.name,
            "email": sg_user.attributes.email,
            "projectNames": projectNames,
            "permissionGroup": sg_user.relationships.permission_rule_set.data.name.toLowerCase(), 
          })
        }
      });
    }
    return sgUsersConformed;
}


const getAyonUsers = async () => {
  /* Query AYON for all existing users. */
  const response = await ayonAPI.post('graphql', {
    query: `
      query ActiveUsers {
        users {
          edges {
            node {
              attrib {
                email
                fullName
              }
              active
              name
              accessGroups
            }
          }
        }
      }
      `
  });
  const ayonUsers = response.data.data.users.edges;

  let ayonUsersConformed = []
  if (ayonUsers) {
    ayonUsers.forEach((user) => {
      ayonUsersConformed.push({
        "name": user.node.name,
        "email": user.node.attrib.email,
        "fullName": user.node.attrib.fullName,
        "accessGroups": user.node.accessGroups,
      })
    })
  }
  
  return ayonUsersConformed
}


const createNewUserInAyon = async (login, email, name) => {
  /* Create a new AYON user. */
  call_result_paragraph = document.getElementById("call-result");

  response = await ayonAPI
    .put("/api/users/" + login, {
      "active": true,
      "attrib": {
        "fullName": name,
        "email": email,
      },
      "password": login,
    })
    .then((result) => result)
    .catch((error) => {
      console.log("Unable to create user in AYON!")
      console.log(error)
      call_result_paragraph.innerHTML = `Unable to create user in AYON! ${error}`
    });
}


const assignUserToProjects = async (login, accessGroups, permissionGroup) => {
  /* Set AYON project access permissions to user */
  call_result_paragraph = document.getElementById("call-result");
  
  /* For admin, executive and management Shotgrid roles we simply set the access group on the user
  as those have access to all projects by default */
  if (["admin", "executive", "management"].includes(permissionGroup)) {
    var access_data = {
      isAdmin: permissionGroup === "admin",
      isManager: ["executive", "management"].includes(permissionGroup),
      isDeveloper: permissionGroup === "admin",
    };
    response = await ayonAPI
      .patch("/api/users/" + login, {
        "data": access_data
      })
      .then((result) => result)
      .catch((error) => {
        console.log("Unable to assign access groups to user!")
        console.log(error)
        call_result_paragraph.innerHTML = `Unable to assign role to user!! ${error}`
      });
  }
  /* Otherwise we set the access group for each project the user is assigned to */
  else {
    response = await ayonAPI
      .patch("/api/users/" + login + "/accessGroups", {
        accessGroups
      })
      .then((result) => result)
      .catch((error) => {
        console.log("Unable to assign access groups to user!")
        console.log(error)
        call_result_paragraph.innerHTML = `Unable to assign access groups to user!! ${error}`
      });
  }
}


const getShotgridProjects = async () => {
  /* Query Shotgrid for all existing projects. */
  const sgBaseUrl = `${addonSettings.shotgrid_server.replace(/\/+$/, '')}/api/v1`
  sgAuthToken = await axios
    .post(`${sgBaseUrl}/auth/access_token`, {
      client_id: `${addonSettings.service_settings.script_name}`,
      client_secret: addonSettings.shotgrid_api_key,
      grant_type: "client_credentials",
    }, {
      headers: {
        'Content-Type': 'application/x-www-form-urlencoded',
        'Accept': 'application/json'
      }
    })
    .then((result) => result.data.access_token)
    .catch((error) => {
      console.log("Unable to Acquire the Shotgrid Authorization Token!")
      console.log(error)
    });

  sgProjects = await axios
    .get(`${sgBaseUrl}/entity/projects?fields=*`, {
      headers: {
        'Authorization': `Bearer ${sgAuthToken}`,
        'Accept': 'application/json'
      }
    })
    .then((result) => result.data.data)
    .catch((error) => {
      console.log("Unable to Fetch Shotgrid Projects!")
      console.log(error)
    });

  var sgProjectsConformed = []

  if (sgProjects) {    
    sgProjects.forEach((project) => {
      /* Only add projects that have a code name as those are the requirements to sync to Ayon. */
      if (
        project.attributes[`${addonSettings.shotgrid_project_code_field}`]
      ) {
        sgProjectsConformed.push({
          "name": slugify(project.attributes.name),
          "code": project.attributes[`${addonSettings.shotgrid_project_code_field}`],
          "shotgridId": project.id,
          "ayonId": project.attributes.sg_ayon_id,
        })
      }
    });
  }
  return sgProjectsConformed;
}


const getAyonProjects = async () => {
  /* Query AYON for all existing projects. */
  const response = await ayonAPI.post('graphql', {
    query: `
      query ActiveProjects {
        projects {
          edges {
            node {
              attrib {
                shotgridId
              }
              active
              code
              name
            }
          }
        }
      }
    `,
  });
  const ayonProjects = response.data.data.projects.edges;

  let ayonProjectsConformed = []
  if (ayonProjects) {
    ayonProjects.forEach((project) => {
      ayonProjectsConformed.push({
        "name": project.node.name,
        "code": project.node.code,
        "shotgridId": project.node.attrib.shotgridId,
        "ayonId": project.node.name,
      })
    })
  }
    return ayonProjectsConformed
}


const syncShotgridToAyon = async (projectName, projectCode) => {
  /* Spawn an AYON Event of topic "shotgrid.event.project.sync" to synchronize a project
  from Shotgrid into AYON. */
  call_result_paragraph = document.getElementById("call-result");

  dispatch_event = await ayonAPI
    .post("/api/events", {
      "topic": "shotgrid.event.project.sync",
      "project": projectName,
      "description": `Synchronize Project '${projectName}' from Shotgrid.`,
      "payload": {
        "action": "sync-from-shotgrid",
        "project_name": projectName,
        "project_code": projectCode,
        "project_code_field": addonSettings.shotgrid_project_code_field,
      },
      "finished": true,
      "store": true
    })
    .then((result) => result)
    .catch((error) => {
      console.log("Unable to submit event to AYON!")
      console.log(error)
      call_result_paragraph.innerHTML = `Unable to submit event to AYON! ${error}`
    });

  if (dispatch_event) {
    call_result_paragraph.innerHTML = `Successfully Spawned Event! ${dispatch_event.data.id} Make sure there's a processor <a target="_parent" href="/services">Service running</a>`
  }
}


const syncAyonToShotgrid = async (projectName, projectCode) => {
  /* Spawn an AYON Event of topic "shotgrid.event.project.sync"
  to synchronize a project from AYON into Shotgrid. */
  call_result_paragraph = document.getElementById("call-result");

  dispatch_event = await ayonAPI
    .post("/api/events", {
      "topic": "shotgrid.event.project.sync",
      "project": projectName,
      "description": `Synchronize Project ${projectName} from AYON.`,
      "payload": {
        "action": "sync-from-ayon",
        "project_name": projectName,
        "project_code": projectCode,
        "project_code_field": addonSettings.shotgrid_project_code_field,
      },
      "finished": true,
      "store": true
    })
    .then((result) => result)
    .catch((error) => {
      console.log("Unable to submit event to AYON!")
      console.log(error)
      call_result_paragraph.innerHTML = `Unable to submit event to AYON! ${error}`
    });

  if (dispatch_event) {
    call_result_paragraph.innerHTML = `Successfully Spawned Event! ${dispatch_event.data.id} Make sure there's a processor <a target="_parent" href="/services">Service running</a>`
  }
}

document.addEventListener('DOMContentLoaded', () => {
 init()
})
