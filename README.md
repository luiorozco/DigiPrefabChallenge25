# DigiPrefabChallenge25

## Overview

The **cadworkMCP** project is an MVP (Minimum Viable Product) developed during the **IntCDC Hackathon Digital Prefabrication Challenge 2025**. This project aims to create an MCP (Model Context Protocol) server for Cadwork, enabling users to establish an interactive interface where hosts like Claude or Cursor can chat with a BIM (Building Information Modeling) model inside Cadwork. The solution was developed in response to a challenge presented by Egoin, a timber construction company.

This project allows users to:
- Interact with BIM models in Cadwork through a conversational interface.
- Retrieve and manipulate model data programmatically.
- Enhance workflows in digital prefabrication and timber construction.

## Hackathon Context

The project was developed as part of a hackathon held from April 25–27, 2025, organized by the Cluster of Excellence IntCDC and the University of British Columbia. The hackathon focused on digital prefabrication in timber construction, with participation from companies like Blumer Lehmann, Renggli, Strong by Form, Egoin, and others. Teams worked on challenges in digital design and prefabrication processes, presenting their solutions to a jury for awards in categories like Industry, Research, and Innovation.

## Features

- **Interactive MCP Server**: Facilitates communication between Cadwork and external tools or hosts.
- **BIM Model Interaction**: Retrieve, modify, and query BIM model data programmatically.
- **Custom Tools**: Includes tools for creating beams, retrieving element information, and managing attributes.

## Getting Started

### Prerequisites

To run this project, you need the following:

1. **Python**: Ensure Python 3.8 or later is installed. You can download it from [python.org](https://www.python.org/).
2. **Virtual Environment**: It is recommended to use a virtual environment to manage dependencies.
3. **Cadwork**: A running instance of Cadwork with its Python API plug-in enabled.

### Setting Up a Virtual Environment

1. Open a terminal and navigate to the project directory.
2. Create a virtual environment:
   ```bash
   python3 -m venv venv
   ```
3. Activate the virtual environment:
   - On Linux/Mac:
     ```bash
     source venv/bin/activate
     ```
   - On Windows:
     ```bash
     venv\Scripts\activate
     ```
4. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

## Important Requirements

- **Python Version:** You must use Python 3.10 or higher for the MCP server to work correctly. Check your version with:
  ```bash
  python3 --version
  ```
  If you have an older version, download and install the latest Python from [python.org](https://www.python.org/downloads/).

## How to Run the MCP Server for Claude or Cursor

### 1. Start the Cadwork MCP Bridge
- In Cadwork, ensure the MCP plug-in is installed and running (see deployment steps above).
- Start the bridge script (e.g., `mcp_cadworks_bridge.py`) inside Cadwork's Python environment if required.

### 2. Start the MCP Server
- In your Linux terminal, activate your virtual environment:
  ```bash
  source venv/bin/activate
  ```
- Run the MCP server:
  ```bash
  python mcp_server.py
  ```
  The server will listen on `127.0.0.1:53002` by default. You can override the port by setting the `CW_PORT` environment variable.

### 3. Connect with Cursor
- Add the MCP server to your `~/.cursor-config.json` file:
  ```json
  {
    "mcp_servers": [
      {
        "name": "CadworkMCP",
        "host": "127.0.0.1",
        "port": 53002
      }
    ]
  }
  ```
- In Cursor, select the CadworkMCP agent and start chatting with your BIM model.

### 4. Connect with Claude
- If using Claude, follow the integration instructions provided by your Claude platform or see their documentation for connecting to a local MCP server.
- Claude and Cursor both use the Model Context Protocol (MCP) to interact with your server.

### 5. Troubleshooting
- If you see connection errors, ensure:
  - Cadwork is running and the plug-in is active.
  - The MCP server is running and listening on the correct port.
  - Your Python version is 3.10 or higher.

For more details, see:
- [Cursor Model Context Protocol Documentation](https://docs.cursor.so/ai-agents/model-context-protocol)
- [Anthropic Claude MCP Integration](https://docs.anthropic.com/claude/docs/using-claude-with-mcp)

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

## Demo Videos

Below are short demo videos showing the Cadwork MCP in action:

[![Identifying Trucks (Video 3)](docs/img/demo_thumbnail.png)](videos/Example_3_identifyingTrucks.mp4)
*Identifying trucks in the BIM model (click to watch)*

[![Finding Materials (Video 4)](docs/img/demo_thumbnail.png)](videos/Example_4_findingMaterials.mp4)
*Finding materials in the BIM model (click to watch)*

> **Note:** GitHub does not support inline video playback in README files. Clicking the image will download or play the video in your browser, depending on your browser settings.
