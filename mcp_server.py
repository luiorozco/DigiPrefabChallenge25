# cadworkmcp/src/cadworkmcp/server.py
import os
import socket
import json
import asyncio
import logging
from dataclasses import dataclass
from contextlib import asynccontextmanager
from typing import AsyncIterator, Dict, Any, List, Optional
from mcp.server.fastmcp import FastMCP, Context, Image
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configure logging
logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("CadworkMCPServer")

DEFAULT_CADWORK_PORT = 53002
SOCKET_TIMEOUT = 30.0  # Increased timeout for potentially longer Cadwork operations

@dataclass
class CadworkConnection:
    host: str
    port: int

    def send_command(self, operation: str, args: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Open a new socket, send a command, receive the response, and close the socket."""
        sock = None
        command = {
            "operation": operation,
            "args": args or {}
        }
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(SOCKET_TIMEOUT)
            sock.connect((self.host, self.port))
            logger.info(f"[Per-call] Connected to Cadwork plug-in at {self.host}:{self.port}")
            command_bytes = json.dumps(command).encode('utf-8')
            sock.sendall(command_bytes)
            logger.info(f"[Per-call] Command sent ({len(command_bytes)} bytes), waiting for response...")
            # Receive response (reuse the chunked receive logic)
            chunks = []
            while True:
                chunk = sock.recv(8192)
                if not chunk:
                    break
                chunks.append(chunk)
                try:
                    data = b''.join(chunks)
                    json.loads(data.decode('utf-8'))
                    break
                except json.JSONDecodeError:
                    continue
            if not chunks:
                raise ConnectionAbortedError("No data received from Cadwork plug-in")
            data = b''.join(chunks)
            response = json.loads(data.decode('utf-8'))
            logger.info(f"[Per-call] Response parsed, status: {response.get('status', 'unknown')}")
            if response.get("status") == "error":
                error_message = response.get("message", "Unknown error from Cadwork plug-in")
                logger.error(f"Cadwork plug-in error: {error_message}")
                # Do not raise generic Exception here, let the caller handle the error status
                # raise Exception(error_message)
            return response
        except socket.timeout:
            logger.error("[Per-call] Socket timeout while waiting for response from Cadwork plug-in")
            raise TimeoutError("Timeout waiting for Cadwork plug-in response - check if the plug-in is running and responsive.")
        except (ConnectionError, BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
            logger.error(f"[Per-call] Socket connection error ({type(e).__name__}) with Cadwork plug-in: {e}", exc_info=True)
            raise ConnectionError(f"Connection to Cadwork plug-in lost: {e}")
        except json.JSONDecodeError as e:
            logger.error(f"[Per-call] Invalid JSON response from Cadwork plug-in: {e}", exc_info=True)
            if 'data' in locals() and data:
                logger.error(f"Raw response (first 500 bytes): {data[:500]}")
            raise ValueError(f"Invalid response format from Cadwork plug-in: {str(e)}")
        except Exception as e:
            logger.error(f"[Per-call] Unexpected error ({type(e).__name__}) communicating with Cadwork plug-in: {e}", exc_info=True)
            raise RuntimeError(f"Communication error with Cadwork plug-in: {e}")
        finally:
            if sock:
                try:
                    sock.close()
                    logger.info("[Per-call] Socket closed.")
                except Exception:
                    pass

# Global connection instance (stateless)
_cadwork_connection: Optional[CadworkConnection] = None

def get_cadwork_connection() -> CadworkConnection:
    """Always return a CadworkConnection instance (stateless)."""
    if _cadwork_connection is None:
        raise ConnectionError("Cadwork connection not configured. Ensure server_lifespan ran.")
    return _cadwork_connection

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    global _cadwork_connection
    host = "127.0.0.1"
    port = int(os.environ.get("CW_PORT", DEFAULT_CADWORK_PORT))
    logger.info(f"CadworkMCP server starting up. (Per-call connection mode) Plug-in at {host}:{port}...")
    _cadwork_connection = CadworkConnection(host=host, port=port)
    # Optionally, do a handshake test here if you want, but don't keep the socket open
    handshake_ok = False
    try:
        # Try handshake
        try:
            handshake_response = _cadwork_connection.send_command("ping")
            if handshake_response.get("status") == "ok":
                logger.info(f"Handshake successful! Plug-in responded: {handshake_response.get('message', '(no message)')}")
                handshake_ok = True
            else:
                logger.warning(f"Handshake failed: Plug-in responded with status '{handshake_response.get('status')}' and message '{handshake_response.get('message', '(no message)')}'")
        except Exception as hs_err:
            logger.warning(f"Handshake failed: {hs_err}")
    except Exception as e:
        logger.error(f"Error during initial handshake attempt to Cadwork plug-in: {str(e)}")
    yield {"cadwork_handshake_ok": handshake_ok}
    logger.info("CadworkMCP server shutting down...")
    _cadwork_connection = None
    logger.info("Cadwork plug-in connection closed.")


# Create the MCP server instance
mcp = FastMCP(
    "CadworkMCP",
    version="0.1.1", # Updated version
    description="Integrates with a running Cadwork instance via its Python API plug-in.",
    lifespan=server_lifespan
)

# --- Placeholder for Resources ---
# @mcp.resource(...)
# async def get_active_document(...): ...

# --- Tools ---
@mcp.tool(
    name="get_cadwork_version_info",
    description="Retrieves detailed version information from the connected Cadwork application and the MCP bridge plug-in. Returns a dictionary containing keys like 'cw_version' and 'plugin_version' on success."
)
async def get_cadwork_version_info() -> Dict[str, Any]:
    """Attempts to get version info from the Cadwork socket plug-in."""
    logger.info("Tool 'get_cadwork_version_info' called.")
    response = {"status": "error", "message": "Unknown error"}
    try:
        connection = get_cadwork_connection() # Raises ConnectionError if not connected
        plugin_response = connection.send_command("get_version_info", {})

        # Check the status from the plugin_response itself
        if plugin_response.get("status") == "ok":
            logger.info(f"Received version info from plug-in: {plugin_response}")
        else:
            # The plugin reported an error
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for get_version_info: {error_msg}")
        # Always return the raw response from the bridge
        response = plugin_response

    except ConnectionError as e:
        logger.error(f"Connection error in get_cadwork_version_info: {e}")
        response["message"] = f"Failed to connect to Cadwork plug-in: {e}"
    except TimeoutError as e:
         logger.error(f"Timeout error in get_cadwork_version_info: {e}")
         response["message"] = f"Timeout communicating with Cadwork plug-in: {e}"
    except Exception as e:
        # Catch other potential errors from send_command or get_connection
        logger.error(f"Unexpected error in get_cadwork_version_info: {e}", exc_info=True)
        response["message"] = f"An unexpected server error occurred: {e}"

    return response

@mcp.tool(
    name="create_beam",
    description="Creates a standard rectangular beam element in the active Cadwork 3D model. Requires start point `p1` ([x,y,z]), end point `p2` ([x,y,z]), `width`, and `height`. An optional orientation point `p3` ([x,y,z]) can be provided; if omitted, a default orientation (vertical Z axis relative to p1) is used. Returns a dictionary containing the new element's ID (e.g., `{'id': 123}`) on success or an error message."
)
async def create_beam(
    p1: list,  # [x, y, z]
    p2: list,  # [x, y, z]
    width: float,
    height: float,
    p3: Optional[list] = None  # Optional [x, y, z], allow None explicitly
) -> dict:
    """Creates a beam in Cadwork via the socket plug-in."""
    # Initial log
    logger.info(f"Tool 'create_beam' called with p1={p1}, p2={p2}, width={width}, height={height}, p3={p3}")
    response = {"status": "error", "message": "Unknown error"}

    try:
        # --- Input Validation ---
        if not isinstance(p1, (list, tuple)) or len(p1) != 3 or not all(isinstance(n, (int, float)) for n in p1):
            raise ValueError("p1 must be a list or tuple of 3 numbers [x, y, z]")
        if not isinstance(p2, (list, tuple)) or len(p2) != 3 or not all(isinstance(n, (int, float)) for n in p2):
            raise ValueError("p2 must be a list or tuple of 3 numbers [x, y, z]")
        if p3 is not None and (not isinstance(p3, (list, tuple)) or len(p3) != 3 or not all(isinstance(n, (int, float)) for n in p3)):
            raise ValueError("p3, if provided, must be a list or tuple of 3 numbers [x, y, z]")
        if not isinstance(width, (int, float)) or width <= 0:
             raise ValueError("width must be a positive number")
        if not isinstance(height, (int, float)) or height <= 0:
             raise ValueError("height must be a positive number")
        # --- End Input Validation ---

        connection = get_cadwork_connection()  # Raises ConnectionError if not connected

        # Prepare arguments, ensuring p1/p2/p3 are lists of floats
        args = {
            "p1": [float(c) for c in p1],
            "p2": [float(c) for c in p2],
            "width": float(width),
            "height": float(height)
        }
        # Only include p3 if it was provided
        if p3 is not None:
            args["p3"] = [float(c) for c in p3]

        # Log arguments just before sending
        logger.info(f"Attempting to send 'create_beam' command with args: {args}")

        plugin_response = connection.send_command("create_beam", args)

        # Check response status
        if plugin_response.get("status") == "ok":
            logger.info(f"Beam created successfully: {plugin_response}")
        else:
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for create_beam: {error_msg}")
        # Return the raw response from the bridge
        response = plugin_response

    except ValueError as ve: # Catch specific validation errors
        logger.error(f"Input validation error in create_beam: {ve}")
        response["message"] = str(ve) # Return validation error message
    except ConnectionError as e:
        logger.error(f"Connection error in create_beam: {e}")
        response["message"] = f"Failed to connect to Cadwork plug-in: {e}"
    except TimeoutError as e:
        logger.error(f"Timeout error in create_beam: {e}")
        response["message"] = f"Timeout communicating with Cadwork plug-in: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in create_beam: {e}", exc_info=True)
        response["message"] = f"An unexpected server error occurred: {e}"

    return response

@mcp.tool(
    name="get_element_info",
    description="Retrieves detailed geometric information (points p1, p2, p3 and vectors x, y, z) and common attributes (like material and group) for a specific Cadwork element identified by its integer `element_id`. Returns a dictionary containing the element's ID, a 'geometry' sub-dictionary, and an 'attributes' sub-dictionary."
)
async def get_element_info(element_id: int) -> dict:
    """Retrieves geometric and attribute information for a given element ID via the socket plug-in."""
    logger.info(f"Tool 'get_element_info' called with element_id={element_id}")
    response = {"status": "error", "message": "Unknown error"}

    try:
        # --- Input Validation ---
        if not isinstance(element_id, int) or element_id < 0:
             raise ValueError("element_id must be a non-negative integer")
        # --- End Input Validation ---

        connection = get_cadwork_connection() # Raises ConnectionError if not connected

        args = {"element_id": element_id}

        # Log arguments just before sending
        logger.info(f"Attempting to send 'get_element_info' command with args: {args}")

        plugin_response = connection.send_command("get_element_info", args)

        # Check response status
        if plugin_response.get("status") == "ok":
            logger.info(f"Element info retrieved successfully: {plugin_response.get('info')}")
        else:
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for get_element_info: {error_msg}")
        # Return the raw response from the bridge
        response = plugin_response

    except ValueError as ve: # Catch specific validation errors
        logger.error(f"Input validation error in get_element_info: {ve}")
        response["message"] = str(ve) # Return validation error message
    except ConnectionError as e:
        logger.error(f"Connection error in get_element_info: {e}")
        response["message"] = f"Failed to connect to Cadwork plug-in: {e}"
    except TimeoutError as e:
        logger.error(f"Timeout error in get_element_info: {e}")
        response["message"] = f"Timeout communicating with Cadwork plug-in: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in get_element_info: {e}", exc_info=True)
        response["message"] = f"An unexpected server error occurred: {e}"

    return response

@mcp.tool(
    name="get_active_element_ids",
    description="Retrieves a list of integer IDs for all elements currently active (selected) in the Cadwork 3D user interface. Returns a dictionary containing a list under the key 'element_ids' (e.g., `{'element_ids': [101, 105, 210]}`) on success, which will be empty if no elements are active."
)
async def get_active_element_ids() -> dict:
    """Retrieves a list of active element IDs from the connected Cadwork plug-in."""
    logger.info("Tool 'get_active_element_ids' called.")
    response = {"status": "error", "message": "Unknown error"}

    try:
        connection = get_cadwork_connection() # Raises ConnectionError if not connected

        # Log arguments just before sending
        logger.info("Attempting to send 'get_active_element_ids' command.")

        plugin_response = connection.send_command("get_active_element_ids", {})

        # Check response status
        if plugin_response.get("status") == "ok":
            # Ensure the key matches what the bridge sends on success
            if "element_ids" in plugin_response:
                logger.info(f"Active element IDs retrieved successfully: {plugin_response.get('element_ids')}")
            else:
                logger.error(f"Plug-in success response for get_active_element_ids missing 'element_ids' key: {plugin_response}")
                # Modify response if key is missing but status was ok
                response["status"] = "error"
                response["message"] = "Plug-in response missing 'element_ids' key."
                return response # Return early with error status
        else:
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for get_active_element_ids: {error_msg}")
        # Return the raw response from the bridge
        response = plugin_response

    except ConnectionError as e:
        logger.error(f"Connection error in get_active_element_ids: {e}")
        response["message"] = f"Failed to connect to Cadwork plug-in: {e}"
    except TimeoutError as e:
        logger.error(f"Timeout error in get_active_element_ids: {e}")
        response["message"] = f"Timeout communicating with Cadwork plug-in: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in get_active_element_ids: {e}", exc_info=True)
        response["message"] = f"An unexpected server error occurred: {e}"

    return response


@mcp.tool(
    name="get_standard_attributes",
    description=(
        "Retrieves common standard attributes for a list of specified element IDs. "
        "Standard attributes include: name, group, subgroup, material name, and comment. "
        "This is useful for gathering basic classification and identification data about elements. "
        "Example Use Case: Get the name, group, and material for elements [101, 105] to display in a report. "
        "Returns a dictionary where keys are the integer element IDs and values are dictionaries of the retrieved attributes. "
        "If an attribute cannot be retrieved for a specific element (e.g., not set or error), its value might be null or contain an error marker."
    )
)
async def get_standard_attributes(element_ids: List[int]) -> dict:
    """Retrieves standard attributes for a list of element IDs via the socket plug-in."""
    logger.info(f"Tool 'get_standard_attributes' called with {len(element_ids)} element IDs.")
    response = {"status": "error", "message": "Unknown error"}

    try:
        # --- Input Validation ---
        if not isinstance(element_ids, list):
             raise ValueError("element_ids must be a list.")
        if not all(isinstance(eid, int) and eid >= 0 for eid in element_ids):
             raise ValueError("All element_ids must be non-negative integers.")
        # --- End Input Validation ---

        if not element_ids:
             logger.info("Received empty element_ids list. Returning empty success response.")
             return {"status": "ok", "attributes_by_id": {}}

        connection = get_cadwork_connection()
        args = {"element_ids": element_ids}
        logger.info(f"Attempting to send 'get_standard_attributes' command with args: {args}")
        plugin_response = connection.send_command("get_standard_attributes", args)

        # Log success or error based on bridge response
        if plugin_response.get("status") == "ok":
            count = len(plugin_response.get("attributes_by_id", {}))
            logger.info(f"Standard attributes retrieved successfully for {count} elements.")
        else:
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for get_standard_attributes: {error_msg}")
        response = plugin_response # Return raw bridge response

    except ValueError as ve:
        logger.error(f"Input validation error in get_standard_attributes: {ve}")
        response["message"] = str(ve)
    except ConnectionError as e:
        logger.error(f"Connection error in get_standard_attributes: {e}")
        response["message"] = f"Failed to connect to Cadwork plug-in: {e}"
    except TimeoutError as e:
        logger.error(f"Timeout error in get_standard_attributes: {e}")
        response["message"] = f"Timeout communicating with Cadwork plug-in: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in get_standard_attributes: {e}", exc_info=True)
        response["message"] = f"An unexpected server error occurred: {e}"

    return response


@mcp.tool(
    name="get_user_attributes",
    description=(
        "Retrieves the values of specific user-defined attributes (identified by their integer number) for a list of specified element IDs. "
        "User attributes store custom data associated with elements (e.g., cost codes, phase information, manufacturing status). "
        "You must provide both the element IDs and the list of attribute numbers you want to retrieve. "
        "Example Use Case: For elements [201, 202], get the values of user attributes number 10 ('CostCode') and 15 ('Phase'). "
        "Returns a dictionary mapping element IDs to dictionaries, where the inner dictionary maps attribute numbers to their values. "
        "Values can be strings, numbers, or potentially null/error markers if not set or retrieval fails."
    )
)
async def get_user_attributes(element_ids: List[int], attribute_numbers: List[int]) -> dict:
    """Retrieves specific user attributes for a list of elements via the socket plug-in."""
    logger.info(f"Tool 'get_user_attributes' called for {len(element_ids)} elements and attributes {attribute_numbers}.")
    response = {"status": "error", "message": "Unknown error"}

    try:
        # --- Input Validation ---
        if not isinstance(element_ids, list):
             raise ValueError("element_ids must be a list.")
        if not all(isinstance(eid, int) and eid >= 0 for eid in element_ids):
             raise ValueError("All element_ids must be non-negative integers.")
        if not isinstance(attribute_numbers, list):
             raise ValueError("attribute_numbers must be a list.")
        if not all(isinstance(num, int) and num > 0 for num in attribute_numbers):
             raise ValueError("All attribute_numbers must be positive integers.")
        # --- End Input Validation ---

        if not element_ids or not attribute_numbers:
             logger.info("Received empty element_ids or attribute_numbers list. Returning empty success response.")
             # Return structure should still match success case for consistency
             return {"status": "ok", "user_attributes_by_id": {}}

        connection = get_cadwork_connection()
        args = {"element_ids": element_ids, "attribute_numbers": attribute_numbers}
        logger.info(f"Attempting to send 'get_user_attributes' command with args: {args}")
        plugin_response = connection.send_command("get_user_attributes", args)

        # Log success or error based on bridge response
        if plugin_response.get("status") == "ok":
            count = len(plugin_response.get("user_attributes_by_id", {}))
            logger.info(f"User attributes retrieved successfully for {count} elements.")
        else:
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for get_user_attributes: {error_msg}")
        response = plugin_response # Return raw bridge response

    except ValueError as ve:
        logger.error(f"Input validation error in get_user_attributes: {ve}")
        response["message"] = str(ve)
    except ConnectionError as e:
        logger.error(f"Connection error in get_user_attributes: {e}")
        response["message"] = f"Failed to connect to Cadwork plug-in: {e}"
    except TimeoutError as e:
        logger.error(f"Timeout error in get_user_attributes: {e}")
        response["message"] = f"Timeout communicating with Cadwork plug-in: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in get_user_attributes: {e}", exc_info=True)
        response["message"] = f"An unexpected server error occurred: {e}"

    return response


@mcp.tool(
    name="list_defined_user_attributes",
    description=(
        "Retrieves a list of all user-defined attribute numbers that have a name configured in the current Cadwork environment. "
        "This helps identify which user attribute numbers (e.g., 1-100) are actually in use and what they represent (e.g., 10='CostCode'). "
        "This tool does not require element IDs as input. "
        "Example Use Case: Find out which user attributes are available for filtering or querying before calling 'get_user_attributes'. "
        "Returns a dictionary mapping the integer user attribute numbers to their configured string names."
    )
)
async def list_defined_user_attributes() -> dict:
    """Retrieves the names of defined user attributes via the socket plug-in."""
    logger.info("Tool 'list_defined_user_attributes' called.")
    response = {"status": "error", "message": "Unknown error"}

    try:
        connection = get_cadwork_connection()
        logger.info("Attempting to send 'list_defined_user_attributes' command.")
        plugin_response = connection.send_command("list_defined_user_attributes", {})

        # Log success or error based on bridge response
        if plugin_response.get("status") == "ok":
            count = len(plugin_response.get("defined_attributes", {}))
            logger.info(f"Defined user attributes listed successfully ({count} found).")
        else:
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for list_defined_user_attributes: {error_msg}")
        response = plugin_response # Return raw bridge response

    except ConnectionError as e:
        logger.error(f"Connection error in list_defined_user_attributes: {e}")
        response["message"] = f"Failed to connect to Cadwork plug-in: {e}"
    except TimeoutError as e:
        logger.error(f"Timeout error in list_defined_user_attributes: {e}")
        response["message"] = f"Timeout communicating with Cadwork plug-in: {e}"
    except Exception as e:
        logger.error(f"Unexpected error in list_defined_user_attributes: {e}", exc_info=True)
        response["message"] = f"An unexpected server error occurred: {e}"

    return response


if __name__ == "__main__":
    # When running with stdio, mcp.run often handles the event loop.
    # Call it directly without async def main() or asyncio.run().
    logger.info("Starting CadworkMCP server with stdio transport...")
    try:
        mcp.run(transport='stdio')
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
    except Exception as e:
        logger.error(f"Server failed to run: {e}", exc_info=True)
        # Potentially exit with error code
        import sys
        sys.exit(1) 