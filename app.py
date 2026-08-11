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

# ---------- Tool schemas for LLM ----------
tools = [
    {
        "type": "function",
        "function": {
            "name": "get_schema",
            "description": "Get the database schema showing all tables, columns, and types. ALWAYS call this first before writing any SQL query, so you use the correct column names.",
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
    }
]

AVAILABLE_FUNCTIONS = {
    "get_schema": get_schema,
    "execute_query": execute_query,
    "generate_chart": generate_chart
}

# Use a stronger model for reliable native tool-calling.
# llama-3.1-8b-instant is fast but often fails to emit proper tool_calls
# and instead writes the function call as plain text.
GROQ_MODEL = "llama-3.3-70b-versatile"
GEMINI_MODEL = "gemini-flash-latest"

FUNC_TEXT_PATTERN = re.compile(
    r"<function=(\w+)>\s*(\{.*?\})\s*</function>", re.DOTALL
)

def parse_text_function_call(text):
    """Fallback: some models occasionally emit the tool call as plain text
    instead of using the structured tool_calls field. Detect and parse it."""
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

# ---------- Fallback LLM call with tool execution ----------
def call_llm(messages):
    def run_groq():
        max_rounds = 5
        for _ in range(max_rounds):
            response = groq_client.chat.completions.create(
                model=GROQ_MODEL,
                messages=messages,
                tools=tools,
                tool_choice="auto"
            )
            msg = response.choices[0].message

            # Case 1: proper structured tool call
            if msg.tool_calls:
                messages.append(msg)
                for tool_call in msg.tool_calls:
                    fn_name = tool_call.function.name
                    fn_args = json.loads(tool_call.function.arguments)
                    result = AVAILABLE_FUNCTIONS[fn_name](**fn_args)
                    messages.append({
                        "role": "tool",
                        "tool_call_id": tool_call.id,
                        "content": str(result)
                    })
                continue  # let the model see the tool result and respond again

            # Case 2: model wrote the function call as plain text (fallback)
            parsed = parse_text_function_call(msg.content)
            if parsed:
                fn_name, fn_args = parsed
                result = AVAILABLE_FUNCTIONS[fn_name](**fn_args)
                messages.append({"role": "assistant", "content": msg.content})
                messages.append({
                    "role": "user",
                    "content": f"Tool '{fn_name}' result: {result}\n\n"
                                f"Now answer the original question in plain language using this result. "
                                f"Do not output any <function=...> tags."
                })
                continue

            # Case 3: normal final answer
            return msg.content

        return "I couldn't complete the request after several tool calls. Please try rephrasing your question."

    def run_gemini():
        prompt = messages[-1]["content"]
        response = gemini_client.models.generate_content(
            model=GEMINI_MODEL,
            contents=prompt
        )
        return response.text

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

    messages = [
        {
            "role": "system",
            "content": (
                "You are a helpful data analyst assistant with access to database tools "
                "(get_schema, execute_query, generate_chart). "
                "Always call get_schema first if you are unsure of table or column names — "
                "never guess a column name. Always use the provided tools via proper tool "
                "calls to answer questions about data — never write function calls as plain "
                "text in your response."
            )
        },
        {"role": "user", "content": prompt}
    ]

    with st.spinner("Thinking..."):
        try:
            answer, provider_used = call_llm(messages)
            st.chat_message("assistant").write(answer)
            st.caption(f"Answered by: {provider_used}")
            st.session_state.chat_history.append({"role": "assistant", "content": answer})
        except Exception as e:
            st.error(f"Error: {e}")