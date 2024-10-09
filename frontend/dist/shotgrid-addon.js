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
      baseUrl: `${e.origin}`,
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
  ayonProjects = await axios({
    url: '/graphql',
    headers: {"Authorization": `Bearer ${accessToken}`},
    method: 'post',
    data: {
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
      `
    }
  }).then((result) => result.data.data.projects.edges);

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
