from flexx import flx

class CommitLogTableWidget(flx.Widget):

    commits = flx.ListProp()
    commit_nodes = flx.ListProp()

    dropdown_map = {}

    def _create_dom(self):
        self.root.get_commits()
        return flx.create_element('div', {'class': 'table-responsive'})

    def _render_dom(self):
        return flx.create_element('div', {'class': 'table-responsive'},
                                            flx.create_element('table', {'class': 'table table-dark table-hover table-borderless'},
                                                flx.create_element('thead', None, 
                                                    flx.create_element('tr', {'class': 'text-muted'}, 
                                                        flx.create_element('th', {"scope": "col"}, 'COMMIT'),
                                                        flx.create_element('th', {"scope": "col"}, 'TIME'),
                                                        flx.create_element('th', {"scope": "col"}, 'AUTHOR'),
                                                        flx.create_element('th', {"scope": "col"}, 'MESSAGE')
                                                    )
                                                ),
                                                flx.create_element('tbody', None, self.commit_nodes)
                                            )
                                )

    @flx.reaction('commits')
    def on_update_commits(self):
        global window
        new_nodes = []
        current_day = None
        for commit in self.commits:
            time = commit.get("time").split(" ")

            date = time[0] + " " + time[1] + " " + time[2] + " " + time[4]
            if date != current_day:
                current_day = date
                date_node = flx.create_element('table', {'class': 'table table-dark table-borderless table-sm m-0 lead'},
                                                         flx.create_element('tbody', None,
                                                            flx.create_element('tr', None,
                                                                flx.create_element('td', None, current_day)
                                                            )
                                                         )
                )
                new_nodes.append(date_node)
                new_nodes.append(flx.create_element('hr', {'class': 'bg-light', 'style': 'width:100vw; position:absolute; margin:0'}))

            time = time[3]
            time_units = time.split(":")
            hours = int(time_units[0])
            division = "PM"
            if hours > 12:
                hours -= 12
            elif hours != 12:
                division = "AM"

            time = hours + ":" + time_units[1] + division

            short_sha = commit.get("sha")[:8]

            author = commit.get("author")

            if author == "ProjectBorealisTeam":
                author = "Project Borealis"

            author_props = None
            if author == "Project Borealis":
                author_props = {"class": "text-warning"}
            elif author == window.GH_USER:
                author_props = {"class": "text-info"}
                author += " (you)"
                

            commit_node = flx.create_element('tr', None,
                                                flx.create_element('td', {"scope": "row", "id": commit.get("sha")}, flx.create_element("span", {"class": "far fa-fw"}), " " + short_sha + " (" + commit.get("human") + ")"),
                                                flx.create_element('td', None, time),
                                                flx.create_element('td', author_props, author),
                                                flx.create_element('td', None,
                                                    flx.create_element('div', {"class": "row"},
                                                        flx.create_element('div', {"class": "col-11"},
                                                            commit.get("message")
                                                        ),
                                                        flx.create_element('div', {"class": "col-1"},
                                                            flx.create_element("div", {"class": "dropdown commit-dropdown"},
                                                                flx.create_element("button", {"class": "btn btn-outline-light dropdown-toggle", "type": "button", "data-bs-toggle": "dropdown", "id": "dropdown-" + short_sha, "aria-expanded": "false"}),
                                                                flx.create_element("ul", {"class": "dropdown-menu dropdown-menu-dark", "aria-labelledby": "dropdown-" + short_sha},
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("h6", {"class": "dropdown-header"}, "STATUS")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("a", {"class": "dropdown-item"}, "Mark as Good")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("a", {"class": "dropdown-item"}, "Mark as Bad")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("hr", {"class": "dropdown-divider"})
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("h6", {"class": "dropdown-header"}, "VERSIONING")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("a", {"class": "dropdown-item"}, "Switch to Version")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("a", {"class": "dropdown-item"}, "Request Binaries Build")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("hr", {"class": "dropdown-divider"})
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("h6", {"class": "dropdown-header"}, "SOURCE CONTROL")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("a", {"class": "dropdown-item"}, "Revert")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("a", {"class": "dropdown-item"}, "Copy to Branch")
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("hr", {"class": "dropdown-divider"})
                                                                    ),
                                                                    flx.create_element("li", None,
                                                                        flx.create_element("a", {"class": "dropdown-item"}, "View on GitHub")
                                                                    )
                                                                )
                                                            )
                                                        )
                                                    )
                                                )
                                            )
            new_nodes.append(commit_node)

        for node in self.commit_nodes:
            node.dispose()

        self.update_commit_nodes(new_nodes)

    @flx.reaction('commit_nodes')
    def on_update_commit_nodes(self):
        global window
        window.post_commit_update(self.outernode)

    @flx.action
    def update_commits(self, commits):
        self._mutate_commits(commits)

    @flx.action
    def update_commit_nodes(self, commit_nodes):
        self._mutate_commit_nodes(commit_nodes)
