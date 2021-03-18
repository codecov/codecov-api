from ariadne import load_schema_from_path
import pathlib

def ariadne_load_local_graphql(current_file, graphql_file):
    """
    Given the current_file (__file__) of the caller and a graphql file name
    import that file and load it with ariadne.load_schema_from_path
    """
    current_dir = pathlib.Path(current_file).parent.absolute()
    graphql_file_path = current_dir.joinpath(graphql_file)
    return load_schema_from_path(graphql_file_path)
