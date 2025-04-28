## Cadwork MCP Server – Technical Build Guide

### 1  Purpose & Scope
- *Goal:* Model-Context-Protocol (MCP)-aware agent Cursor create, query or modify a live Cadwork 3D model in real time.  
- *Core idea:* keep Cadwork editing logic inside Cadwork (Python plug-in) while exposing a lightweight HTTP/JSON façade that agents already understand.  
- *Security boundary:* all write operations stay in Cadwork’s sandbox; the outer HTTP service never touches model files directly (minimises data-loss risk).

### 2  RhinoMCP vs CadworkMCP – Key Differences
| Area | *RhinoMCP* (reference) | *CadworkMCP* (target) | Impact on build |
|------|--------------------------|-------------------------|-----------------|
| *Inner bridge language* | C# plug-in compiled for Rhino | Plain Python script in API.x64 | No compiler → faster iteration. |
| *Geometry API* | rhinoscriptsyntax | element_controller, utility_controller, etc. | Need wrapper converting JSON arrays → point_3d objects (type safety). |
| *Thread safety* | Rhino allows long-running tasks on UI thread | Cadwork freezes if UI thread blocked | Always start socket loop in a daemon thread. |
| *Autostart mechanism* | Plug-in embedded via Rhino package installer | utility_controller.api_autostart() flag | Document one-time flag set for deployment. |
| *Version detection* | rs.AppVersion() | uc.get_cadwork_version() | Add handshake check for ≥ v27. |

(Comments in italics show why choices differ.)

### 3  High-Level Architecture
*Two-layer pattern, identical to RhinoMCP*

1. *Inner socket service (Cadwork plug-in)*  
   - Lives at …\API.x64\cadwork_mcp\cadwork_mcp.py.  
   - Opens 127.0.0.1:<port>; translates JSON to Cadwork API calls; returns JSON.  
   - Runs in a background thread → UI stays responsive. (Essential for user experience.)
2. *Outer FastAPI façade (optional but recommended)*  
   - Re-uses RhinoMCP’s FastAPI routes; forwards each request to the socket.  
   - Lets multiple agents share the same Cadwork instance concurrently.  
   - Lives anywhere on disk; launched by uvx cadworkmcp entry-point.

### 4  Modules / Components
| Layer | Module | Responsibility |
|-------|--------|----------------|
| *Cadwork plug-in* | *dispatcher.py* | maps "operation" strings → controller calls; centralised to ease adding commands. |
| | *types.py* | helpers: to_pt(list) → point_3d, enum aliases, version constants; keeps cadwork_mcp.py minimal. |
| | *server.py* | socket bind, JSON decode/encode, thread start/stop; no Cadwork calls here (separation of concerns). |
| *Outer façade* | *api.py* | FastAPI routes, pydantic schemas (validates agent payloads early). |
| | *bridge.py* | minimal TCP client (send_cmd(cmd_dict)) + timeout retry; allows drop-in switch to websockets later. |
| *Shared assets* | *plugin_info.xml, **Icon.png* | toolbar appearance & tooltip; optional but helps users find the button. |

(Small, single-responsibility modules make future expansion—e.g., IFC export—less error-prone.)

### 5  Recommended Data Structures
| Structure | Fields | Notes |
|-----------|--------|-------|
| **MCPRequest** | operation:str, args:dict[str,Any] | Flat JSON packets keep socket parsing trivial. |
| **BeamArgs** | p1:list[float], p2:list[float], width:float, height:float, p3:list[float]|None | Mirrors Cadwork signature; p3 optional; default is p1 + z. |
| **MCPResponse** | status:str ("ok"|"error"), id:int|None, name:str|None, msg:str|None | Single schema for all replies (simplifies agent code). |
| **OpTable** (Python dict) | key =operation, value =callable(args)->dict | Dispatcher look-up; avoids if-elif chains. (Easier to unit-test.) |
| **VersionInfo** | cw_version:int, mcp_server:str | Sent on first handshake; outer façade can warn if feature unsupported. |

### 6  Data Relationships

FastAPI JSON (validated) ──► TcpBridge (bytes)
                                 │
                                 ▼
                    Cadwork Plug-in Dispatcher
                                 │
                  +--------------+---------------+
                  |                              |
        Cadwork Controller API          utility_controller
                  |                              |
             Model Changes                 Meta-Info

(Unidirectional arrows show control flow; data always returned upward as JSON only.)

### 7  Deployment Steps (chronological)
1. *Place plug-in folder* in Userprofile\API.x64.  
2. *Click the plug-in* once to verify socket message “listening…”.  
3. **Run uc.api_autostart("cadwork_mcp",1)** so Cadwork auto-loads it.  
4. *Install outer package* with uv pip install -e . (editable for dev).  
5. *Add MCP entry* in ~/.cursor-config.json → agents discover it automatically.  
6. *Document port* in README; allow override via CW_PORT env var (helps multi-instance setups).  

(Order ensures a developer can test each layer independently.)

### 8  Why These Choices
- *Simple TCP + JSON* on localhost: keeps zero dependencies inside Cadwork; no risk of TLS/WS overhead.  
- *FastAPI outside*: piggybacks RhinoMCP codebase → 95 % reused.  
- *Type-conversion helper*: isolates Cadwork-specific point_3d quirks; business logic remains framework-agnostic.  
- *Threading not asyncio* inside Cadwork: CPython 3.9 in Cadwork lacks modern async features; threads are sufficient and predictable.  
- *One schema for all replies*: agents can generically route responses without operation-specific parsing—perfect for LLM tool calls.

---

Delivering the above structure gives any developer a drop-in Cadwork MCP server that mirrors RhinoMCP behaviour while respecting Cadwork’s own API constraints and threading model.