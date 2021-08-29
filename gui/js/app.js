
// Create Flexx elements inline
if (!customElements.get("x-flx")) {
    class Flexx extends HTMLDivElement {
        constructor() {
            super();
        }
    }

    customElements.define("x-flx", Flexx, { extends: 'div' })
}

let app = null;
let react = null;

const reqHeaders = {
  headers: {
    'User-Agent': 'ProjectBorealis-PBSync',
  },
}

let reqGHAPIHeaders = {
  headers: {
    'Accept': 'application/vnd.github.v3+json',
    'Content-Type': 'application/json;charset=UTF-8',
    ...reqHeaders.headers
  }
}

// React function helpers
function changePage(page) {
    react("change_page", page)
}

function markCommit(sha, status) {
    console.log("sha")
    let commitNode = document.getElementById(sha)
    if (status == "success") {
        commitNode.parentElement.classList.remove("table-danger")
        commitNode.children[0].classList.add("fa-check-circle")
        commitNode.children[0].classList.remove("fa-times-circle")
    } else if (status == "failure") {
        commitNode.parentElement.classList.add("table-danger")
        commitNode.children[0].classList.add("fa-times-circle")
        commitNode.children[0].classList.remove("fa-check-circle")
    }
    react("mark_commit", sha, status)
}

// Element handlers
window.elementHandlers = {
};

window.post_commit_update = function(el) {
    let table = el.children[0];
    let tbody = table.children[1];
    for (const row of tbody.children) {
        if (row.nodeName != "TR") {
            continue;
        }
        let commitNode = row.children[0];
        let status = row.dataset.status;
        let commit = commitNode.id;
        // try getting our metadata status, if we have it
        if (status) {
            if (status == "success") {
                commitNode.children[0].classList.add("fa-check-circle");
            } else if (status == "failure") {
                row.classList.add("table-danger");
                commitNode.children[0].classList.add("fa-times-circle");
            }
        } else {
            // fetch build status from github
            fetch("https://api.github.com/repos/" + window.GH_REPO + "/commits/" + commit + "/check-suites?app_id=15368", reqGHAPIHeaders)
            .then((response) => response.json())
            .then((data) => {
                let status = "success";
                let checks = 0;
                for (const check of data.check_suites) {
                    if (check.status == "completed") {
                        checks++;
                        if (check.conclusion != "success") {
                            status = ""
                        } else if (data.conclusion == "failure") {
                            status = "failure"
                            break;
                        }
                    }
                }
                if (checks > 1) {
                    if (status == "success") {
                        commitNode.children[0].classList.add("fa-check-circle");
                    } else if (status == "failure") {
                        row.classList.add("table-danger");
                        commitNode.children[0].classList.add("fa-times-circle");
                    }
                }
            });
        }
        let dropdown = row.children[row.children.length - 1].children[0].children[1].children[0]; // td -> row -> col-1 -> dropdown
        let dropdownBtn = dropdown.children[0];
        dropdownBtn.onclick = () => {
            bootstrap.Dropdown.getOrCreateInstance(dropdownBtn).toggle();
            row.classList.toggle("active");
        }
        let menuItems = dropdown.children[1].children;
        for (const menuItem of menuItems) {
            menuItem.children[0].onclick = () => {
                if (menuItem.dataset.func == "mark_commit") {
                    markCommit(commit, menuItem.dataset.status)
                }
            }
        }
    }
}

// Hook up JavaScript communication
// and callback to notify Python
function callback() {
    console.log("App loaded")
    app = document.getElementById("app")
    react = app.onreact
    reqGHAPIHeaders.headers.Authorization = window.GH_AUTH

    react("app_update")

    let observer = new MutationObserver(() => {
        react("app_update")
    })

    observer.observe(app, {
        subtree: true,
        attributes: true,
        childList: true,
        characterData: true
    })
}

let observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
        if (!mutation.addedNodes) return

        for (let i = 0; i < mutation.addedNodes.length; i++) {
            // do things to your newly added nodes here
            let node = mutation.addedNodes[i]
            if (node.id === "app") {
                observer.disconnect()
                callback()
                return
            }
        }
    })
})

observer.observe(document.body, {
    childList: true,
    subtree: true
})