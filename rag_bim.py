#!/usr/bin/env python
r"""
Self‑contained RAG for the BIM timber dataset – hybrid approach:
1.   Structured questions → SQL via DuckDB over **all** rows.
2.   Open‑ended questions → Chroma vector search + GPT‑4o.

Place this file anywhere. Specify where your existing **rag_db** lives by
setting one env‑var:

    setx RAG_DB_DIR "C:\\path\\to\\rag_db"

If you skip it, the script falls back to a sibling folder named `rag_db/`.

### requirements.txt
openai>=1.12.0
chromadb>=0.4.23
duckdb>=0.10.2
python-dotenv
tqdm

Install then run, e.g.:
```bash
pip install -r requirements.txt
python rag_bim.py "how many CLT elements do we have?"
```
"""

import json, os, sys, pathlib, re
from typing import List
from dotenv import load_dotenv
from tqdm import tqdm
import duckdb
import chromadb
from chromadb.config import Settings
from chromadb.utils.embedding_functions import OpenAIEmbeddingFunction
import openai

# ANSI colors
C_CYAN  = '\033[96m'
C_GREEN = '\033[92m'
C_RESET = '\033[0m'

# ---------------------- env & paths ---------------------------------------
load_dotenv()
API_KEY = os.getenv("OPENAI_API_KEY")
if not API_KEY:
    sys.exit("OPENAI_API_KEY missing – add it to .env or env vars.")

BASE = pathlib.Path(__file__).resolve().parent
DATA_PATH = BASE / "bim_timber_clean.jsonl"
SQL_DB    = BASE / "bim.duckdb"
VEC_DB_DIR = pathlib.Path(os.getenv("RAG_DB_DIR", BASE / "rag_db"))
COLLECTION = "bim"
EMBED_MODEL = "text-embedding-3-small"

# ---------------------- DuckDB -------------------------------------------

def ensure_table() -> duckdb.DuckDBPyConnection:
    """Return a DuckDB connection; import JSONL the first time."""
    con = duckdb.connect(SQL_DB)

    # portable check that works on all DuckDB versions
    tbl_exists = con.sql(
        "SELECT 1 FROM information_schema.tables "
        "WHERE table_name = 'bim' LIMIT 1"
    ).fetchone() is not None

    if not tbl_exists:
        if not DATA_PATH.exists():
            sys.exit(f"JSONL not found: {DATA_PATH}")
        print("[duckdb] importing JSONL → table bim …")
        con.sql("CREATE TABLE bim AS SELECT * FROM read_json_auto(?);", params=[str(DATA_PATH)])
        con.sql("CREATE INDEX idx_nombre ON bim(nombre);")
        con.sql("CREATE INDEX idx_material ON bim(material);")
    return con


# ---------------------- Chroma -------------------------------------------

def make_sentence(entry: dict) -> str:
    bits: List[str] = []
    for k in ("nombre", "grupo", "subgrupo"):
        if v := entry.get(k):
            bits.append(str(v))
    if m := entry.get("material"):
        bits.append(f"material {m}")
    if l := entry.get("longitud_m"):
        bits.append(f"length {l:.2f} m")
    if v := entry.get("volumen_m3"):
        bits.append(f"volume {v:.2f} m³")
    if c := entry.get("comentario"):
        bits.append(f"comment {c}")
    return ", ".join(bits)


def ensure_vector():
    VEC_DB_DIR.mkdir(parents=True, exist_ok=True)
    client = chromadb.PersistentClient(path=str(VEC_DB_DIR), settings=Settings())
    embed_fn = OpenAIEmbeddingFunction(api_key=API_KEY, model_name=EMBED_MODEL)

    if COLLECTION in client.list_collections():
        return client.get_collection(COLLECTION, embedding_function=embed_fn)

    print(f"[chroma] building vector store in {VEC_DB_DIR} …")
    col = client.create_collection(COLLECTION, embedding_function=embed_fn)
    with DATA_PATH.open(encoding="utf-8") as f:
        for idx, line in enumerate(tqdm(f, desc="Embedding rows")):
            doc = json.loads(line)
            meta = {"nombre_kw": str(doc.get("nombre", "")).lower()}
            col.add(ids=str(idx), documents=make_sentence(doc), metadatas=meta)
    return col

# ---------------------- initialisation ------------------------------------
con    = ensure_table()
vector = ensure_vector()
openai_client = openai.OpenAI()

# ---------------------- tool functions ------------------------------------

def sql_query(query: str) -> str:
    try:
        df = con.execute(query).df()
    except Exception as e:
        return f"SQL error: {e}"
    return df.to_markdown(index=False)


def vector_search(question: str) -> str:
    res = vector.query(question, n_results=10)
    return "\n".join(res["documents"][0])

# ---------------------- OpenAI function-calling ---------------------------
TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "sql_query",
            "description": "Executes a SQL query against the 'bim' table containing structured BIM data. Use for precise questions involving counts, sums, averages, filtering by specific known values (e.g., material='CLT', nombre='Wall 01'), or retrieving exact lists.",
            "parameters": {
                "type": "object",
                "properties": {"query": {"type": "string", "description": "The SQL query string to execute."}},
                "required": ["query"],
            },
        }
    },
    {
        "type": "function",
        "function": {
            "name": "vector_search",
            "description": "Performs a semantic search over descriptive sentences generated from BIM element data. Use for open-ended questions, finding elements based on conceptual similarity or textual descriptions (e.g., 'find elements related to external walls', 'search for comments about connections'), or exploring related items when exact criteria are unknown. Returns up to 10 most similar results.",
            "parameters": {
                "type": "object",
                "properties": {"question": {"type": "string", "description": "The natural language question or search query for semantic search."}},
                "required": ["question"],
            },
        }
    },
]
SYSTEM_PROMPT = (
    "You are a BIM assistant. Use sql_query for numeric/list queries; "
    "use vector_search for explanatory/contextual ones."
)

# ---------------------- chat function -------------------------------------

def chat(user_q: str, history: List[dict]) -> tuple[str, List[dict]]:
    """Processes a user query within a conversation history."""
    # Append the new user message to the history
    history.append({"role": "user", "content": user_q})

    while True:
        resp = openai_client.chat.completions.create(
            model="o4-mini-2025-04-16",
            messages=history, # Pass the entire history
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = resp.choices[0].message

        # Append the assistant's response (potentially with tool calls)
        history.append(msg)

        if msg.tool_calls:
            # Append the assistant message with tool_calls before processing
            # (Already appended above)
            for call in msg.tool_calls:
                func_name = call.function.name
                args = json.loads(call.function.arguments)
                if func_name == "sql_query":
                    func_out = sql_query(args["query"])
                elif func_name == "vector_search":
                    func_out = vector_search(args["question"])
                else:
                    # Handle unknown function call if necessary
                    func_out = f"Unknown function: {func_name}"

                # Append the tool result message
                history.append({"role": "tool", "tool_call_id": call.id, "name": func_name, "content": func_out})
            continue  # loop; GPT will produce final answer next

        # If no tool calls, it's the final answer
        final_response = msg.content.strip() if msg.content else "Sorry, I couldn't generate a response."
        return final_response, history # Return the response and updated history

# --- raw SQL helper -------------------------------------------------
if len(sys.argv) > 1 and sys.argv[1] == "--sql":
    print(sql_query(" ".join(sys.argv[2:])))
    sys.exit()

# ---------------------- CLI ----------------------------------------------
if __name__ == "__main__":
    print("BIM Assistant Activated. Type 'exit' or 'quit' to end.")
    # Initialize conversation history with the system prompt
    conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
    while True:
        try:
            question = input(f"{C_CYAN}Ask > {C_RESET}")
            if question.lower() in ["exit", "quit"]:
                break
            if not question:
                continue

            answer, conversation_history = chat(question, conversation_history)
            print(f"{C_GREEN}Assistant: {C_RESET}{answer}")

        except (KeyboardInterrupt, EOFError):
            print("\nExiting...")
            break
        except Exception as e:
            print(f"An error occurred: {e}")
            # Optionally reset history or try to recover
            # conversation_history = [{"role": "system", "content": SYSTEM_PROMPT}]
