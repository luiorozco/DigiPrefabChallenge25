# DigiPrefabChallenge25

## Demo Videos

Watch these videos to see the Cadwork MCP server in action:

<table>
  <tr>
    <td><a href="https://github.com/user-attachments/assets/d1e8f0a1-c3b1-4e9a-8a0f-1a2b3c4d5e6f" target="_blank">Example 1: Texting with Data</a></td>
    <td><a href="https://github.com/user-attachments/assets/a1b2c3d4-e5f6-7890-1234-567890abcdef" target="_blank">Example 2: Multilingual Texting</a></td>
  </tr>
  <tr>
    <td><a href="https://github.com/user-attachments/assets/f0e9d8c7-b6a5-4321-fedc-ba9876543210" target="_blank">Example 3: Identifying Trucks</a></td>
    <td><a href="https://github.com/user-attachments/assets/01234567-89ab-cdef-0123-456789abcdef" target="_blank">Example 4: Finding Materials</a></td>
  </tr>
</table>


## Overview

The **cadworkMCP** project is an MVP (Minimum Viable Product) developed during the **IntCDC Hackathon Digital Prefabrication Challenge 2025** (April 25–27, 2025). It creates a Model Context Protocol (MCP) server for Cadwork, enabling AI hosts like Claude or Cursor to interact conversationally with a BIM model inside a running Cadwork instance. This allows users to retrieve and manipulate model data programmatically, enhancing workflows in digital prefabrication and timber construction. The solution was developed in response to a challenge presented by Egoin, a timber construction company.

## How it Works

The system consists of two main parts:
1.  **Cadwork Bridge (`mcp_cadworks_bridge.py`):** A Python script running *inside* Cadwork via its API plug-in. It listens on a local socket for commands.
2.  **MCP Server (`mcp_server.py`):** An external Python server (using FastAPI via `mcp.server.fastmcp`) that exposes MCP tools. When an AI host calls a tool, this server translates the request and sends it to the Cadwork Bridge via the socket connection.

This separation keeps Cadwork-specific logic within the Cadwork environment while providing a standard MCP interface for external agents.

## Getting Started

### Prerequisites

1.  **Python**: Version 3.8 or later. ([python.org](https://www.python.org/))
2.  **Cadwork**: A running instance of Cadwork with its Python API plug-in enabled and the `mcp_cadworks_bridge.py` script running within it (see `INSTRUCTIONS.md` for setup).
3.  **Virtual Environment**: Recommended for managing dependencies.

### Setup

1.  Clone the repository.
2.  Open a terminal in the project directory.
3.  Create and activate a virtual environment:
    ```bash
    # Windows
    python -m venv venv
    .\venv\Scripts\activate
    # macOS/Linux
    python3 -m venv venv
    source venv/bin/activate
    ```
4.  Install dependencies:
    ```bash
    pip install -r requirements.txt
    ```

### Running the MCP Server

The MCP server needs to be running for an AI host to connect to it.

1.  Ensure the Cadwork Bridge (`mcp_cadworks_bridge.py`) is running inside Cadwork and listening on the configured port (default: 53002).
2.  Run the MCP server from your terminal (ensure the virtual environment is active):
    ```bash
    python mcp_server.py
    ```
    This typically starts the server in stdio mode, suitable for direct integration with tools like Cursor configured via `.cursor/mcp.json`. If you need an HTTP server, you might need to adjust the run command or the server configuration (refer to `mcp_server.py` and `mcp.server` documentation).

### Connecting an AI Host (e.g., Cursor)

The primary way to use this project is through an AI-powered code editor or chat interface that supports MCP.

1.  **Configure your Host:** Set up your AI host (like Cursor) to connect to the running MCP server. This project includes a sample configuration in `.cursor/mcp.json`. You may need to adjust paths and ports according to your setup.
2.  **Interact:** Once connected, you can ask the AI host to perform actions using the available tools, such as:
    *   `get_cadwork_version_info`: Get version details.
    *   `create_beam`: Create a new beam element.
    *   `get_element_info`: Retrieve geometry and attributes for an element.
    *   `get_active_element_ids`: Get IDs of selected elements.
    *   `get_standard_attributes`: Get common attributes (name, group, material, etc.).
    *   `get_user_attributes`: Get specific user-defined attributes.
    *   `list_defined_user_attributes`: List available user attributes.

The AI host will call the corresponding tools on the MCP server, which communicates with Cadwork to execute the actions or retrieve the requested information.

## Hackathon Context

The project was developed as part of a hackathon held from April 25–27, 2025, organized by the Cluster of Excellence IntCDC and the University of British Columbia. The hackathon focused on digital prefabrication in timber construction, with participation from companies like Blumer Lehmann, Renggli, Strong by Form, Egoin, and others. Teams worked on challenges in digital design and prefabrication processes, presenting their solutions to a jury for awards in categories like Industry, Research, and Innovation.

## Features

- **Interactive MCP Server**: Facilitates communication between Cadwork and external tools or hosts.
- **BIM Model Interaction**: Retrieve, modify, and query BIM model data programmatically.
- **Custom Tools**: Includes tools for creating beams, retrieving element information, and managing attributes.

## Important Requirements

- **Python Version:** You must use Python 3.10 or higher for the MCP server to work correctly. Check your version with:
  ```bash
  python3 --version
  ```
  If you have an older version, download and install the latest Python from [python.org](https://www.python.org/downloads/).

## Tools and Usage

The MCP server includes several tools for interacting with Cadwork. Below are some examples:

1. **Get Cadwork Version Info**:
   - Retrieves version information from the Cadwork application and plug-in.

2. **Create Beam**:
   - Creates a rectangular beam in the active Cadwork 3D model.
   - Example:
     ```python
     {
       "operation": "create_beam",
       "args": {
         "p1": [0, 0, 0],
         "p2": [10, 0, 0],
         "width": 0.2,
         "height": 0.3
       }
     }
     ```

3. **Get Element Info**:
   - Retrieves geometric and attribute information for a specific element.

4. **List Defined User Attributes**:
   - Lists all user-defined attributes configured in the current Cadwork environment.

## Contribution

This project is an MVP and welcomes contributions to improve its functionality and usability. Feel free to fork the repository and submit pull requests.

## Acknowledgments

Special thanks to the organizers, mentors, and participants of the IntCDC Hackathon Digital Prefabrication Challenge 2025 for their support and collaboration.

## Technical Architecture & Instructions

For a deeper understanding of the design and deployment, see the summary below (adapted from `INSTRUCTIONS.md`).

### Purpose & Scope
- **Goal:** Enable MCP-aware agents (like Cursor or Claude) to create, query, or modify a live Cadwork 3D model in real time.
- **Approach:** All Cadwork editing logic remains inside Cadwork (Python plug-in), while a lightweight HTTP/JSON façade exposes the interface for agents.
- **Security:** All write operations are sandboxed within Cadwork; the HTTP service never touches model files directly, minimizing data-loss risk.

### Key Differences from RhinoMCP
- **No compilation:** CadworkMCP uses plain Python scripts for rapid iteration.
- **Geometry API:** Uses Cadwork's controllers (e.g., `element_controller`, `utility_controller`).
- **Threading:** Always run the socket loop in a daemon thread to keep the UI responsive.
- **Autostart:** Use `utility_controller.api_autostart()` for plug-in deployment.
- **Version check:** Handshake checks for Cadwork v27+.

### High-Level Architecture
- **Inner Socket Service (Cadwork plug-in):**
  - Listens on `127.0.0.1:<port>`, translates JSON to Cadwork API calls, returns JSON.
  - Runs in a background thread for UI responsiveness.
- **Outer FastAPI Façade (optional):**
  - Forwards HTTP requests to the socket, allowing multiple agents to share a Cadwork instance.
  - Reuses FastAPI routes from RhinoMCP.

### Main Components
- **dispatcher.py:** Maps operation strings to controller calls.
- **types.py:** Type helpers and constants.
- **server.py:** Socket binding, JSON encode/decode, thread management.
- **api.py (outer):** FastAPI routes and payload validation.
- **bridge.py (outer):** TCP client for command forwarding.

### Data Structures
- **MCPRequest:** `{operation: str, args: dict}`
- **BeamArgs:** `{p1: [x, y, z], p2: [x, y, z], width: float, height: float, p3: [x, y, z]|None}`
- **MCPResponse:** `{status: 'ok'|'error', id: int|None, name: str|None, msg: str|None}`
- **OpTable:** Python dict mapping operation to callable.
- **VersionInfo:** `{cw_version: int, mcp_server: str}`

### Deployment Steps
1. Place the plug-in folder in `Userprofile\API.x64`.
2. Click the plug-in to verify it shows “listening…” in the socket message.
3. Run `uc.api_autostart("cadwork_mcp",1)` to auto-load the plug-in.
4. (Optional) Install the outer FastAPI package with `uv pip install -e .` for development.
5. Add MCP entry in `~/.cursor-config.json` for agent discovery.
6. Document the port in the README; override with `CW_PORT` env var if needed.

### Design Rationale
- **Simple TCP + JSON:** Zero dependencies inside Cadwork, no TLS/WS overhead.
- **FastAPI outside:** Reuses existing codebase for rapid development.
- **Type-conversion helpers:** Isolate Cadwork-specific quirks.
- **Threading:** Reliable and compatible with Cadwork’s Python environment.
- **Unified response schema:** Simplifies agent integration and tool calls.

---

For more details, see the `INSTRUCTIONS.md` and the `docs/` directory for module-level documentation and examples.

## Retrieval-Augmented Generation (RAG) Integration

This project includes a RAG (Retrieval-Augmented Generation) component for enhanced BIM data interaction. The `rag_bim.py` script enables you to query BIM data using natural language, leveraging a local database and OpenAI's API for LLM-powered responses.

### Setting Up RAG and OpenAI API

1. **Install Requirements**
   - Ensure your virtual environment is activated (see above).
   - Install all dependencies:
     ```bash
     pip install -r requirements.txt
     ```

2. **Create a `.env` File**
   - In the project root directory, create a file named `.env` (no filename, just `.env`).
   - Add your OpenAI API key to this file:
     ```env
     OPENAI_API_KEY=sk-...your-key-here...
     ```
   - Save the file. This keeps your API key private and secure.

3. **Run RAG BIM Script**
   - To use the retrieval-augmented BIM querying, run:
     ```bash
     python rag_bim.py
     ```
   - The script will use your `.env` file to access the OpenAI API and provide enhanced BIM data responses.

### Notes for Novice Users
- If you do not have an OpenAI API key, you can get one by signing up at [OpenAI's website](https://platform.openai.com/signup).
- Never share your API key publicly or commit it to version control.
- The `.env` file is automatically loaded by the project to keep your credentials safe.

---

For more details on RAG and BIM data, see the `rag_bim.py` script and the documentation in the `docs/` folder.

## Registering the MCP Server with Cursor (.cursor/mcp.json)

To make your Cadwork MCP server discoverable by Cursor, you may need to create a `.cursor/mcp.json` file in your project root or in your home directory under `.cursor/`.

### Example `.cursor/mcp.json`:
```json
{
  "mcp_servers": [
    {
      "name": "CadworkMCP",
      "host": "127.0.0.1",
      "port": 53002,
      "description": "MCP server for Cadwork BIM integration. Developed during IntCDC Hackathon 2025."
    }
  ]
}
```

- Place this file at `/workspaces/DigiPrefabChallenge25/.cursor/mcp.json` or in your home directory at `~/.cursor/mcp.json`.
- Adjust the `host` and `port` if you are running the server on a different machine or port.
- This will allow Cursor to automatically detect and list your Cadwork MCP server as an available agent.
