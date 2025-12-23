function init() {
    refresh_builds();
    // initialise tooltips by selector
    $('body').tooltip({
        selector: '[data-bs-toggle="tooltip"]'
    });
}

function refresh_builds() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', "/builds");

    // disable cache, thanks to: https://stackoverflow.com/questions/22356025/force-cache-control-no-cache-in-chrome-via-xmlhttprequest-on-f5-reload
    xhr.setRequestHeader("Cache-Control", "no-cache, no-store, max-age=0");
    xhr.setRequestHeader("Expires", "Tue, 01 Jan 1980 1:00:00 GMT");
    xhr.setRequestHeader("Pragma", "no-cache");

    xhr.onload = function () {
        if (xhr.status === 200) {
            updateBuildsTable(JSON.parse(xhr.response));
        }
        setTimeout(refresh_builds, 5000);
    }
    xhr.send();
}

function showFeatures(row_num) {
    document.getElementById("featureModalBody").innerHTML = document.getElementById(`${row_num}_features_all`).innerHTML;
    var feature_modal = bootstrap.Modal.getOrCreateInstance(document.getElementById('featureModal'));
    feature_modal.show();
    return;
}

function timeAgo(timestampStr) {
    const timestamp = parseFloat(timestampStr);
    const now = Date.now() / 1000;
    const diff = now - timestamp;

    if (diff < 0) return "In the future";

    const hours = Math.floor(diff / 3600);
    const minutes = Math.floor((diff % 3600) / 60);

    return `${hours}h ${minutes}m`;
}

function updateBuildsTable(builds) {
    let output_container = document.getElementById('build_table_container');
    if (builds.length == 0) {
        output_container.innerHTML = `<div class="alert alert-success" role="alert" id="welcome_alert">
                                        <h4 class="alert-heading">Welcome!</h4>
                                        <p>No builds were queued to run on the server recently. To queue one, please click <a href="./add_build" class="alert-link">add a build</a>.</p>
                                      </div>`;
        return;
    }

    // hide any tooltips which are currently open
    // this is needed as they might get stuck 
    // if the element to which they belong goes out of the dom tree
    $('.tooltip-button').tooltip("hide");

    let table_body_html = '';
    let row_num = 0;
    builds.forEach((build_info) => {
        let status_color = 'primary';
        if (build_info['progress']['state'] == 'SUCCESS') {
            status_color = 'success';
        } else if (build_info['progress']['state'] == 'PENDING') {
            status_color = 'warning';
        } else if (build_info['progress']['state'] == 'FAILURE' || build_info['progress']['state'] == 'ERROR') {
            status_color = 'danger';
        }

        const features_string = build_info['selected_features'].join(', ')
        const build_age = timeAgo(build_info['time_created'])

        table_body_html +=  `<tr>
                                <td class="align-middle"><span class="badge text-bg-${status_color}">${build_info['progress']['state']}</span></td>
                                <td class="align-middle">${build_age}</td>
                                <td class="align-middle"><a href="https://github.com/ArduPilot/ardupilot/commit/${build_info['git_hash']}">${build_info['git_hash'].substring(0,8)}</a></td>
                                <td class="align-middle">${build_info['board']}</td>
                                <td class="align-middle">${build_info['vehicle_id']}</td>
                                <td class="align-middle" id="${row_num}_features">
                                        ${features_string.substring(0, 100)}... 
                                        <span id="${row_num}_features_all" style="display:none;">${features_string}</span>
                                    <a href="javascript: showFeatures(${row_num});">show more</a>
                                </td>
                                <td class="align-middle">
                                    <div class="progress border" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                                        <div class="progress-bar bg-${status_color}" style="width: ${build_info['progress']['percent']}%">${build_info['progress']['percent']}%</div>
                                    </div>
                                </td>
                                <td class="align-middle">
                                    <button class="btn btn-md btn-outline-primary m-1 tooltip-button" data-bs-toggle="tooltip" data-bs-animation="false" data-bs-title="View log" onclick="launchLogModal('${build_info['build_id']}');">
                                        <i class="bi bi-file-text"></i>
                                    </button>
                                    <button class="btn btn-md btn-outline-primary m-1 tooltip-button" data-bs-toggle="tooltip" data-bs-animation="false" data-bs-title="Download build artifacts" id="${build_info['build_id']}-download-btn" onclick="window.location.href='/builds/${build_info['build_id']}/artifacts/${build_info['build_id']}.tar.gz';">
                                        <i class="bi bi-download"></i>
                                    </button>
                                </td>
                            </tr>`;
        row_num += 1;
    });

    let table_html =    `<table class="table table-hover table-light shadow">
                            <thead class="table-dark">
                                <th scope="col" style="width: 5%">Status</th>
                                <th scope="col" style="width: 5%">Age</th>
                                <th scope="col" style="width: 5%">Git Hash</th>
                                <th scope="col" style="width: 5%">Board</th>
                                <th scope="col" style="width: 5%">Vehicle</th>
                                <th scope="col">Features</th>
                                <th scope="col" style="width: 15%">Progress</th>
                                <th scope="col" style="width: 15%">Actions</th>
                            </thead>
                            <tbody>${table_body_html}</tbody>
                        </table>`;
    output_container.innerHTML = table_html;
}

const LogFetch = (() => {
    var stopFetch = true;
    var build_id = null;
    var scheduled_fetches = 0;

    function startLogFetch(new_build_id) {
        build_id = new_build_id;
        stopFetch = false;
        if (scheduled_fetches <= 0) {
            scheduled_fetches = 1;
            fetchLogFile();
        }
    }

    function stopLogFetch() {
        stopFetch = true;
    }

    function getBuildId() {
        return build_id;
    }

    function fetchLogFile() {
        if (stopFetch || !build_id) {
            scheduled_fetches -= 1;
            return;
        }

        var xhr = new XMLHttpRequest();
        xhr.open('GET', `/builds/${build_id}/artifacts/build.log`);

        // disable cache, thanks to: https://stackoverflow.com/questions/22356025/force-cache-control-no-cache-in-chrome-via-xmlhttprequest-on-f5-reload
        xhr.setRequestHeader("Cache-Control", "no-cache, no-store, max-age=0");
        xhr.setRequestHeader("Expires", "Tue, 01 Jan 1980 1:00:00 GMT");
        xhr.setRequestHeader("Pragma", "no-cache");

        xhr.onload = () => {
            if (xhr.status == 200) {
                let logTextArea = document.getElementById('logTextArea');
                let autoScrollSwitch = document.getElementById('autoScrollSwitch');
                logTextArea.textContent = xhr.responseText;
                if (autoScrollSwitch.checked) {
                    logTextArea.scrollTop = logTextArea.scrollHeight;
                }

                if (xhr.responseText.includes('BUILD_FINISHED')) {
                    stopFetch = true;
                }
            }
            if (!stopFetch) {
                setTimeout(fetchLogFile, 3000);
            } else {
                scheduled_fetches -= 1;
            }
        }
        xhr.send();
    }

    return {startLogFetch, stopLogFetch, getBuildId};
})();

function launchLogModal(build_id) {
    document.getElementById('logTextArea').textContent = `Fetching build log...\nBuild ID: ${build_id}`;
    LogFetch.startLogFetch(build_id);
    let logModalElement = document.getElementById('logModal');
    logModalElement.addEventListener('hide.bs.modal', () => {
        LogFetch.stopLogFetch();
    });
    let logModal = bootstrap.Modal.getOrCreateInstance(logModalElement);
    logModal.show();
}

// Trigger auto-download if state changes from "RUNNING" to "SUCCESS"
let previousState = null;
let autoDownloadIntervalId = null;

async function tryAutoDownload(buildId) {
    if (!autoDownloadIntervalId) {
        return;
    }

    try {
        const apiUrl = `/builds/${buildId}`
        const response = await fetch(apiUrl);
        const data = await response.json();

        const currentState = data.progress?.state;

        if (previousState === "RUNNING" && currentState === "SUCCESS") {
            console.log("Build completed successfully. Starting download...");
            document.getElementById(`${buildId}-download-btn`).click();
        }

        // Stop running if the build is in a terminal state
        if (["FAILURE", "SUCCESS", "ERROR"].includes(currentState)) {
            clearInterval(autoDownloadIntervalId);
            return;
        }

        previousState = currentState;
    } catch (err) {
        console.error("Failed to fetch build status:", err);
    }
};
