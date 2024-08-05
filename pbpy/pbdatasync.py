from pbpy import pbtools
from pbpy import pbgit
from pbpy import pbconfig
from pbpy import pbunreal


def get_oid(path):
    oid_pairs = pbtools.get_combined_output(
        pbgit.get_lfs_executable(), "ls-files", "-l", "-I", path
    ).splitlines()
    for oid_pair in oid_pairs:
        oid_pair = oid_pair.split(" * ")
        oid = oid_pair[0]
        file = oid_pair[1]
        yield oid, file


def get_remote_file_name(file, oid=None):
    if oid is None:
        oid = get_oid(file)
    file = file.replace(".umap", "")
    return f"{file}/{file}_BuiltData_{oid}.uasset"


def get_remote_path(file, oid=None):
    file_name = get_remote_file_name(file, oid)
    gcs_uri = f"{pbunreal.get_ddc_gsuri()}{pbconfig.get('ddc_key')}"
    return f"{gcs_uri}/BuiltData/{file_name}"


def get_all_maps():
    include_globs = pbconfig.get_user("project", "include", default="Content").split(
        ","
    )
    include_globs = [path.strip() for path in include_globs]
    for glob in include_globs:
        yield get_oid(f"{glob}/**/*.umap")


def pull_data():
    for oid, file in get_all_maps():
        remote_file = get_remote_path(file, oid)
        data_path = file.replace(".umap", "_BuildData.uasset")
        command_runner = pbunreal.init_gcs()
        try:
            command_runner.RunNamedCommand(
                "rsync",
                args=["-Cir", remote_file, data_path],
                collect_analytics=False,
                skip_update_check=True,
                parallel_operations=True,
            )
        except:
            # keep going
            pass


def push_data():
    for oid, file in get_all_maps():
        remote_file = get_remote_path(file, oid)
        data_path = file.replace(".umap", "_BuildData.uasset")
        command_runner = pbunreal.init_gcs()
        command_runner.RunNamedCommand(
            "rsync",
            args=["-Cir", data_path, remote_file],
            collect_analytics=False,
            skip_update_check=True,
            parallel_operations=True,
        )
