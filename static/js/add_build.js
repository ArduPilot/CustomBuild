const Features = (() => {
    let features = {};
    let defines_dictionary = {};
    let labels_dictionary = {};

    function resetDictionaries() {
        defines_dictionary = {}; // clear old dictionary
        labels_dictionary = {}; // clear old dictionary
        features.forEach((category, cat_idx) => {
            category['options'].forEach((option, opt_idx) => {
                defines_dictionary[option.define] = labels_dictionary[option.label] = {
                    'category_index' : cat_idx,
                    'option_index' : opt_idx,
                };
            });
        });
    }

    function updateRequiredFor() {
        features.forEach((category) => {
            category['options'].forEach((option) => {
                if (option.dependency != null) {
                    option.dependency.split(',').forEach((dependency) => {
                        let dep = getByLabel(dependency);
                        if (dep.requiredFor == undefined) {
                            dep.requiredFor = [];
                        }
                        dep.requiredFor.push(option.label);
                    });
                }
            });
        });
    }

    function reset(new_features) {
        features = new_features;
        resetDictionaries();
        updateRequiredFor();
    }

    function getByDefine(define) {
        let dict_value = defines_dictionary[define];
        if (dict_value == undefined) {
            return null;
        }
        return features[dict_value['category_index']]['options'][dict_value['option_index']];
    }

    function getByLabel(label) {
        let dict_value = labels_dictionary[label];
        if (dict_value == undefined) {
            return null;
        }
        return features[dict_value['category_index']]['options'][dict_value['option_index']];
    }

    function updateDefaults(defines_array) {
        // updates default on the basis of define array passed
        // the define array consists define in format, EXAMPLE_DEFINE or !EXAMPLE_DEFINE
        // we update the defaults in features object by processing those defines
        for (let i=0; i<defines_array.length; i++) {
            let select_opt = (defines_array[i][0] != '!');
            let sanitised_define = (select_opt ? defines_array[i] : defines_array[i].substring(1)); // this removes the leading '!' from define if it contatins
            if (getByDefine(sanitised_define)) {
                let cat_idx = defines_dictionary[sanitised_define]['category_index'];
                let opt_idx = defines_dictionary[sanitised_define]['option_index'];
                getByDefine(sanitised_define).default = select_opt ? 1 : 0;
            }
        }
    }

    function fixDepencencyHelper(feature_label, visited) {
        if (visited[feature_label] != undefined ) {
            return;
        }

        visited[feature_label] = true;
        document.getElementById(feature_label).checked = true;
        let feature = getByLabel(feature_label);

        if (feature.dependency == null) {
            return;
        }

        let children = feature.dependency.split(',');
        children.forEach((child) => {
            fixDepencencyHelper(child, visited);
        });
    }

    function fixAllDependencies() {
        var visited = {};
        Object.keys(labels_dictionary).forEach((label) => {
            if (document.getElementById(label).checked) {
                fixDepencencyHelper(label, visited);
            }
        });
    }

    function handleDependenciesForFeature(feature_label) {
        var visited = {};
        if (document.getElementById(feature_label).checked) {
            fixDepencencyHelper(feature_label, visited);
        } else {
            enabled_dependent_features = getEnabledDependentFeaturesFor(feature_label);
            if (enabled_dependent_features.length > 0) {
                document.getElementById('modalBody').innerHTML = "The feature(s) <strong>"+enabled_dependent_features.join(", ")+"</strong> is/are dependant on <strong>"+feature_label+"</strong>" +
                                                                 " and hence will be disabled too.<br><strong>Do you want to continue?</strong>";
                document.getElementById('modalDisableButton').onclick = () => { disableCheckboxesByIds(enabled_dependent_features); }
                document.getElementById('modalCancelButton').onclick = document.getElementById('modalCloseButton').onclick = () => { document.getElementById(feature_label).checked = true; };
                var confirmationModal = bootstrap.Modal.getOrCreateInstance(document.getElementById('dependencyCheckModal'));
                confirmationModal.show();
            }
        }
    }

    function getEnabledDependentFeaturesHelper(feature_label,  visited, dependent_features) {
        if (visited[feature_label] != undefined || document.getElementById(feature_label).checked == false) {
            return;
        }

        visited[feature_label] = true;
        dependent_features.push(feature_label);

        let feature = getByLabel(feature_label);
        if (feature.requiredFor == null) {
            return;
        }

        feature.requiredFor.forEach((dependent_feature) => {
            getEnabledDependentFeaturesHelper(dependent_feature, visited, dependent_features);
        });
    }

    function getEnabledDependentFeaturesFor(feature_label) {
        let dependent_features = [];
        let visited = {};

        if (getByLabel(feature_label).requiredFor) {
            getByLabel(feature_label).requiredFor.forEach((dependent_feature) => {
                getEnabledDependentFeaturesHelper(dependent_feature, visited, dependent_features);
            });
        }

        return dependent_features;
    }

    function disableDependents(feature_label) {
        if (getByLabel(feature_label).requiredFor == undefined) {
            return;
        }

        getByLabel(feature_label).requiredFor.forEach((dependent_feature) => {
            document.getElementById(dependent_feature).checked = false;
        });
    }

    function applyDefaults() {
        features.forEach(category => {
            category['options'].forEach(option => {
                element = document.getElementById(option['label']);
                if (element != undefined) {
                    element.checked = (option['default'] == 1);
                }
            });
        });
        fixAllDependencies();
    }

    return {reset, handleDependenciesForFeature, disableDependents, updateDefaults, applyDefaults};
})();

var all_categories_expanded = false;

var pending_update_calls = 0;   // to keep track of unresolved Promises

function init() {
    onVehicleChange(document.getElementById("vehicle").value);
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

function disableCheckboxesByIds(ids) {
    ids.forEach((id) => {
        box_element = document.getElementById(id);
        if (box_element) {
            box_element.checked = false;
        }
    })
}

function onVehicleChange(new_vehicle) {
    // following elemets will be blocked (disabled) when we make the request
    let elements_to_block = ['vehicle', 'branch', 'board', 'submit', 'reset_def', 'exp_col_button'];
    enableDisableElementsById(elements_to_block, false);
    let request_url = '/get_allowed_branches/'+new_vehicle;
    setSpinnerToDiv('branch_list', 'Fetching branches...');
    pending_update_calls += 1;
    sendAjaxRequestForJsonResponse(request_url)
        .then((json_response) => {
            let new_branch = json_response.default_branch;
            let all_branches = json_response.branches;
            updateBranches(all_branches, new_branch);
        })
        .catch((message) => {
            console.log("Branch update failed. "+message);
        })
        .finally(() => {
            enableDisableElementsById(elements_to_block, true);
            pending_update_calls -= 1;
            fetchAndUpdateDefaults();
        });
}

function updateBranches(all_branches, new_branch) {
    let branch_element = document.getElementById('branch');
    let old_branch = branch_element ? branch_element.value : '';
    fillBranches(all_branches, new_branch);
    if (old_branch != new_branch) {
        onBranchChange(new_branch);
    }
}

function onBranchChange(new_branch) {
    // following elemets will be blocked (disabled) when we make the request
    let elements_to_block = ['vehicle', 'branch', 'board', 'submit', 'reset_def', 'exp_col_button'];
    enableDisableElementsById(elements_to_block, false);
    let request_url = '/boards_and_features/'+new_branch;

    // create a temporary container to set spinner inside it
    let temp_container = document.createElement('div');
    temp_container.id = "temp_container";
    temp_container.setAttribute('class', 'container-fluid w-25 mt-3');
    let features_list_element = document.getElementById('build_options');   // append the temp container to the main features_list container
    features_list_element.innerHTML = "";
    features_list_element.appendChild(temp_container);
    setSpinnerToDiv('temp_container', 'Fetching features...');
    setSpinnerToDiv('board_list', 'Fetching boards...');
    pending_update_calls += 1;
    sendAjaxRequestForJsonResponse(request_url)
        .then((json_response) => {
            let boards = json_response.boards;
            let new_board = json_response.default_board;
            let new_features = json_response.features;
            Features.reset(new_features);
            updateBoards(boards, new_board);
            fillBuildOptions(new_features);
        })
        .catch((message) => {
            console.log("Boards and features update failed. "+message);
        })
        .finally(() => {
            enableDisableElementsById(elements_to_block, true);
            pending_update_calls -= 1;
            fetchAndUpdateDefaults();
        });
}

function updateBoards(all_boards, new_board) {
    let board_element = document.getElementById('board');
    let old_board = board_element ? board.value : '';
    fillBoards(all_boards, new_board);
    if (old_board != new_board) {
        onBoardChange(new_board);
    }
}

function onBoardChange(new_board) {
    fetchAndUpdateDefaults();
}

function fetchAndUpdateDefaults() {
    // return early if there is an unresolved promise (i.e., there is an ongoing ajax call)
    if (pending_update_calls > 0) {
        return;
    }
    elements_to_block = ['reset_def'];
    document.getElementById('reset_def').innerHTML = '<span class="spinner-border spinner-border-sm me-2" role="status" aria-hidden="true"></span>Fetching defaults';
    enableDisableElementsById(elements_to_block, false);
    let branch = document.getElementById('branch').value;
    let vehicle = document.getElementById('vehicle').value;
    let board = document.getElementById('board').value;
    let request_url = '/get_defaults/'+vehicle+'/'+branch+'/'+board;
    sendAjaxRequestForJsonResponse(request_url)
        .then((json_response) => {
            Features.updateDefaults(json_response);
        })
        .catch((message) => {
            console.log("Default reset failed. "+message);
        })
        .finally(() => {
            if (document.getElementById('auto_apply_def').checked) {
                Features.applyDefaults();
            }
            enableDisableElementsById(elements_to_block, true);
            document.getElementById('reset_def').innerHTML = '<i class="bi bi-arrow-counterclockwise me-2"></i>Reset feature defaults';
        });
}

function fillBoards(boards, default_board) {
    let output = document.getElementById('board_list');
    output.innerHTML =  '<label for="board" class="form-label"><strong>Select Board</strong></label>' +
                        '<select name="board" id="board" class="form-select" aria-label="Select Board" onchange="onBoardChange(this.value);"></select>';
    let boardList = document.getElementById("board")
    boards.forEach(board => {
        let opt = document.createElement('option');
        opt.value = board;
        opt.innerHTML = board;
        opt.selected = (board === default_board);
        boardList.appendChild(opt);
    });
}

function toggle_all_categories() {
    // toggle global state
    all_categories_expanded = !all_categories_expanded;

    all_collapse_elements = document.getElementsByClassName('collapse');

    for (let i=0; i<all_collapse_elements.length;) {
        collapse_instance = bootstrap.Collapse.getOrCreateInstance(all_collapse_elements[i]);
        if (all_categories_expanded) {
            collapse_instance.show();
        } else {
            collapse_instance.hide();
        }
    }
}

function createCategoryCard(category_name, options, expanded) {
    options_html = "";
    options.forEach(option => {
        options_html += '<div class="form-check">' +
                            '<input class="form-check-input" type="checkbox" value="1" name="'+option['label']+'" id="'+option['label']+'" onclick="Features.handleDependenciesForFeature(this.id);">' +
                            '<label class="form-check-label" for="'+option['label']+'">' +
                                option['description'].replace(/enable/i, "") +
                            '</label>' +
                        '</div>';
    });

    let id_prefix = category_name.split(" ").join("_");
    let card_element = document.createElement('div');
    card_element.setAttribute('class', 'card ' + (expanded == true ? 'h-100' : ''));
    card_element.id = id_prefix + '_card';
    card_element.innerHTML =    '<div class="card-header">' +
                                    '<div class="d-flex justify-content-between">' +
                                        '<span class="d-flex align-items-center"><strong>'+category_name+'</strong></span>' +
                                        '<button class="btn btn-sm btn-outline-secondary" type="button" data-bs-toggle="collapse" data-bs-target="#'+id_prefix+'_collapse" aria-expanded="false" aria-controls="'+id_prefix+'_collapse">' +
                                            '<i class="bi bi-chevron-'+(expanded == true ? 'up' : 'down')+'" id="'+id_prefix+'_icon'+'"></i>' +
                                        '</button>' +
                                    '</div>' +
                                '</div>';
    let collapse_element = document.createElement('div');
    collapse_element.setAttribute('class', 'collapse '+(expanded == true ? 'show' : ''));
    collapse_element.id = id_prefix + '_collapse';
    collapse_element.innerHTML = '<div class="container-fluid px-2 py-2">'+options_html+'</div>';
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

function fillBuildOptions(buildOptions) {
    let output = document.getElementById('build_options');
    output.innerHTML =  `<div class="d-flex mb-3 justify-content-between">
                            <div class="d-flex d-flex align-items-center">
                                <p class="card-text"><strong>Available features for the current selection are:</strong></p>
                            </div>
                            <button type="button" class="btn btn-outline-primary" id="exp_col_button" onclick="toggle_all_categories();"><i class="bi bi-chevron-expand me-2"></i>Expand/Collapse all categories</button> 
                        </div>`;

    buildOptions.forEach((category, cat_idx) => {
        if (cat_idx % 4 == 0) {
            let new_row = document.createElement('div');
            new_row.setAttribute('class', 'row');
            new_row.id = 'category_'+parseInt(cat_idx/4)+'_row';
            output.appendChild(new_row);
        }
        let col_element = document.createElement('div');
        col_element.setAttribute('class', 'col-md-3 col-sm-6 mb-2');
        col_element.appendChild(createCategoryCard(category['name'], category['options'], all_categories_expanded));
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

function fillBranches(branches, branch_to_select) {
    var output = document.getElementById('branch_list');
    output.innerHTML =  '<label for="branch" class="form-label"><strong>Select Branch</strong></label>' +
                        '<select name="branch" id="branch" class="form-select" aria-label="Select Branch" onchange="onBranchChange(this.value);"></select>';
    branchList = document.getElementById("branch");
    branches.forEach(branch => {
        opt = document.createElement('option');
        opt.value = branch['full_name'];
        opt.innerHTML = branch['label'];
        opt.selected = (branch['full_name'] === branch_to_select);
        branchList.appendChild(opt);
    });
}
