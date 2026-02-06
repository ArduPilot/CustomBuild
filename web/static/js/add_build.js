const Features = (() => {
    let features = [];  // Flat array of feature objects from API
    let features_by_id = {};  // Map feature IDs to feature objects
    let categories_grouped = {};  // Features grouped by category name
    let selected_options = 0;

    function resetDictionaries() {
        // clear old dictionaries
        features_by_id = {};
        categories_grouped = {};

        // Build lookup maps from flat feature array
        features.forEach((feature) => {
            features_by_id[feature.id] = feature;
            
            // Group by category
            const cat_name = feature.category.name;
            if (!categories_grouped[cat_name]) {
                categories_grouped[cat_name] = {
                    name: cat_name,
                    description: feature.category.description,
                    features: []
                };
            }
            categories_grouped[cat_name].features.push(feature);
        });
    }

    function updateRequiredFor() {
        features.forEach((feature) => {
            if (feature.dependencies && feature.dependencies.length > 0) {
                feature.dependencies.forEach((dependency_id) => {
                    let dep = getOptionById(dependency_id);
                    if (dep && dep.requiredFor == undefined) {
                        dep.requiredFor = [];
                    }
                    if (dep) {
                        dep.requiredFor.push(feature.id);
                    }
                });
            }
        });
    }

    function reset(new_features) {
        features = new_features;
        selected_options = 0;
        resetDictionaries();
        updateRequiredFor();
    }

    function getOptionById(id) {
        return features_by_id[id];
    }

    function getCategoryByName(category_name) {
        return categories_grouped[category_name];
    }

    function getAllCategories() {
        return Object.values(categories_grouped);
    }

    function getCategoryIdByName(category_name) {
        return 'category_'+category_name.split(" ").join("_");
    }

    function featureIsDisabledByDefault(feature_id) {
        let feature = getOptionById(feature_id);
        return feature && !feature.default.enabled;
    }

    function featureisEnabledByDefault(feature_id) {
        return !featureIsDisabledByDefault(feature_id);
    }

    function enableDependenciesForFeature(feature_id) {
        let feature = getOptionById(feature_id);

        if (!feature || !feature.dependencies || feature.dependencies.length === 0) {
            return;
        }

        feature.dependencies.forEach((dependency_id) => {
            const check = true;
            checkUncheckOptionById(dependency_id, check);
        });
    }

    function handleOptionStateChange(feature_id, triggered_by_ui, updateDependencies = true) {
        // feature_id is the feature ID from the API
        let element = document.getElementById(feature_id);
        if (!element) return;
        
        let feature = getOptionById(feature_id);
        if (!feature) return;
        
        if (element.checked) {
            selected_options += 1;
            if (updateDependencies) {
                enableDependenciesForFeature(feature.id);
            }
        } else {
            selected_options -= 1;
            if (updateDependencies) {
                if (triggered_by_ui) {
                    askToDisableDependentsForFeature(feature.id);
                } else {
                    disabledDependentsForFeature(feature.id);
                }
            }
        }

        updateCategoryCheckboxState(feature.category.name);
        updateGlobalCheckboxState();
    }

    function askToDisableDependentsForFeature(feature_id) {
        let enabled_dependent_features = getEnabledDependentFeaturesFor(feature_id);
        
        if (enabled_dependent_features.length <= 0) {
            return;
        }

        let feature = getOptionById(feature_id);
        let feature_display_name = feature ? feature.name : feature_id;
        
        // Get display names for dependent features
        let dependent_names = enabled_dependent_features.map(dep_id => {
            let dep_feature = getOptionById(dep_id);
            return dep_feature ? dep_feature.name : dep_id;
        });

        document.getElementById('modalBody').innerHTML = "The feature(s) <strong>"+dependent_names.join(", ")+"</strong> is/are dependant on <strong>"+feature_display_name+"</strong>" +
                                                         " and hence will be disabled too.<br><strong>Do you want to continue?</strong>";
        document.getElementById('modalDisableButton').onclick = () => { disabledDependentsForFeature(feature_id); };
        document.getElementById('modalCancelButton').onclick = document.getElementById('modalCloseButton').onclick = () => {
            const check = true;
            if (feature) {
                checkUncheckOptionById(feature.id, check);
            }
        };
        var confirmationModal = bootstrap.Modal.getOrCreateInstance(document.getElementById('dependencyCheckModal'));
        confirmationModal.show();
    }

    function disabledDependentsForFeature(feature_id) {
        let feature = getOptionById(feature_id);

        if (!feature || feature.requiredFor == undefined) {
            return;
        }

        let dependents = feature.requiredFor;
        dependents.forEach((dependent_id) => {
            const check = false;
            checkUncheckOptionById(dependent_id, check);
        });
    }

    function updateCategoryCheckboxState(category_name) {
        let category = getCategoryByName(category_name);

        if (category == undefined) {
            console.log("Could not find category by given name");
            return;
        }

        let checked_options_count = 0;

        category.features.forEach((feature) => {
            // Use ID to find the element
            let element = document.getElementById(feature.id);

            if (element && element.checked) {
                checked_options_count += 1;
            }
        });

        let category_checkbox_element = document.getElementById(getCategoryIdByName(category_name));
        if (category_checkbox_element == undefined) {
            console.log("Could not find element for given category");
            return;
        }   

        let indeterminate_state = false;
        switch(checked_options_count) {
            case 0:
                category_checkbox_element.checked = false;
                break;
            case category.features.length:
                category_checkbox_element.checked = true;
                break;
            default:
                indeterminate_state = true;
                break;
        }

        category_checkbox_element.indeterminate = indeterminate_state;
    }

    function updateGlobalCheckboxState() {
        const total_options = Object.keys(features_by_id).length;
        let global_checkbox = document.getElementById("check-uncheck-all");

        let indeterminate_state = false;
        switch (selected_options) {
            case 0:
                global_checkbox.checked = false;
                break
            case total_options:
                global_checkbox.checked = true;
                break;
            default:
                indeterminate_state = true;
                break;
        }

        global_checkbox.indeterminate = indeterminate_state;
    }

    function getEnabledDependentFeaturesHelper(feature_id, visited, dependent_features) {
        if (visited[feature_id] != undefined) {
            return;
        }
        
        let feature = getOptionById(feature_id);
        if (!feature) return;
        
        // Use ID to check the checkbox
        let element = document.getElementById(feature.id);
        if (!element || element.checked == false) {
            return;
        }

        visited[feature_id] = true;
        dependent_features.push(feature_id);

        if (feature.requiredFor == null) {
            return;
        }

        feature.requiredFor.forEach((dependent_feature_id) => {
            getEnabledDependentFeaturesHelper(dependent_feature_id, visited, dependent_features);
        });
    }

    function getEnabledDependentFeaturesFor(feature_id) {
        let dependent_features = [];
        let visited = {};

        let feature = getOptionById(feature_id);
        if (feature && feature.requiredFor) {
            feature.requiredFor.forEach((dependent_feature_id) => {
                getEnabledDependentFeaturesHelper(dependent_feature_id, visited, dependent_features);
            });
        }

        return dependent_features;
    }

    function applyDefaults() {
        features.forEach(feature => {
            const check = featureisEnabledByDefault(feature.id);
            checkUncheckOptionById(feature.id, check);
        });
    }

    function checkUncheckOptionById(id, check, updateDependencies = true) {
        let feature = getOptionById(id);
        if (!feature) return;
        
        // Use ID to find the element
        let element = document.getElementById(feature.id);
        if (element == undefined || element.checked == check) {
            return;
        }
        element.checked = check;
        const triggered_by_ui = false;
        handleOptionStateChange(feature.id, triggered_by_ui, updateDependencies);
    }

    function checkUncheckAll(check) {
        getAllCategories().forEach(category => { 
            checkUncheckCategory(category.name, check);
        });
    }

    function checkUncheckCategory(category_name, check) {
        getCategoryByName(category_name).features.forEach(feature => {
            checkUncheckOptionById(feature.id, check);
        });
    }

    return {reset, handleOptionStateChange, getCategoryIdByName, applyDefaults, checkUncheckAll, checkUncheckCategory, getOptionById, checkUncheckOptionById};
})();

var init_categories_expanded = false;

var pending_update_calls = 0;   // to keep track of unresolved Promises
var currentBoards = [];
var currentFeatures = [];

var rebuildConfig = {
    vehicleId: null,
    versionId: null,
    boardId: null,
    selectedFeatures: [],
    isRebuildMode: false
};

async function init() {
    if (typeof rebuildFromBuildId !== 'undefined') {
        await initRebuild(rebuildFromBuildId);
    }
    
    fetchVehicles();
}

async function initRebuild(buildId) {
    try {
        const buildResponse = await fetch(`/api/v1/builds/${buildId}`);
        if (!buildResponse.ok) {
            throw new Error('Failed to fetch build details');
        }
        const buildData = await buildResponse.json();
        
        if (!buildData.vehicle || !buildData.vehicle.id) {
            throw new Error('Vehicle information is missing from the build');
        }
        if (!buildData.version || !buildData.version.id) {
            throw new Error('Version information is missing from the build');
        }
        if (!buildData.board || !buildData.board.id) {
            throw new Error('Board information is missing from the build');
        }
        
        rebuildConfig.vehicleId = buildData.vehicle.id;
        rebuildConfig.versionId = buildData.version.id;
        rebuildConfig.boardId = buildData.board.id;
        rebuildConfig.selectedFeatures = buildData.selected_features || [];
        rebuildConfig.isRebuildMode = true;
        
    } catch (error) {
        console.error('Error loading rebuild configuration:', error);
        alert('Failed to load build configuration: ' + error.message + '\n\nRedirecting to new build page...');
        window.location.href = '/add_build';
        throw error;
    }
}

function applyRebuildFeatures(featuresList) {
    Features.checkUncheckAll(false);
    
    if (featuresList && featuresList.length > 0) {
        featuresList.forEach(featureId => {
            Features.checkUncheckOptionById(featureId, true, false);
        });
    }
}

function clearRebuildConfig() {
    rebuildConfig.vehicleId = null;
    rebuildConfig.versionId = null;
    rebuildConfig.boardId = null;
    rebuildConfig.selectedFeatures = [];
    rebuildConfig.isRebuildMode = false;
}

// enables or disables the elements with ids passed as an array
// if enable is true, the elements are enabled and vice-versa
function enableDisableElementsById(ids, enable) {
    for (let i=0; i<ids.length; i++) {
        let element = document.getElementById(ids[i]);
        if (element) {
            element.disabled = (!enable);
        }
    }
}

// sets a spinner inside the division with given id
// also sets a custom message inside the division
// this indicates that an ajax call related to that element is in progress
function setSpinnerToDiv(id, message) {
    let element = document.getElementById(id);
    if (element) {
        element.innerHTML = '<div class="container-fluid d-flex align-content-between">' +
                                '<strong>'+message+'</strong>' +
                                '<div class="spinner-border ms-auto" role="status" aria-hidden="true"></div>' +
                            '</div>';
    }
}

function fetchVehicles() {
    // following elemets will be blocked (disabled) when we make the request
    let elements_to_block = ['vehicle', 'version', 'board', 'submit', 'reset_def', 'exp_col_button'];
    enableDisableElementsById(elements_to_block, false);
    let request_url = '/api/v1/vehicles';
    setSpinnerToDiv('vehicle_list', 'Fetching vehicles...');
    sendAjaxRequestForJsonResponse(request_url)
        .then((json_response) => {
            let all_vehicles = json_response;
            
            if (rebuildConfig.vehicleId) {
                const vehicleExists = all_vehicles.some(v => v.id === rebuildConfig.vehicleId);
                if (!vehicleExists) {
                    console.warn(`Rebuild vehicle '${rebuildConfig.vehicleId}' not found in available vehicles`);
                    alert(`Warning: The vehicle from the original build is no longer available.\n\nRedirecting to new build page...`);
                    window.location.href = '/add_build';
                    return;
                }
            }
            
            let new_vehicle = rebuildConfig.vehicleId || 
                             (all_vehicles.find(vehicle => vehicle.name === "Copter") ? "copter" : all_vehicles[0].id);
            updateVehicles(all_vehicles, new_vehicle);
        })
        .catch((message) => {
            console.log("Vehicle update failed. "+message);
        })
        .finally(() => {
            enableDisableElementsById(elements_to_block, true);
        });
}

function updateVehicles(all_vehicles, new_vehicle_id) {
    let vehicle_element = document.getElementById('vehicle');
    let old_vehicle_id = vehicle_element ? vehicle_element.value : '';
    fillVehicles(all_vehicles, new_vehicle_id);
    if (old_vehicle_id != new_vehicle_id) {
        onVehicleChange(new_vehicle_id);
    }
}

function onVehicleChange(new_vehicle_id) {
    // following elemets will be blocked (disabled) when we make the request
    let elements_to_block = ['vehicle', 'version', 'board', 'submit', 'reset_def', 'exp_col_button'];
    enableDisableElementsById(elements_to_block, false);
    let request_url = '/api/v1/vehicles/'+new_vehicle_id+'/versions';
    setSpinnerToDiv('version_list', 'Fetching versions...');
    sendAjaxRequestForJsonResponse(request_url)
        .then((json_response) => {
            let all_versions = json_response;
            all_versions = sortVersions(all_versions);
            
            if (rebuildConfig.versionId) {
                const versionExists = all_versions.some(v => v.id === rebuildConfig.versionId);
                if (!versionExists) {
                    console.warn(`Rebuild version '${rebuildConfig.versionId}' not found for vehicle '${new_vehicle_id}'`);
                    alert(`Warning: The version from the original build is no longer available.\n\nRedirecting to new build page...`);
                    window.location.href = '/add_build';
                    return;
                }
            }
            
            const new_version = rebuildConfig.versionId || all_versions[0].id;
            updateVersions(all_versions, new_version);
        })
        .catch((message) => {
            console.log("Version update failed. "+message);
        })
        .finally(() => {
            enableDisableElementsById(elements_to_block, true);
        });
}

function updateVersions(all_versions, new_version) {
    let version_element = document.getElementById('version');
    let old_version = version_element ? version_element.value : '';
    fillVersions(all_versions, new_version);
    if (old_version != new_version) {
        onVersionChange(new_version);
    }
}

function onVersionChange(new_version) {
    // following elemets will be blocked (disabled) when we make the request
    let elements_to_block = ['vehicle', 'version', 'board', 'submit', 'reset_def', 'exp_col_button'];
    enableDisableElementsById(elements_to_block, false);
    let vehicle_id = document.getElementById("vehicle").value;
    let version_id = new_version;
    
    // Fetch boards first
    let boards_url = `/api/v1/vehicles/${vehicle_id}/versions/${version_id}/boards`;
    setSpinnerToDiv('board_list', 'Fetching boards...');
    
    // Clear build options and show loading state
    let temp_container = document.createElement('div');
    temp_container.id = "temp_container";
    temp_container.setAttribute('class', 'container-fluid w-25 mt-3');
    let features_list_element = document.getElementById('build_options');
    features_list_element.innerHTML = "";
    features_list_element.appendChild(temp_container);
    setSpinnerToDiv('temp_container', 'Fetching features...');
    
    // Fetch boards
    sendAjaxRequestForJsonResponse(boards_url)
        .then((boards_response) => {
            // Keep full board objects with id and name
            let boards = boards_response;
            
            if (rebuildConfig.boardId) {
                const boardExists = boards.some(b => b.id === rebuildConfig.boardId);
                if (!boardExists) {
                    console.warn(`Rebuild board '${rebuildConfig.boardId}' not found for version '${version_id}'`);
                    alert(`Warning: The board from the original build is no longer available.\n\nRedirecting to new build page...`);
                    window.location.href = '/add_build';
                    return;
                }
            }
            
            let new_board = rebuildConfig.boardId || (boards.length > 0 ? boards[0].id : null);
            updateBoards(boards, new_board);
        })
        .catch((message) => {
            console.log("Boards update failed. "+message);
        })
        .finally(() => {
            enableDisableElementsById(elements_to_block, true);
        });
}

function updateBoards(all_boards, new_board) {
    currentBoards = all_boards || [];
    let board_element = document.getElementById('board');
    let old_board = board_element ? board_element.value : '';
    let old_board = board_element ? board_element.value : '';
    fillBoards(all_boards, new_board);
    if (old_board != new_board) {
        onBoardChange(new_board);
    }
}

function onBoardChange(new_board) {
    // When board changes, fetch features for the new board
    let vehicle_id = document.getElementById('vehicle').value;
    let version_id = document.getElementById('version').value;
    
    let temp_container = document.createElement('div');
    temp_container.id = "temp_container";
    temp_container.setAttribute('class', 'container-fluid w-25 mt-3');
    let features_list_element = document.getElementById('build_options');
    features_list_element.innerHTML = "";
    features_list_element.appendChild(temp_container);
    setSpinnerToDiv('temp_container', 'Fetching features...');
    
    let features_url = `/api/v1/vehicles/${vehicle_id}/versions/${version_id}/boards/${new_board}/features`;
    sendAjaxRequestForJsonResponse(features_url)
        .then((features_response) => {
            Features.reset(features_response);
            fillBuildOptions(features_response);
            
            // TODO: Refactor to use a single method to apply both rebuild and default features
            if (rebuildConfig.isRebuildMode) {
                applyRebuildFeatures(rebuildConfig.selectedFeatures);
                clearRebuildConfig();
            } else {
                Features.applyDefaults();
            }
        })
        .catch((message) => {
            console.log("Features update failed. "+message);
        });
}

function fillBoards(boards, default_board_id) {
    let output = document.getElementById('board_list');
    output.innerHTML =  '<label for="board" class="form-label"><strong>Select Board</strong></label>' +
                        '<select name="board" id="board" class="form-select" aria-label="Select Board" onchange="onBoardChange(this.value);"></select>';
    let boardList = document.getElementById("board")
    boards.forEach(board => {
        const boardName = (typeof board === 'object' && board !== null) ? board.name : board;
        const hasCan = (typeof board === 'object' && board !== null) ? Boolean(board.has_can) : false;
        if (!boardName) {
            return;
        }
        let opt = document.createElement('option');
        opt.value = board.id;
        opt.innerHTML = board.name;
        opt.selected = (board.id === default_board_id);
        boardList.appendChild(opt);
    });
}


var toggle_all_categories = (() => {
    let all_categories_expanded = init_categories_expanded;

    function toggle_method() {
        // toggle global state
        all_categories_expanded = !all_categories_expanded;

        let all_collapse_elements = document.getElementsByClassName('feature-group');

        for (let i=0; i<all_collapse_elements.length; i+=1) {
            let collapse_element = all_collapse_elements[i];
            collapse_instance = bootstrap.Collapse.getOrCreateInstance(collapse_element);
            if (all_categories_expanded && !collapse_element.classList.contains('show')) {
                collapse_instance.show();
            } else if (!all_categories_expanded && collapse_element.classList.contains('show')) {
                collapse_instance.hide();
            }
        }
    }

    return toggle_method;
})();

function createCategoryCard(category_name, features_in_category, expanded) {
    options_html = "";
    features_in_category.forEach(feature => {
        options_html += '<div class="form-check">' +
                            '<input class="form-check-input feature-checkbox" type="checkbox" value="1" name="'+feature.id+'" id="'+feature.id+'" onclick="Features.handleOptionStateChange(this.id, true);">' +
                            '<label class="form-check-label ms-2" for="'+feature.id+'">' +
                                (feature.description || feature.name) +
                            '</label>' +
                        '</div>';
    });

    let id_prefix = Features.getCategoryIdByName(category_name);
    let card_element = document.createElement('div');
    card_element.setAttribute('class', 'card ' + (expanded == true ? 'h-100' : ''));
    card_element.id = id_prefix + '_card';
    card_element.innerHTML =    '<div class="card-header ps-3">' +
                                    '<div class="d-flex justify-content-between">' +
                                        '<div class="d-inline-flex">' +
                                            '<span class="align-middle me-3"><input class="form-check-input" type="checkbox" id="'+Features.getCategoryIdByName(category_name)+'" onclick="Features.checkUncheckCategory(\''+category_name+'\', this.checked);"></span>' +
                                            '<strong>' +
                                                '<label for="check-uncheck-category">' + category_name + '</label>' +
                                            '</strong>' +
                                        '</div>' +
                                        '<button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#'+id_prefix+'_collapse" aria-expanded="false" aria-controls="'+id_prefix+'_collapse">' +
                                            '<i class="bi bi-chevron-'+(expanded == true ? 'up' : 'down')+'" id="'+id_prefix+'_icon'+'"></i>' +
                                        '</button>' +
                                    '</div>' +
                                '</div>';
    let collapse_element = document.createElement('div');
    collapse_element.setAttribute('class', 'feature-group collapse '+(expanded == true ? 'show' : ''));
    collapse_element.id = id_prefix + '_collapse';
    collapse_element.innerHTML = '<div class="container-fluid px-3 py-2">'+options_html+'</div>';
    card_element.appendChild(collapse_element);

    // add relevent event listeners
    collapse_element.addEventListener('hide.bs.collapse', () => {
        card_element.classList.remove('h-100');
        document.getElementById(id_prefix+'_icon').setAttribute('class', 'bi bi-chevron-down');
    });
    collapse_element.addEventListener('shown.bs.collapse', () => {
        card_element.classList.add('h-100');
        document.getElementById(id_prefix+'_icon').setAttribute('class', 'bi bi-chevron-up');
    });

    return card_element;                  
}

function fillBuildOptions(features) {
    let output = document.getElementById('build_options');
    output.innerHTML =  `<div class="d-flex mb-3 justify-content-between">
                            <div class="d-flex d-flex align-items-center">
                                <p class="card-text"><strong>Available features for the current selection are:</strong></p>
                            </div>
                            <button type="button" class="btn btn-outline-primary" id="exp_col_button" onclick="toggle_all_categories();"><i class="bi bi-chevron-expand me-2"></i>Expand/Collapse all categories</button> 
                        </div>`;

    // Group features by category
    let categories_map = {};
    features.forEach(feature => {
        const cat_name = feature.category.name;
        if (!categories_map[cat_name]) {
            categories_map[cat_name] = [];
        }
        categories_map[cat_name].push(feature);
    });

    // Convert to array and display
    let categories = Object.entries(categories_map).map(([name, feats]) => ({name, features: feats}));
    
    categories.forEach((category, cat_idx) => {
        if (cat_idx % 4 == 0) {
            let new_row = document.createElement('div');
            new_row.setAttribute('class', 'row');
            new_row.id = 'category_'+parseInt(cat_idx/4)+'_row';
            output.appendChild(new_row);
        }
        let col_element = document.createElement('div');
        col_element.setAttribute('class', 'col-md-3 col-sm-6 mb-2');
        col_element.appendChild(createCategoryCard(category.name, category.features, init_categories_expanded));
        document.getElementById('category_'+parseInt(cat_idx/4)+'_row').appendChild(col_element);
    });
}

// returns a Promise
// the promise is resolved when we recieve status code 200 from the AJAX request
// the JSON response for the request is returned in such case
// the promise is rejected when the status code is not 200
// the status code is returned in such case
function sendAjaxRequestForJsonResponse(url) {
    return new Promise((resolve, reject) => {
        var xhr = new XMLHttpRequest();
        xhr.open('GET', url);

        // disable cache, thanks to: https://stackoverflow.com/questions/22356025/force-cache-control-no-cache-in-chrome-via-xmlhttprequest-on-f5-reload
        xhr.setRequestHeader("Cache-Control", "no-cache, no-store, max-age=0");
        xhr.setRequestHeader("Expires", "Tue, 01 Jan 1980 1:00:00 GMT");
        xhr.setRequestHeader("Pragma", "no-cache");

        xhr.onload = function () {
            if (xhr.status == 200) {
                resolve(JSON.parse(xhr.response));
            } else {
                reject("Got response:"+xhr.response+" (Status Code: "+xhr.status+")");
            }
        }
        xhr.send();
    });
}

function fillVehicles(vehicles, vehicle_id_to_select) {
    var output = document.getElementById('vehicle_list');
    output.innerHTML =  '<label for="vehicle" class="form-label"><strong>Select Vehicle</strong></label>' +
                        '<select name="vehicle" id="vehicle" class="form-select" aria-label="Select Vehicle" onchange="onVehicleChange(this.value);"></select>';
    vehicleList = document.getElementById("vehicle");
    vehicles.forEach(vehicle => {
        opt = document.createElement('option');
        opt.value = vehicle.id;
        opt.innerHTML = vehicle.name;
        opt.selected = (vehicle.id === vehicle_id_to_select);
        vehicleList.appendChild(opt);
    });
}

function compareVersionNums(a, b) {
  const versionRegex = /(\d+)\.(\d+)\.(\d+)/;

  const [, aMajor, aMinor, aPatch] = a.match(versionRegex).map(Number);
  const [, bMajor, bMinor, bPatch] = b.match(versionRegex).map(Number);

  if (aMajor !== bMajor) return bMajor - aMajor;
  if (aMinor !== bMinor) return bMinor - aMinor;
  return bPatch - aPatch;
}

function sortVersions(versions) {
    const order = {
        "beta"  : 0,
        "latest": 1,
        "stable": 2,
        "tag"   : 3,
    }

    versions.sort((a, b) => {
        // sort the version types in order mentioned above
        if (a.type != b.type) {
            return order[a.type] - order[b.type];
        }

        // for numbered versions, do reverse sorting to make sure recent versions come first
        if (a.type == "stable" || b.type == "beta") {
            return compareVersionNums(a.name.split(" ")[1], b.name.split(" ")[1]);
        }

        return a.name.localeCompare(b.name);
    });

    // Push the first stable version in the list to the top
    const firstStableIndex = versions.findIndex(v => v.name.split(" ")[0].toLowerCase() === "stable");
    if (firstStableIndex !== -1) {
        const stableVersion = versions.splice(firstStableIndex, 1)[0];
        versions.unshift(stableVersion);
    }

    return versions;
}

function fillVersions(versions, version_to_select) {
    var output = document.getElementById('version_list');
    output.innerHTML =  '<label for="version" class="form-label"><strong>Select Version</strong></label>' +
                        '<select name="version" id="version" class="form-select" aria-label="Select Version" onchange="onVersionChange(this.value);"></select>';
    versionList = document.getElementById("version");

    versions.forEach(version => {
        opt = document.createElement('option');
        opt.value = version.id;
        opt.innerHTML = version.name;
        opt.selected = (version.id === version_to_select);
        versionList.appendChild(opt);
    });
}

// Handle form submission
async function handleFormSubmit(event) {
    event.preventDefault();
    
    const submitButton = document.getElementById('submit');
    const originalButtonText = submitButton.innerHTML;
    
    try {
        // Disable submit button and show loading state
        submitButton.disabled = true;
        submitButton.innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Submitting...';
        
        // Collect form data
        const vehicle_id = document.getElementById('vehicle').value;
        const version_id = document.getElementById('version').value;
        const board_id = document.getElementById('board').value;
        
        // Collect selected features - checkboxes now have feature IDs directly
        const selected_features = [];
        const checkboxes = document.querySelectorAll('.feature-checkbox:checked');
        checkboxes.forEach(checkbox => {
            // The checkbox ID is already the feature define (ID)
            selected_features.push(checkbox.id);
        });
        
        // Create build request payload
        const buildRequest = {
            vehicle_id: vehicle_id,
            version_id: version_id,
            board_id: board_id,
            selected_features: selected_features
        };
        
        // Send POST request to API
        const response = await fetch('/api/v1/builds', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify(buildRequest)
        });
        
        if (!response.ok) {
            const errorData = await response.json();
            throw new Error(errorData.detail || 'Failed to submit build');
        }
        
        const result = await response.json();
        
        // Redirect to viewlog page
        window.location.href = `/?build_id=${result.build_id}`;
        
    } catch (error) {
        console.error('Error submitting build:', error);
        alert('Failed to submit build: ' + error.message);
        
        // Re-enable submit button
        submitButton.disabled = false;
        submitButton.innerHTML = originalButtonText;
    }
}

// Initialize form submission handler
document.addEventListener('DOMContentLoaded', () => {
    const buildForm = document.getElementById('build-form');
    if (buildForm) {
        buildForm.addEventListener('submit', handleFormSubmit);
    }
});
