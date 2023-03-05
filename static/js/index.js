function init() {
    refresh_builds();
    // initialise tooltips by selector
    $('body').tooltip({
        selector: '[data-bs-toggle="tooltip"]'
    });
}

function refresh_builds() {
    var xhr = new XMLHttpRequest();
    xhr.open('GET', "/builds/status.json");

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

function updateBuildsTable(status_json) {
    let output_container = document.getElementById('build_table_container');
    if (Object.keys(status_json).length == 0) {
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
    Object.keys(status_json).forEach((build_id) => {
        let build_info = status_json[build_id];
        let status_color = 'primary';
        if (build_info['status'] == 'Finished') {
            status_color = 'success';
        } else if (build_info['status'] == 'Pending') {
            status_color = 'warning';
        } else if (build_info['status'] == 'Failed' || build_info['status'] == 'Error') {
            status_color = 'danger';
        }

        table_body_html +=  `<tr>
                                <td class="align-middle"><span class="badge text-bg-${status_color}">${build_info['status']}</span></td>
                                <td class="align-middle">${build_info['age']}</td>
                                <td class="align-middle"><a href="https://github.com/ArduPilot/ardupilot/commit/${build_info['git_hash_short']}">${build_info['git_hash_short']}</a></td>
                                <td class="align-middle">${build_info['board']}</td>
                                <td class="align-middle">${build_info['vehicle']}</td>
                                <td class="align-middle" id="${row_num}_features">
                                        ${build_info['features'].substring(0, 100)}... 
                                        <span id="${row_num}_features_all" style="display:none;">${build_info['features']}</span>
                                    <a href="javascript: showFeatures(${row_num});">show more</a>
                                </td>
                                <td class="align-middle">
                                    <div class="progress border" role="progressbar" aria-valuenow="0" aria-valuemin="0" aria-valuemax="100">
                                        <div class="progress-bar bg-${status_color}" style="width: ${build_info['progress']}%">${build_info['progress']}%</div>
                                    </div>
                                </td>
                                <td class="align-middle">
                                    <button class="btn btn-md btn-outline-primary m-1 tooltip-button" data-bs-toggle="tooltip" data-bs-animation="false" data-bs-title="View log" onclick="launchLogModal('${build_id}');">
                                        <i class="bi bi-file-text"></i>
                                    </button>
                                    <button class="btn btn-md btn-outline-primary m-1 tooltip-button" data-bs-toggle="tooltip" data-bs-animation="false" data-bs-title="Open build directory" onclick="window.location.href = './builds/${build_id}';">
                                        <i class="bi bi-folder2-open"></i>
                                    </button>
                                </td>
                            </tr>`;
        row_num += 1;
    });

    let table_html =    `<table class="table table-hover table-light shadow">
                            <thead class="table-dark">
                                <th scope="col" style="width: 5%">Status</th>
                                <th scope="col" style="width: 5%">Age (hr:min)</th>
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
        xhr.open('GET', `/builds/${build_id}/build.log`);

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
