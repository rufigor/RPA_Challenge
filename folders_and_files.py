import json


def read_json_file(json_file_path) -> dict:
    """
    Read a JSON file and return its contents as a dictionary.

    Args:
        json_file_path (str): path where the json file is located.

    Returns:
        dict: a dictionary containing the contents of the JSON file.
    """
    with open(json_file_path) as json_file:
        data = json.load(json_file)
        dict_return = data.get('payload')
    return dict_return

