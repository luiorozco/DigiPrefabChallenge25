# cadwork MCP plugin: Display all attributes of all elements in the open 3D model
# This script must be run inside cadwork 3D's Python MCP environment
# Documentation: https://docs.cadwork.com/projects/cwapi3dpython/en/latest/

try:
    import cwapi3d.cw as cw
except ImportError:
    print("This script must be run inside cadwork 3D.")
    exit(1)

def get_all_attributes(element_id):
    # Get standard attributes
    std_attrs = cw.get_element_attributes(element_id)
    # Get user-defined attributes
    user_attrs = cw.get_element_user_attributes(element_id)
    return std_attrs, user_attrs

def main():
    # Get all element IDs in the model
    element_ids = cw.get_all_element_ids()
    print(f"Found {len(element_ids)} elements in the model.\n")
    for eid in element_ids:
        print(f"Element ID: {eid}")
        std_attrs, user_attrs = get_all_attributes(eid)
        print("  Standard Attributes:")
        for key, value in std_attrs.items():
            print(f"    {key}: {value}")
        print("  User-defined Attributes:")
        for key, value in user_attrs.items():
            print(f"    {key}: {value}")
        print("-"*40)

if __name__ == "__main__":
    main()
