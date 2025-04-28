#!/usr/bin/env python
"""
Self‑contained RAG for the BIM timber dataset – hybrid approach:
1.   Structured questions → SQL via DuckDB over **all** rows.
2.   Open‑ended questions → Chroma vector search + GPT‑4o.

Place this file anywhere. Specify where your existing **rag_db** lives by
setting one env‑var:

    setx RAG_DB_DIR "C:\Users\Samko\Documents\Github\DigiPrefabChallenge25_new\DigiPrefabChallenge25\rag_db"

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

def ensure_table():
    con = duckdb.connect(SQL_DB)
    if not con.table_exists("bim"):
        if not DATA_PATH.exists():
            sys.exit(f"Missing {DATA_PATH} – place dataset next to script.")
        print("[duckdb] importing JSONL → table bim …")
        con.execute("CREATE TABLE bim AS SELECT * FROM read_json_auto(?);", [str(DATA_PATH)])
        con.execute("CREATE INDEX ON bim(nombre);")
        con.execute("CREATE INDEX ON bim(material);")
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

    if COLLECTION in {c.name for c in client.list_collections()}:
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
        "name": "sql_query",
        "description": "Run SQL on table 'bim' for counts, sums, filters, lists.",
        "parameters": {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        },
    },
    {
        "name": "vector_search",
        "description": "Return up to 10 semantically similar BIM rows.",
        "parameters": {
            "type": "object",
            "properties": {"question": {"type": "string"}},
            "required": ["question"],
        },
    },
]
SYSTEM_PROMPT = (
    "You are a BIM assistant. Use sql_query for numeric/list queries; "
    "use vector_search for explanatory/contextual ones. "
    "When counting elements by type, search BOTH nombre and material columns."
)

# ---------------------- chat function -------------------------------------

def chat(user_q: str) -> str:
    msgs = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user",   "content": user_q},
    ]
    while True:
        resp = openai_client.chat.completions.create(
            model="gpt-4o-mini",
            temperature=0,
            messages=msgs,
            tools=TOOLS,
            tool_choice="auto",
        )
        msg = resp.choices[0].message
        if msg.tool_calls:
            for call in msg.tool_calls:
                func_out = (
                    sql_query(call.args["query"]) if call.name == "sql_query" else
                    vector_search(call.args["question"])
                )
                msgs.append({"role": "tool", "tool_call_id": call.id, "content": func_out})
            continue  # loop; GPT will produce final answer next
        return msg.content.strip()

# ---------------------- CLI ----------------------------------------------
if __name__ == "__main__":
    question = " ".join(sys.argv[1:]) or input("Ask > ")
    print(chat(question))
