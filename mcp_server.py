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
                raise Exception(error_message)
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
    version="0.1.0", # Start with an initial version
    description="Integrates with a running Cadwork instance via its Python API plug-in.",
    lifespan=server_lifespan
)

# --- Placeholder for Resources ---
# @mcp.resource(...)
# async def get_active_document(...): ...

# --- Placeholder for Tools ---
@mcp.tool(
    name="get_cadwork_version_info",
    description="Retrieves version information from the connected Cadwork plug-in."
)
async def get_cadwork_version_info() -> Dict[str, Any]:
    """Attempts to get version info from the Cadwork socket plug-in."""
    logger.info("Tool 'get_cadwork_version_info' called.")
    response = {"status": "error", "message": "Unknown error"}
    try:
        connection = get_cadwork_connection() # Raises ConnectionError if not connected
        # This assumes the inner Cadwork plug-in handles an operation named "get_version_info"
        # and returns a dict with keys like 'cw_version', 'plugin_version' upon success.
        plugin_response = connection.send_command("get_version_info", {})

        # Check the status from the plugin_response itself
        if plugin_response.get("status") == "ok":
            logger.info(f"Received version info from plug-in: {plugin_response}")
            # Relay the successful response structure
            response = plugin_response
        else:
            # The plugin reported an error
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for get_version_info: {error_msg}")
            response["message"] = error_msg

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
    description="Creates a beam in Cadwork with the specified parameters. Args: p1 (start point), p2 (end point), width, height, and optionally p3 (orientation point). Returns the new element ID or error message."
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

        # Explicitly set p3 if not provided
        if p3 is not None:
            args["p3"] = [float(c) for c in p3]
        else:
            # Calculate default p3 (point vertically above p1)
            args["p3"] = [args["p1"][0], args["p1"][1], args["p1"][2] + 1.0]
            logger.info(f"Calculated default p3: {args['p3']}")


        # Log arguments just before sending
        logger.info(f"Attempting to send 'create_beam' command with args: {args}")

        plugin_response = connection.send_command("create_beam", args)

        # Check response status
        if plugin_response.get("status") == "ok":
            logger.info(f"Beam created successfully: {plugin_response}")
            response = plugin_response
        else:
            error_msg = plugin_response.get("message", "Plug-in returned an error status.")
            logger.error(f"Plug-in reported error for create_beam: {error_msg}")
            response["message"] = error_msg

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