"""
cadwork_mcp.py  – minimal MCP bridge (v3, proper point_3d conversion, added logging)
"""

import socket, json, threading, traceback
import utility_controller as uc
import element_controller as ec
import cadwork             
HOST, PORT = "127.0.0.1", 53002          # keep your chosen port

# ───────── helpers ────────────────────────────────────────────────────────────
def to_pt(v):
    """Convert [x,y,z] list/tuple -> cadwork.point_3d"""
    # Add basic type/length checking for robustness
    if not isinstance(v, (list, tuple)) or len(v) != 3:
        raise ValueError(f"Invalid point format: {v}. Expected list/tuple of 3 numbers.")
    try:
        return cadwork.point_3d(float(v[0]), float(v[1]), float(v[2]))
    except (ValueError, TypeError) as e:
        raise ValueError(f"Invalid coordinate in point {v}: {e}")


# ───────── dispatcher ─────────────────────────────────────────────────────────
def handle(msg: dict) -> dict:
    op = msg.get("operation")
    print(f"▶ Dispatcher received operation: {op}") # Log received operation

    if not isinstance(msg, dict):
        print("Error: Invalid message format, expected JSON object")
        return {"status": "error", "msg": "Invalid message format, expected JSON object"}

    args = msg.get("args", {}) # Get args, default to empty dict if missing

    if not isinstance(args, dict):
         print("Error: Invalid 'args' format, expected JSON object")
         return {"status": "error", "msg": "Invalid 'args' format, expected JSON object"}

    if op == "get_version_info": # Example handler for the other tool
        try:
            # --- Attempt to get Cadwork version ---
            # NOTE: uc.get_cadwork_version_info() might not exist or might return
            # something different. Adapt based on available uc functions.
            # Trying a known function first:
            cw_version_str = str(uc.get_cadwork_version()) # get_cadwork_version() returns major version int

            # If you have a more detailed info function, use it:
            # version_info_dict = uc.get_cadwork_version_info() # Example if this exists
            # cw_version_str = version_info_dict.get('version', 'unknown') # Example

            print(f"Successfully retrieved Cadwork version: {cw_version_str}")
            return {"status": "ok", "cw_version": cw_version_str, "plugin_version": "0.1.0_logged"} # Added suffix
        except AttributeError:
             print("Error: utility_controller has no 'get_cadwork_version' or expected 'get_cadwork_version_info'")
             return {"status": "error", "msg": "Failed to get version info: Function not found in utility_controller"}
        except Exception as e:
            print(f"Error in get_version_info: {e}")
            traceback.print_exc() # Print traceback for unexpected errors here
            return {"status": "error", "msg": f"Failed to get version info: {e}"}

    if op == "get_model_name":
        try:
            model_name = uc.get_3d_file_name()
            print(f"Retrieved model name: {model_name}")
            return {"status": "ok", "name": model_name or "(unsaved model)"}
        except Exception as e:
            print(f"Error in get_model_name: {e}")
            traceback.print_exc()
            return {"status": "error", "msg": f"Failed to get model name: {e}"}

    if op == "create_beam":
        try:
            print(f"Handling 'create_beam' with args: {args}") # Log args received by handler
            # Input validation within the handler
            required_args = ["p1", "p2", "width", "height"]
            if not all(key in args for key in required_args):
                 missing = [key for key in required_args if key not in args]
                 err_msg = f"Missing required arguments for create_beam: {missing}"
                 print(f"Error: {err_msg}")
                 raise ValueError(err_msg)

            p1 = to_pt(args["p1"])
            p2 = to_pt(args["p2"])
            # Use args.get for optional p3, provide default if not present *or* if None
            p3_raw = args.get("p3")
            if p3_raw is None:
                # Default p3 is point vertically above p1 (positive Z)
                p3 = cadwork.point_3d(p1.x, p1.y, p1.z + 1.0) # Use point_3d directly
                print(f"Using default p3 (vertical): {p3.x}, {p3.y}, {p3.z}")
            else:
                p3 = to_pt(p3_raw)
                print(f"Using provided p3: {p3_raw}")

            width = float(args["width"])
            height = float(args["height"])

            if width <= 0 or height <= 0:
                 err_msg = f"Width ({width}) and height ({height}) must be positive numbers."
                 print(f"Error: {err_msg}")
                 raise ValueError(err_msg)

            # Log the final points being used - accessing members ensures they are valid point_3d
            print(f"Calling ec.create_rectangular_beam_points with w={width}, h={height}, "
                  f"p1=({p1.x},{p1.y},{p1.z}), p2=({p2.x},{p2.y},{p2.z}), p3=({p3.x},{p3.y},{p3.z})")

            beam_id = ec.create_rectangular_beam_points(width, height, p1, p2, p3)

            # Check if beam_id seems valid (often > 0 for success)
            if isinstance(beam_id, int) and beam_id >= 0: # Adjust if Cadwork uses different success indicators
                print(f"Beam created successfully, ID: {beam_id}")
                return {"status": "ok", "id": beam_id}
            else:
                # Handle cases where Cadwork might return 0 or negative on failure without exception
                err_msg = f"ec.create_rectangular_beam_points returned unexpected value: {beam_id}"
                print(f"Error: {err_msg}")
                return {"status": "error", "msg": err_msg, "returned_id": beam_id}

        except (ValueError, TypeError) as e: # Catch specific conversion/validation errors
             print(f"Input Error in create_beam: {e}")
             # traceback.print_exc() # Keep commented unless needed
             return {"status": "error", "msg": f"Invalid input for create_beam: {e}"}
        except Exception as e: # Catch other Cadwork API errors
            print(f"Cadwork API Error in create_beam: {e}")
            traceback.print_exc() # Print full traceback for unexpected errors
            # Try to provide a more specific error message if possible
            return {"status": "error", "msg": f"Cadwork API error: {type(e).__name__} - {e}"}

    # Fallback for unknown operations
    print(f"Unknown operation received: {op}")
    return {"status": "error", "msg": f"unknown operation '{op}'"}


# ───────── socket thread ──────────────────────────────────────────────────────
def socket_server():
    # Ensure HOST is a string and PORT is an int
    host_str = str(HOST)
    port_int = int(PORT)
    server_address = (host_str, port_int)
    srv = None # Define srv before try block

    try:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Option to allow reusing the address quickly after script restart
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        print(f"Attempting to bind to {server_address}...")
        srv.bind(server_address)
        print(f"Socket bound successfully.")
        srv.listen(1) # Listen for only one connection at a time
        print(f"✓ cadwork_mcp listening on {host_str}:{port_int}")
    except Exception as e:
        print(f"!!! Server socket setup failed on {server_address}: {e} !!!")
        traceback.print_exc()
        if srv:
             srv.close() # Clean up socket if partially created
        return # Stop the thread if setup fails

    # --- Main Server Loop ---
    while True:
        conn = None # Ensure conn is defined for finally block
        addr = None
        try:
            print(f"\n[{threading.current_thread().name}] Waiting for incoming connection...") # Log thread name
            conn, addr = srv.accept() # Blocking call
            print(f"[{threading.current_thread().name}] Connection accepted from: {addr}") # Log thread name

            # Set timeout for the accepted connection's operations
            conn.settimeout(20.0) # e.g., 20 seconds timeout for recv/send

            print(f"[{threading.current_thread().name}] Attempting to receive data...")
            # More robust receive loop: read untildelimiter or timeout/error
            raw_chunks = []
            bytes_received = 0
            raw = b'' # Initialize raw
            try:
                while True:
                    # print(f"[{threading.current_thread().name}] Calling conn.recv(4096)...") # Verbose log
                    chunk = conn.recv(4096) # Read in chunks
                    if not chunk:
                        print(f"[{threading.current_thread().name}] Connection closed by client ({addr}) during receive.")
                        break # Client closed connection gracefully
                    # print(f"[{threading.current_thread().name}] Received chunk of size {len(chunk)}.") # Verbose log
                    raw_chunks.append(chunk)
                    bytes_received += len(chunk)

                    # *** Basic JSON Detection Logic ***
                    # Look for balanced braces. This is imperfect but better than nothing.
                    # A better protocol would use length prefixing or a clear delimiter.
                    temp_data = b''.join(raw_chunks).strip()
                    if temp_data.startswith(b'{') and temp_data.endswith(b'}'):
                         try:
                              # Try to parse; if it works, assume we got a full JSON object
                              json.loads(temp_data.decode('utf-8'))
                              print(f"[{threading.current_thread().name}] Received data looks like complete JSON ({bytes_received} bytes).")
                              break
                         except (json.JSONDecodeError, UnicodeDecodeError):
                              # Incomplete JSON or bad encoding, keep receiving
                              # print(f"[{threading.current_thread().name}] Data received but not valid JSON yet, continuing...") # Verbose
                              pass

                    if bytes_received > 65536: # Safety break for large messages
                         print(f"[{threading.current_thread().name}] Warning: Received > 65536 bytes from {addr}, potential issue or large message.")
                         # Decide whether to break or continue based on your expected message sizes
                         break # Breaking for safety here

            except socket.timeout:
                print(f"[{threading.current_thread().name}] Socket timeout ({conn.gettimeout()}s) while receiving data from {addr}. Received {bytes_received} bytes so far.")
                # If we received *some* data before timeout, try processing it
                if not raw_chunks:
                     print(f"[{threading.current_thread().name}] No data received before timeout.")
                     continue # Go back to waiting for connection
            except ConnectionResetError:
                 print(f"[{threading.current_thread().name}] Connection reset by peer ({addr}) during receive.")
                 continue # Go back to waiting for connection
            except Exception as recv_err:
                 print(f"[{threading.current_thread().name}] Error during recv from {addr}: {recv_err}")
                 traceback.print_exc()
                 continue # Go back to waiting for connection

            # --- Process received data ---
            if not raw_chunks:
                print(f"[{threading.current_thread().name}] No data received or connection closed early by {addr}.")
                continue # Go back to waiting for connection

            raw = b''.join(raw_chunks)
            print(f"[{threading.current_thread().name}] Received total {len(raw)} bytes from {addr}.")
            if len(raw) > 0:
                # Log only first few hundred bytes for readability
                log_snippet = raw[:500].decode('utf-8', errors='replace') # Decode safely for logging
                print(f"[{threading.current_thread().name}] Raw data received (first 500 bytes): {log_snippet}")
                decoded_data = None
                response = None # Ensure response is defined
                try:
                    print(f"[{threading.current_thread().name}] Attempting to decode UTF-8...")
                    decoded_data = raw.decode('utf-8')
                    # print(f"[{threading.current_thread().name}] Decoded data: {decoded_data}") # Verbose log
                    print(f"[{threading.current_thread().name}] Attempting to parse JSON...")
                    parsed_msg = json.loads(decoded_data)
                    print(f"[{threading.current_thread().name}] JSON parsed successfully: {parsed_msg}")
                    print(f"[{threading.current_thread().name}] Dispatching to handle function...")
                    # --- Call the actual handler ---
                    response = handle(parsed_msg)
                    # --------------------------------
                    print(f"[{threading.current_thread().name}] Handle function returned: {response}")
                    if response is None:
                         print(f"[{threading.current_thread().name}] !!! Warning: handle function returned None for op {parsed_msg.get('operation')} !!!")
                         response = {"status": "error", "msg": "Handler function returned None"}

                    response_bytes = json.dumps(response).encode('utf-8')
                    response_snippet = response_bytes[:500].decode('utf-8', errors='replace')
                    print(f"[{threading.current_thread().name}] Sending response ({len(response_bytes)} bytes): {response_snippet}...")
                    conn.sendall(response_bytes)
                    print(f"[{threading.current_thread().name}] Response sent to {addr}.")

                except UnicodeDecodeError as ude:
                    print(f"[{threading.current_thread().name}] !!! Unicode Decode Error: {ude} !!!")
                    print(f"[{threading.current_thread().name}] Problematic raw data (approx location):", raw[max(0, ude.start-20):ude.end+20])
                    response = {"status": "error", "msg": f"Invalid UTF-8 data received: {ude}"}
                except json.JSONDecodeError as jde:
                    print(f"[{threading.current_thread().name}] !!! JSON Decode Error: {jde} !!!")
                    # Log the decoded string if decoding worked, otherwise raw bytes
                    if decoded_data:
                         print(f"[{threading.current_thread().name}] Problematic decoded data: {decoded_data}")
                    else:
                         print(f"[{threading.current_thread().name}] Problematic raw data: {raw}")
                    response = {"status": "error", "msg": f"Invalid JSON format received: {jde}"}
                except Exception as handle_err:
                    print(f"[{threading.current_thread().name}] !!! Error during handle/response phase: {handle_err} !!!")
                    traceback.print_exc()
                    response = {"status": "error", "msg": f"Internal server error: {type(handle_err).__name__} - {handle_err}"}

                # --- Attempt to send error response if needed ---
                if response and response.get("status") == "error":
                    try:
                        print(f"[{threading.current_thread().name}] Attempting to send error response back to {addr}...")
                        error_bytes = json.dumps(response).encode('utf-8')
                        conn.sendall(error_bytes)
                        print(f"[{threading.current_thread().name}] Error response sent.")
                    except Exception as send_err:
                         print(f"[{threading.current_thread().name}] !!! Failed to send error response to {addr}: {send_err} !!!")

            else:
                print(f"[{threading.current_thread().name}] Received zero bytes after loop from {addr}, closing connection.")

        except socket.timeout:
            # This timeout is for the conn.accept() call if srv.settimeout() was used (it isn't here)
            # Or potentially relates to the conn.settimeout() if error occurs before recv loop
            print(f"[{threading.current_thread().name}] Socket timeout occurred for {addr}. (Timeout: {conn.gettimeout() if conn else 'N/A'}s)")
        except ConnectionResetError:
            # This happens if the client disconnects abruptly *after* accept() but before/during send/recv
            print(f"[{threading.current_thread().name}] Connection reset by peer {addr}.")
        except Exception as e:
            # Catch errors during accept or general connection handling loop
            print(f"[{threading.current_thread().name}] Error in connection handling loop (client: {addr}):")
            traceback.print_exc()
        finally:
             if conn:
                 print(f"[{threading.current_thread().name}] Closing connection to {addr}.")
                 try:
                     conn.shutdown(socket.SHUT_RDWR) # Attempt graceful shutdown
                 except OSError:
                      pass # Ignore if already closed
                 except Exception as shut_err:
                      print(f"[{threading.current_thread().name}] Error during socket shutdown for {addr}: {shut_err}")
                 try:
                      conn.close() # Ensure connection is closed
                 except Exception as close_err:
                      print(f"[{threading.current_thread().name}] Error closing socket for {addr}: {close_err}")
             print(f"[{threading.current_thread().name}] Finished handling connection from {addr}.")
             # Loop continues, waiting for next connection


# ───────── main execution ─────────────────────────────────────────────────────
# Global flag to signal shutdown
shutdown_event = threading.Event()

def signal_handler(signum, frame):
    """Handle signals like Ctrl+C"""
    print(f"\nSignal {signum} received, initiating shutdown...")
    shutdown_event.set()
    # Optionally, try to connect to the server socket to unblock accept()
    try:
        # This might fail if the server socket is already closed
        with socket.create_connection((HOST, PORT), timeout=0.1) as sock:
             print("Connected to self to unblock accept()...")
             # Send a dummy message or just close
             sock.close()
    except Exception as e:
        print(f"Could not connect to self to unblock accept(): {e}")

def main():
    global server_thread # Make thread accessible if needed elsewhere

    # --- Check if already running (simple socket bind check) ---
    try:
        # Try to bind to the *actual* port. If it fails, another instance IS likely running.
        test_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        # Crucially, DON'T set SO_REUSEADDR here for the check
        test_sock.bind((HOST, PORT))
        test_sock.close()
        print("Port check successful, no other instance detected.")
        can_start = True
    except OSError as e:
         if "already in use" in str(e).lower() or e.winerror == 10048: # winerror 10048 is WSAEADDRINUSE
              print(f"!!! Port {PORT} is already in use. Is another instance of cadwork_mcp.py running? !!!")
              print("!!! If previous run crashed, you might need to wait or manually free the port. !!!")
              can_start = False
         else:
              print(f"!!! Error checking port {PORT}: {e} !!!")
              traceback.print_exc()
              can_start = False # Safer not to start if check failed unexpectedly
    except Exception as e:
         print(f"!!! Unexpected error during port check: {e} !!!")
         traceback.print_exc()
         can_start = False

    if not can_start:
        print("--- Exiting cadwork_mcp.py due to port conflict or check error ---")
        return # Exit main() if cannot start

    # --- Start Server Thread ---
    print("Starting socket server thread...")
    server_thread = threading.Thread(target=socket_server, name="SocketServerThread", daemon=True)
    server_thread.start()
    print("cadwork_mcp main() finished, server thread running in background.")

    # --- Keep Main Thread Alive (Optional but good for clean shutdown) ---
    # This part allows Ctrl+C to be caught gracefully if running interactively
    # If run purely as a Cadwork plugin without interactive console, it might not be needed
    # import signal
    # signal.signal(signal.SIGINT, signal_handler) # Catch Ctrl+C
    # signal.signal(signal.SIGTERM, signal_handler) # Catch termination signals

    # print("Main thread running. Press Ctrl+C to attempt graceful shutdown.")
    # try:
    #      # Keep main thread alive while server thread runs
    #      while server_thread.is_alive():
    #           server_thread.join(timeout=1.0) # Check every second
    #           if shutdown_event.is_set():
    #                print("Shutdown signal received in main loop.")
    #                break
    # except KeyboardInterrupt:
    #      print("\nCtrl+C detected in main thread.")
    #      shutdown_event.set()

    # print("Main thread exiting.")
    # If server_thread is daemon, it will exit when main thread exits.
    # If not daemon, ensure it stops cleanly here if needed.


if __name__ == "__main__":
    print(f"\n--- Running cadwork_mcp.py ({__name__} namespace) ---")
    main()
    # The print below might appear *before* the server thread fully stops if main exits quickly
    print("--- cadwork_mcp.py script execution context finished ---")
