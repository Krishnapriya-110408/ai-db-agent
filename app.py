import streamlit as st
import sqlite3
import json
import os
import re
from groq import Groq
from google import genai
import plotly.graph_objects as go

DB_PATH = "ecommerce.db"

st.set_page_config(page_title="AI DB Agent", layout="wide")
st.title("🤖 AI-Powered Database Chat Agent")

# ---------- API keys (hidden — loaded from .env only) ----------
groq_key = os.environ.get("GROQ_API_KEY", "")
gemini_key = os.environ.get("GOOGLE_API_KEY", "")

groq_client = Groq(api_key=groq_key) if groq_key else None
gemini_client = genai.Client(api_key=gemini_key) if gemini_key else None

# ---------- Database tool functions ----------
def get_schema():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [row[0] for row in cursor.fetchall()]
    schema = {}
    for table in tables:
        cursor.execute(f"PRAGMA table_info({table})")
        schema[table] = [{"column": col[1], "type": col[2]} for col in cursor.fetchall()]
        cursor.execute(f"PRAGMA foreign_key_list({table})")
        fks = cursor.fetchall()
        if fks:
            schema[table + "_foreign_keys"] = [
                {"column": fk[3], "references_table": fk[2], "references_column": fk[4]}
                for fk in fks
            ]
    conn.close()
    return json.dumps(schema)

def execute_query(query):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(query)
        columns = [desc[0] for desc in cursor.description]
        rows = cursor.fetchall()
        conn.close()
        result = [dict(zip(columns, row)) for row in rows]
        return json.dumps(result)
    except Exception as e:
        return json.dumps({"error": str(e)})

def generate_chart(chart_type, labels, values, title="Chart"):
    fig = go.Figure()
    if chart_type == "bar":
        fig.add_trace(go.Bar(x=labels, y=values))
    elif chart_type == "line":
        fig.add_trace(go.Scatter(x=labels, y=values, mode="lines+markers"))
    elif chart_type == "pie":
        fig.add_trace(go.Pie(labels=labels, values=values))
    fig.update_layout(title=title)
    st.plotly_chart(fig, use_container_width=True)
    return "Chart displayed successfully"

def generate_diagram(diagram_type, dot_source, title="Diagram"):
    """Render a flowchart or ER diagram from Graphviz DOT source."""
    try:
        st.subheader(title)
        st.graphviz_chart(dot_source)
        return f"{diagram_type} diagram displayed successfully"
    except Exception as e:
        return json.dumps({"error": str(e)})

# ---------- Tool schemas for LLM (Groq / OpenAI-style) ----------
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": "Get the database schema showing all tables, columns, types, and foreign keys. ALWAYS call this first before writing any SQL query or ER diagram, so you use the correct column/table names and relationships.",
            "parameters": {"type": "object", "properties": {}}
        }
    },
    {
        "type": "function",
        "function": {
            "name": "execute_query",
            "description": "Execute a SQL query against the ecommerce database and return results as JSON",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "The SQL query to execute"}
                },
                "required": ["query"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_chart",
            "description": "Generate a chart (bar, line, or pie) from data",
            "parameters": {
                "type": "object",
                "properties": {
                    "chart_type": {"type": "string", "enum": ["bar", "line", "pie"]},
                    "labels": {"type": "array", "items": {"type": "string"}},
                    "values": {"type": "array", "items": {"type": "number"}},
                    "title": {"type": "string"}
                },
                "required": ["chart_type", "labels", "values"]
            }
        }
    },
    {
        "type": "function",
        "function": {
            "name": "generate_diagram",
            "description": (
                "Generate a flowchart or an ER (Entity-Relationship) diagram using Graphviz DOT syntax. "
                "For ER diagrams, first call get_schema to know the real tables/columns/foreign keys, then "
                "build a DOT digraph representing tables as nodes and foreign keys as edges. "
                "For flowcharts, build a DOT digraph representing the process steps as nodes and arrows as edges. "
                "The dot_source MUST be valid Graphviz DOT text, e.g. "
                "'digraph G { rankdir=LR; Orders -> Customers [label=\"customer_id\"]; }'"
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "diagram_type": {"type": "string", "enum": ["flowchart", "er"]},
                    "dot_source": {"type": "string", "description": "Valid Graphviz DOT source code for the diagram"},
                    "title": {"type": "string"}
                },
                "required": ["diagram_type", "dot_source"]
            }
        }
    }
]

AVAILABLE_FUNCTIONS = {
    "get_schema": get_schema,
    "execute_query": execute_query,
    "generate_chart": generate_chart,
    "generate_diagram": generate_diagram
}

# ---------- Gemini tool schemas (function_declarations format) ----------
GEMINI_TOOLS = [{
    "function_declarations": [
        {
            "name": t["function"]["name"],
            "description": t["function"]["description"],
            "parameters": t["function"]["parameters"]
        } for t in tools
    ]
}]

GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-flash-latest"

SYSTEM_PROMPT = (
    "You are a helpful data analyst assistant with access to database tools "
    "(get_schema, execute_query, generate_chart, generate_diagram). "
    "Always call get_schema first if you are unsure of table or column names — "
    "never guess a column name. If the user asks for a flowchart or an ER "
    "(Entity-Relationship) diagram, call get_schema first, then call "
    "generate_diagram with valid Graphviz DOT source. Always use the provided "
    "tools via proper tool calls to answer questions about data — never write "
    "function calls as plain text in your response."
)

FUNC_TEXT_PATTERN = re.compile(
    r"<function=(\w+)>\s*(\{.*?\})\s*</function>", re.DOTALL
)

def parse_text_function_call(text):
    if not text:
        return None
    match = FUNC_TEXT_PATTERN.search(text)
    if not match:
        return None
    fn_name = match.group(1)
    try:
        fn_args = json.loads(match.group(2))
    except json.JSONDecodeError:
        return None
    if fn_name not in AVAILABLE_FUNCTIONS:
        return None
    return fn_name, fn_args

def safe_parse_args(raw_args):
    """FIX: Groq sometimes sends the literal string 'null' for functions
    with no arguments (e.g. get_schema). json.loads('null') -> None, and
    func(**None) crashes with 'argument after ** must be a mapping, not NoneType'."""
    if not raw_args:
        return {}
    try:
        parsed = json.loads(raw_args)
    except json.JSONDecodeError:
        return {}
    if not isinstance(parsed, dict):
        return {}
    return parsed

# ---------- Fallback LLM call with tool execution ----------
def call_llm(original_prompt, groq_messages):
    def run_groq():
        max_rounds = 5
        for _ in range(max_rounds):
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=groq_messages,
                tools=tools,
                tool_choice="auto"
            )
            msg = response.choices[0].message

            if msg.tool_calls:
                groq_messages.append({
                    "role": "assistant",
                    "content": msg.content or "",
                    "tool_calls": [
                        {
                            "id": tc.id,
                            "type": "function",
                            "function": {
                                "name": tc.function.name,
                                "arguments": tc.function.arguments
                            }
                        }
                        for tc in msg.tool_calls
                    ]
                })
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = safe_parse_args(tool_call.function.arguments)
                    try:
                        result = AVAILABLE_FUNCTIONS[fn_name](**fn_args)
                    except Exception as tool_err:
                        result = json.dumps({"error": f"Tool '{fn_name}' failed: {tool_err}"})
                    groq_messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })
                continue

            parsed = parse_text_function_call(msg.content)
            if parsed:
                fn_name, fn_args = parsed
                fn_args = fn_args or {}
                result = AVAILABLE_FUNCTIONS[fn_name](**fn_args)
                groq_messages.append({"role": "assistant", "content": msg.content})
                groq_messages.append({
                    "role": "user",
                    "content": f"Tool '{fn_name}' result: {result}\n\n"
                                f"Now answer the original question in plain language using this result. "
                                f"Do not output any <function=...> tags."
                })
                continue

            return msg.content

        return "I couldn't complete the request after several tool calls. Please try rephrasing your question."

    def run_gemini():
        # FIX: Gemini now gets the SAME tools + system instruction as Groq,
        # and actually executes function calls in a loop instead of just
        # answering blind (which caused "I don't have direct access..." replies).
        chat = gemini_client.chats.create(
            model=GEMINI_MODEL,
            config={
                "tools": GEMINI_TOOLS,
                "system_instruction": SYSTEM_PROMPT
            }
        )

        max_rounds = 5
        response = chat.send_message(original_prompt)

        for _ in range(max_rounds):
            function_calls = []
            for part in response.candidates[0].content.parts:
                if getattr(part, "function_call", None):
                    function_calls.append(part.function_call)

            if not function_calls:
                return response.text

            function_response_parts = []
            for fc in function_calls:
                fn_name = fc.name
                fn_args = dict(fc.args) if fc.args else {}
                try:
                    result = AVAILABLE_FUNCTIONS[fn_name](**fn_args)
                except Exception as tool_err:
                    result = json.dumps({"error": f"Tool '{fn_name}' failed: {tool_err}"})

                function_response_parts.append(
                    genai.types.Part.from_function_response(
                        name=fn_name,
                        response={"result": result}
                    )
                )

            response = chat.send_message(function_response_parts)

        return "I couldn't complete the request after several tool calls. Please try rephrasing your question."

    if groq_client:
        try:
            return run_groq(), "groq"
        except Exception as e:
            st.info(f"⚠️ Groq issue ({str(e)[:80]}...), switching to Gemini...")

    if gemini_client:
        try:
            return run_gemini(), "gemini"
        except Exception as e:
            raise Exception(f"Both providers failed. Gemini error: {e}")

    raise Exception("No valid API key found. Check your .env file.")

# ---------- Chat UI ----------
if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

for msg in st.session_state.chat_history:
    st.chat_message(msg["role"]).write(msg["content"])

if prompt := st.chat_input("Ask about your data... e.g. 'Show top 5 products by revenue'"):
    st.chat_message("user").write(prompt)
    st.session_state.chat_history.append({"role": "user", "content": prompt})

    groq_messages = [
        {"role": "system", "content": SYSTEM_PROMPT},
        {"role": "user", "content": prompt}
    ]

    with st.spinner("Thinking..."):
        try:
            answer, provider_used = call_llm(prompt, groq_messages)
            st.chat_message("assistant").write(answer)
            st.caption(f"Answered by: {provider_used}")
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.error(f"Error: {e}")