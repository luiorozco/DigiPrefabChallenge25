import socket, json

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

with socket.create_connection(("127.0.0.1", 53001)) as s:
    s.sendall(json.dumps(cmd).encode())
    reply = json.loads(s.recv(8192).decode())
    print(reply)
