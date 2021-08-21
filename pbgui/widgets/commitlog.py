from flexx import flx


class CommitLogTable(flx.Widget):

    commits = flx.ListProp()
    commit_nodes = flx.ListProp()

    def _create_dom(self):
        self.root.get_commits()
        return flx.create_element('div', {'class': 'table-responsive'})

    def _render_dom(self):
        return flx.create_element('div', {'class': 'table-responsive'},
                                            flx.create_element('table', {'class': 'table table-dark table-hover table-borderless'},
                                                flx.create_element('thead', None, 
                                                    flx.create_element('tr', None, 
                                                        flx.create_element('th', {"scope": "col"}, 'Commit'),
                                                        flx.create_element('th', {"scope": "col"}, 'Time'),
                                                        flx.create_element('th', {"scope": "col"}, 'Author'),
                                                        flx.create_element('th', {"scope": "col"}, 'Message')
                                                    )
                                                ),
                                                flx.create_element('tbody', None, self.commit_nodes)
                                            )
                                )

    @flx.reaction('commits')
    def on_update_commits(self):
        new_nodes = []
        current_day = None
        for commit in self.commits:
            status = commit.get("pass")
            if status == "success":
                row_color = ""
            elif status == "fail":
                row_color = "table-danger"
            else:
                row_color = "table-warning"

            time = commit.get("time").split(" ")

            date = time[0] + " " + time[1] + " " + time[2] + " " + time[4]
            if date != current_day:
                current_day = date
                date_node = flx.create_element('table', {'class': 'table table-dark table-borderless table-sm m-0'},
                                                         flx.create_element('tbody', None,
                                                            flx.create_element('tr', None,
                                                                flx.create_element('th', None, current_day)
                                                            )
                                                         )
                )
                new_nodes.append(date_node)

            time = time[3]
            time_units = time.split(":")
            hours = int(time_units[0])
            division = "PM"
            if hours > 12:
                hours -= 12
            elif hours != 12:
                division = "AM"

            time = hours + ":" + time_units[1] + division

            commit_node = flx.create_element('tr', {"class": f"{row_color}"},
                                                flx.create_element('th', {"scope": "row"}, commit.get("sha")),
                                                flx.create_element('td', None, time),
                                                flx.create_element('td', None, commit.get("author")),
                                                flx.create_element('td', None, commit.get("message"))
                                            )
            new_nodes.append(commit_node)

        for node in self.commit_nodes:
            node.dispose()

        self.update_commit_nodes(new_nodes)

    @flx.action
    def update_commits(self, commits):
        self._mutate_commits(commits)

    @flx.action
    def update_commit_nodes(self, commit_nodes):
        self._mutate_commit_nodes(commit_nodes)
