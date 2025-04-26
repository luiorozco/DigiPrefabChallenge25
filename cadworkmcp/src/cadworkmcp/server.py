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

DEFAULT_CADWORK_PORT = 2000
SOCKET_TIMEOUT = 30.0  # Increased timeout for potentially longer Cadwork operations

@dataclass
class CadworkConnection:
    host: str
    port: int
    sock: Optional[socket.socket] = None

    def connect(self) -> bool:
        """Connect to the Cadwork Python plug-in socket server"""
        if self.sock:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.settimeout(SOCKET_TIMEOUT) # Set timeout for the connection attempt
            self.sock.connect((self.host, self.port))
            logger.info(f"Connected to Cadwork plug-in at {self.host}:{self.port}")
            return True
        except socket.timeout:
            logger.error(f"Timeout connecting to Cadwork plug-in at {self.host}:{self.port}")
            self.sock = None
            return False
        except Exception as e:
            logger.error(f"Failed to connect to Cadwork plug-in: {str(e)}")
            self.sock = None
            return False

    def disconnect(self):
        """Disconnect from the Cadwork plug-in"""
        if self.sock:
            try:
                # Send a 'disconnect' signal if the protocol supports it (optional)
                # self.send_command("disconnect", {}) # Example
                self.sock.close()
                logger.info("Disconnected from Cadwork plug-in.")
            except Exception as e:
                logger.error(f"Error disconnecting from Cadwork plug-in: {str(e)}")
            finally:
                self.sock = None

    def receive_full_response(self, buffer_size=8192) -> bytes:
        """Receive the complete JSON response, potentially in multiple chunks"""
        if not self.sock:
            raise ConnectionError("Socket is not connected for receiving")

        chunks = []
        self.sock.settimeout(SOCKET_TIMEOUT) # Use the defined timeout

        try:
            while True:
                try:
                    chunk = self.sock.recv(buffer_size)
                    if not chunk:
                        if not chunks:
                            raise ConnectionAbortedError("Connection closed by Cadwork plug-in before receiving data")
                        break # Connection closed gracefully after sending data
                    chunks.append(chunk)
                    # Simple check: try to decode after each chunk
                    # More robust: check for balanced braces/brackets if expecting JSON
                    try:
                        data = b''.join(chunks)
                        json.loads(data.decode('utf-8'))
                        logger.info(f"Received complete JSON response ({len(data)} bytes)")
                        return data
                    except json.JSONDecodeError:
                        # Incomplete JSON, continue receiving
                        continue
                except socket.timeout:
                    logger.warning("Socket timeout during chunked receive from Cadwork plug-in.")
                    # If we timed out, maybe we have enough data? Try decoding what we got.
                    if chunks:
                        break
                    else:
                        raise TimeoutError("Socket timeout waiting for initial data from Cadwork plug-in")
                except (ConnectionError, BrokenPipeError, ConnectionResetError) as e:
                    logger.error(f"Socket connection error during receive from Cadwork plug-in: {str(e)}")
                    raise # Re-raise to be handled by the caller

        except Exception as e:
            logger.error(f"Error during receive from Cadwork plug-in: {str(e)}")
            raise

        # If we broke out (timeout with some data or clean close), try decoding
        if chunks:
            data = b''.join(chunks)
            logger.info(f"Returning data after receive completion ({len(data)} bytes)")
            try:
                json.loads(data.decode('utf-8')) # Validate final data
                return data
            except json.JSONDecodeError as e:
                logger.error(f"Incomplete/Invalid JSON received before Cadwork plug-in closed connection or timed out: {e}")
                logger.error(f"Raw data received: {data[:500]}") # Log partial data for debugging
                raise ValueError("Incomplete or invalid JSON response received from Cadwork plug-in")
        else:
            # This case should ideally be caught by earlier checks
            raise ConnectionAbortedError("No data received, connection likely closed prematurely by Cadwork plug-in")


    def send_command(self, operation: str, args: Dict[str, Any] = {}) -> Dict[str, Any]:
        """Send a command to the Cadwork plug-in and return the response"""
        if not self.sock and not self.connect():
            # Log the connection failure reason if connect() failed
            if not self.sock:
                 logger.error("Failed to establish connection to Cadwork plug-in.")
            raise ConnectionError("Not connected to Cadwork plug-in")

        # Ensure socket exists before proceeding (connect might have failed)
        if self.sock is None:
             logger.error("Socket object is None after connection attempt.")
             raise ConnectionError("Socket is None, cannot send command.")

        command = {
            "operation": operation,
            "args": args or {}
        }

        try:
            logger.info(f"Sending command: {operation} with args: {args}")
            command_bytes = json.dumps(command).encode('utf-8')
            self.sock.sendall(command_bytes)
            logger.info(f"Command sent ({len(command_bytes)} bytes), waiting for response...")

            # Receive the response
            response_data = self.receive_full_response()
            logger.info(f"Received {len(response_data)} bytes of data from Cadwork plug-in")

            response = json.loads(response_data.decode('utf-8'))
            logger.info(f"Response parsed, status: {response.get('status', 'unknown')}")

            # Check for application-level errors reported by the plug-in
            if response.get("status") == "error":
                error_message = response.get("message", "Unknown error from Cadwork plug-in")
                logger.error(f"Cadwork plug-in error: {error_message}")
                # Consider raising a custom exception type here
                raise Exception(error_message)

            return response # Return the entire response dict

        except socket.timeout:
            logger.error("Socket timeout while waiting for response from Cadwork plug-in")
            self.disconnect() # Disconnect on timeout
            raise TimeoutError("Timeout waiting for Cadwork plug-in response - check if the plug-in is running and responsive.")
        except (ConnectionError, BrokenPipeError, ConnectionResetError, ConnectionAbortedError) as e:
            logger.error(f"Socket connection error with Cadwork plug-in: {str(e)}")
            self.disconnect() # Disconnect on connection error
            raise ConnectionError(f"Connection to Cadwork plug-in lost: {str(e)}")
        except json.JSONDecodeError as e:
            logger.error(f"Invalid JSON response from Cadwork plug-in: {str(e)}")
            # Log raw response if available
            if 'response_data' in locals() and response_data:
                logger.error(f"Raw response (first 500 bytes): {response_data[:500]}")
            self.disconnect() # Disconnect on bad data
            raise ValueError(f"Invalid response format from Cadwork plug-in: {str(e)}")
        except Exception as e:
            logger.error(f"Unexpected error communicating with Cadwork plug-in: {str(e)}")
            self.disconnect() # Disconnect on other errors
            raise RuntimeError(f"Communication error with Cadwork plug-in: {str(e)}")

# Global connection instance (managed by lifespan)
_cadwork_connection: Optional[CadworkConnection] = None

def get_cadwork_connection() -> CadworkConnection:
    """Get the active Cadwork connection, raising an error if not connected."""
    if _cadwork_connection is None or _cadwork_connection.sock is None:
        # This ideally shouldn't happen if lifespan manager is working correctly
        # and tools/resources check connection status.
        logger.error("Cadwork connection not available or disconnected.")
        raise ConnectionError("Not connected to the Cadwork plug-in. Ensure it's running and the server lifespan manager connected successfully.")
    return _cadwork_connection

@asynccontextmanager
async def server_lifespan(server: FastMCP) -> AsyncIterator[Dict[str, Any]]:
    """Manage server startup and shutdown lifecycle, including Cadwork connection."""
    global _cadwork_connection
    host = "127.0.0.1"
    port = int(os.environ.get("CW_PORT", DEFAULT_CADWORK_PORT))

    logger.info(f"CadworkMCP server starting up. Attempting connection to plug-in at {host}:{port}...")
    _cadwork_connection = CadworkConnection(host=host, port=port)

    # Try initial connection on startup
    connected = False
    try:
        if _cadwork_connection.connect():
             # Optional: Send a 'ping' or 'get_version' command to verify?
             # try:
             #     version_info = _cadwork_connection.send_command("get_version_info")
             #     logger.info(f"Successfully connected to Cadwork plug-in. Version info: {version_info}")
             #     connected = True
             # except Exception as ping_error:
             #     logger.warning(f"Connected to socket, but failed to get version info: {ping_error}")
             #     # Decide if this is critical. Maybe the plugin is old or doesn't support it.
             #     # We can still proceed, but log the warning.
             #     connected = True # Assume connection is okay if socket opened
             logger.info("Successfully established socket connection to Cadwork plug-in.")
             connected = True
        else:
             logger.warning("Could not connect to Cadwork plug-in on startup.")
             # Server will still start, but tools will fail until plug-in is ready.
    except Exception as e:
        logger.error(f"Error during initial connection attempt to Cadwork plug-in: {str(e)}")
        # Ensure connection object is reset if connection failed badly
        if _cadwork_connection:
             _cadwork_connection.disconnect() # Clean up socket if partially opened
        _cadwork_connection = None

    # Yield context to the server
    # We could pass the connection status or details if needed by MCP app startup
    yield {"cadwork_connected_on_startup": connected}

    # Cleanup on shutdown
    logger.info("CadworkMCP server shutting down...")
    if _cadwork_connection:
        _cadwork_connection.disconnect()
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
# @mcp.tool(...)
# async def create_beam(...): ...


# Main execution function (consider moving to a separate main.py or __main__.py later)
async def main():
    """Run the CadworkMCP server."""
    # uvicorn is used indirectly when calling mcp.run() if default settings are used
    # For explicit control, you might configure uvicorn separately
    logger.info("Starting CadworkMCP server...")
    # The host and port here are for the MCP server itself, not the Cadwork connection
    mcp.run(host="127.0.0.1", port=8010) # Example port for the MCP server


if __name__ == "__main__":
    # Note: Running directly like this might have issues with async context in some envs.
    # Using 'uvicorn cadworkmcp.server:mcp --reload' or a proper entry point is recommended.
    # For simplicity now:
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.") 