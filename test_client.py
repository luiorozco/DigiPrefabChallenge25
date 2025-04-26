import socket
import json


def test_create_beam(host="127.0.0.1", port=53002):
    """Test the create_beam operation on the MCP server."""
    cmd = {
        "operation": "create_beam",
        "args": {
            "p1": [0, 0, 0],
            "p2": [4000, 0, 0],
            "width": 60,
            "height": 160
            # p3 optional – plugin adds [0,0,1]
        }
    }
    try:
        with socket.create_connection((host, port)) as s:
            s.sendall(json.dumps(cmd).encode())
            reply = json.loads(s.recv(8192).decode())
            print("create_beam reply:", reply)
    except Exception as e:
        print(f"Error in create_beam test: {e}")


def test_get_version_info(host="127.0.0.1", port=53002):
    """Test the get_version_info operation on the MCP server."""
    data = {"operation": "get_version_info"}
    try:
        with socket.create_connection((host, port)) as s:
            s.sendall(json.dumps(data).encode("utf-8"))
            response = s.recv(4096)
            print("get_version_info reply:", response.decode("utf-8"))
    except Exception as e:
        print(f"Error in get_version_info test: {e}")


def main():
    print("Select test to run:")
    print("1. create_beam")
    print("2. get_version_info")
    print("3. both")
    choice = input("Enter choice (1/2/3): ").strip()
    if choice == "1":
        test_create_beam()
    elif choice == "2":
        test_get_version_info()
    elif choice == "3":
        test_create_beam()
        test_get_version_info()
    else:
        print("Invalid choice.")


if __name__ == "__main__":
    main() 