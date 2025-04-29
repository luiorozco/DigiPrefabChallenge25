# DigiPrefabChallenge25

## Demo Videos

Watch these videos to see the Cadwork MCP server in action:

<table>
  <tr>
    <td>Example 3: Identifying Trucks<br><img src="videos/Example_3_identifyingTrucks-ezgif.com-video-to-gif-converter.gif" alt="Example 3: Identifying Trucks"></td>
  </tr>
  <tr>
    <td>Example 4: Finding Materials<br><img src="videos/Example_4_findingMaterials-ezgif.com-video-to-gif-converter.gif" alt="Example 4: Finding Materials"></td>
  </tr>
</table>


## Overview

The **cadworkMCP** project is an MVP (Minimum Viable Product) developed during the **IntCDC Hackathon Digital Prefabrication Challenge 2025** (April 25–27, 2025). It creates a Model Context Protocol (MCP) server for Cadwork, enabling AI hosts like Claude or Cursor to interact conversationally with a BIM model inside a running Cadwork instance. This allows users to retrieve and manipulate model data programmatically, enhancing workflows in digital prefabrication and timber construction. The solution was developed in response to a challenge presented by Egoin, a timber construction company.

## Architecture

The system enables MCP-aware agents (like Cursor or Claude) to create, query, or modify a live Cadwork 3D model in real time. All Cadwork editing logic remains inside Cadwork (Python plug-in), while a lightweight HTTP/JSON façade exposes the interface for agents. All write operations are sandboxed within Cadwork; the HTTP service never touches model files directly, minimizing data-loss risk.

It consists of two main parts:
1.  **Cadwork Bridge (`mcp_cadworks_bridge.py`):** A Python script running *inside* Cadwork via its API plug-in. It listens on a local socket (`127.0.0.1:<port>`) for commands, translates JSON to Cadwork API calls, and returns JSON responses. It runs in a background thread to keep the Cadwork UI responsive. The bridge can be run via the Python IDLE plugin for Cadwork (https://docs.cadwork.com/projects/cwapi3dpython/en/latest/get_started/).
2.  **MCP Server (`mcp_server.py`):** An external Python server (using FastAPI via `mcp.server.fastmcp`) that exposes MCP tools. When an AI host calls a tool, this server translates the request and sends it to the Cadwork Bridge via the socket connection. This allows multiple agents to share a Cadwork instance.

This separation keeps Cadwork-specific logic within the Cadwork environment while providing a standard MCP interface for external agents.

## Getting Started

### Prerequisites

1.  **Python**: Version 3.10 or later. ([python.org](https://www.python.org/))
2.  **Cadwork**: A running instance of Cadwork v27+ with its Python API plug-in enabled.
3.  **Virtual Environment**: Recommended for managing dependencies. See [Python venv documentation](https://docs.python.org/3/library/venv.html).

### Important Requirements

- **Python Version:** You must use Python 3.10 or higher for the MCP server to work correctly. Check your version with:
  ```bash
  python3 --version
  ```
  If you have an older version, download and install the latest Python from [python.org](https://www.python.org/downloads/).

### Setup and Usage

1.  **Clone the Repository:**
    ```bash
    git clone <repository-url>
    cd DigiPrefabChallenge25
    ```
2.  **Set up Cadwork Bridge:**
    *   Run the `mcp_cadworks_bridge.py` script within Cadwork (e.g., via the Python IDLE plugin). Verify it shows “listening…” in the socket message.
3.  **Set up MCP Server:**
    *   Open a terminal in the project directory.
    *   Create and activate a virtual environment:
        ```bash
        # Windows
        python -m venv venv
        .\venv\Scripts\activate
        # macOS/Linux
        python3 -m venv venv
        source venv/bin/activate
        ```
    *   Install dependencies:
        ```bash
        pip install -r requirements.txt
        # Or using uv:
        # uv pip install -r requirements.txt
        ```
        *(Note: The default port is 53002. Override with the `CW_PORT` environment variable if needed.)*
4.  **Configure your AI Host (e.g., Cursor or Claude):**
    *   Set up your AI host to connect to the running MCP server (typically `http://127.0.0.1:53002`).
        *   For **Cursor**, follow the [MCP setup guide](https://docs.cursor.com/context/model-context-protocol).
        *   For **Claude**, refer to the [MCP Use documentation](https://docs.anthropic.com/en/docs/agents-and-tools/mcp).
    *   For Cursor, you can create a `.cursor/mcp.json` file in the project root or your home directory (`~/.cursor/`) to make the server discoverable:
      ```json
        {
          "mcpServers": {
            "cadwork": {
              "command": "python",
              "args": [
                "C:\\Users\\SSlezak\\Documents\\github\\DigiPrefabChallenge25\\mcp_server.py",
                "mcp_server.py",
                "--transport",
                "http",
                "--port",
                "8001"
              ],
              "env": {
                "CW_PORT": "53002"
              },
              "uri": "http://localhost:8001"
            }
          }
        }
      ```
      Adjust `host` and `port` if necessary.
5.  **Interact:** Once connected, ask the AI host to perform actions using the available tools (see below). The AI host will call the corresponding tools on the MCP server, which communicates with Cadwork via the bridge to execute the actions or retrieve information.

     *Use case: In your prefered host environment (cursor most likely), you can write a prompt like you would when using chatGPT. It is a good practice to give context in your prompt that you would like to execute something with cadworkMCP.*

## Features and Tools

- **Interactive MCP Server**: Facilitates communication between Cadwork and external tools or hosts.
- **BIM Model Interaction**: Retrieve, modify, and query BIM model data programmatically.
- **Available Tools**:
    *   `get_cadwork_version_info`: Get version details from Cadwork and the plug-in.
    *   `create_beam`: Create a new rectangular beam element.
        - Example Args: `{"p1": [0, 0, 0], "p2": [10, 0, 0], "width": 0.2, "height": 0.3}`
    *   `get_element_info`: Retrieve geometry and attribute information for a specific element ID.
    *   `get_active_element_ids`: Get IDs of currently selected elements in Cadwork.
    *   `get_standard_attributes`: Get common attributes (name, group, material, etc.) for an element ID.
    *   `get_user_attributes`: Get specific user-defined attributes for an element ID.
    *   `list_defined_user_attributes`: List all user-defined attributes configured in the current Cadwork environment.

## Retrieval-Augmented Generation (RAG) Integration

This project includes an optional RAG (Retrieval-Augmented Generation) component for enhanced BIM data interaction using natural language.


## Hackathon Context

This project was developed as part of the **IntCDC Hackathon Digital Prefabrication Challenge 2025** (April 25–27, 2025), organized by the Cluster of Excellence IntCDC and the University of British Columbia. The hackathon focused on digital prefabrication in timber construction, with participation from companies like Blumer Lehmann, Renggli, Strong by Form, Egoin, and others.

## Contribution

This project is an MVP and welcomes contributions. Feel free to fork the repository and submit pull requests.

## Authors

- **Client:** Lui Orozco
- **Tutor:** Lasath Siriwardena
- **Technical Support:** Rainer Abt

**Team:**
- Sasipa Vichitkraivin
- Max Maier
- Samuel Slezak
- Hyo Wook Kim

## Acknowledgments

Special thanks to the organizers, mentors, and participants of the IntCDC Hackathon Digital Prefabrication Challenge 2025.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.


