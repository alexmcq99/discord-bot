import json

# Read a json file to a dictionary
# Return an empty dictionary if not found
def read_json_file(file):
    try:
        with open(file) as f:
            data = json.load(f)
    except FileNotFoundError as e:
        data = {}
    except Exception as e:
        print("Error reading json file")
        # logging.debug("Unexpected error in reading file: " + str(e))
    
    return data

# Write data back to disk as json file
# Done when bot exits, data is stored in dictionaries while running
def write_json_file(file, data):
    with open(file, "w") as f:
        json.dump(data, f, indent=4)