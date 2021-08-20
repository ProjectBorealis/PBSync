
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

// Hook up JavaScript communication
// and callback to notify Python
function callback() {
    console.log("App loaded")
    app = document.getElementById("app")
    react = app.onreact

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

// React function helpers
function changePage(page) {
    react("change_page", page)
}
