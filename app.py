"""
AI Database Agent - Hackathon Submission
Run: streamlit run app.py
Requires: ANTHROPIC_API_KEY environment variable (or paste in sidebar)
"""
import streamlit as st
import sqlite3
import json
import os
import anthropic
import plotly.graph_objects as go

DB_PATH = "ecommerce.db"

st.set_page_config(page_title="AI DB Agent", layout="wide")
st.title("🤖 AI-Powered Database Chat Agent")

# ---------- Sidebar: API key ----------
api_key = st.sidebar.text_input("Anthropic API Key", type="password",
                                 value=os.environ.get("ANTHROPIC_API_KEY", ""))
if not api_key:
    st.warning("Enter your Anthropic API key in the sidebar to start.")
    st.stop()

client = anthropic.Anthropic(api_key=api_key)

# ---------- TOOL 1: get_schema ----------
def get_schema():
    conn = sqlite3.connect(DB_PATH)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    tables = [r[0] for r in cur.fetchall()]
    schema = {}
    for t in tables:
        cur.execute(f"PRAGMA table_info({t})")
        schema[t] = [{"column": r[1], "type": r[2]} for r in cur.fetchall()]
    conn.close()
    return json.dumps(schema)

# ---------- TOOL 2: execute_query ----------
def execute_query(sql):
    try:
        conn = sqlite3.connect(DB_PATH)
        cur = conn.cursor()
        cur.execute(sql)
        cols = [d[0] for d in cur.description] if cur.description else []
        rows = cur.fetchall()
        conn.close()
        result = [dict(zip(cols, row)) for row in rows]
        return json.dumps({"success": True, "rows": result})
    except Exception as e:
        return json.dumps({"success": False, "error": str(e)})

# ---------- TOOL 3: generate_chart ----------
def generate_chart(chart_type, labels, values, title=""):
    fig = None
    if chart_type == "bar":
        fig = go.Figure([go.Bar(x=labels, y=values)])
    elif chart_type == "line":
        fig = go.Figure([go.Scatter(x=labels, y=values, mode="lines+markers")])
    elif chart_type == "pie":
        fig = go.Figure([go.Pie(labels=labels, values=values)])
    else:
        return json.dumps({"success": False, "error": "unsupported chart_type"})
    fig.update_layout(title=title)
    st.session_state.pending_chart = fig
    return json.dumps({"success": True, "message": f"{chart_type} chart generated"})

# ---------- TOOL 4: generate_flowchart ----------
def generate_flowchart(mermaid_code, title=""):
    st.session_state.pending_mermaid = mermaid_code
    return json.dumps({"success": True, "message": "flowchart generated"})

# ---------- TOOL 5: explain_data ----------
def explain_data(data_json, question):
    resp = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=300,
        messages=[{"role": "user", "content":
                   f"Data: {data_json}\n\nQuestion: {question}\n\nGive a short 2-3 sentence natural language insight."}]
    )
    return json.dumps({"success": True, "explanation": resp.content[0].text})

TOOLS = [
    {
        "name": "get_schema",
        "description": "Get the database schema (tables and columns).",
        "input_schema": {"type": "object", "properties": {}, "required": []}
    },
    {
        "name": "execute_query",
        "description": "Execute a read-only SQL query against the SQLite database and return results.",
        "input_schema": {
            "type": "object",
            "properties": {"sql": {"type": "string", "description": "SQL SELECT query"}},
            "required": ["sql"]
        }
    },
    {
        "name": "generate_chart",
        "description": "Generate a bar, line, or pie chart from labels and values.",
        "input_schema": {
            "type": "object",
            "properties": {
                "chart_type": {"type": "string", "enum": ["bar", "line", "pie"]},
                "labels": {"type": "array", "items": {"type": "string"}},
                "values": {"type": "array", "items": {"type": "number"}},
                "title": {"type": "string"}
            },
            "required": ["chart_type", "labels", "values"]
        }
    },
    {
        "name": "generate_flowchart",
        "description": "Generate a flowchart or ER diagram using Mermaid.js syntax.",
        "input_schema": {
            "type": "object",
            "properties": {
                "mermaid_code": {"type": "string", "description": "Valid Mermaid.js diagram code"},
                "title": {"type": "string"}
            },
            "required": ["mermaid_code"]
        }
    },
    {
        "name": "explain_data",
        "description": "Generate a natural language explanation/insight from query result data.",
        "input_schema": {
            "type": "object",
            "properties": {
                "data_json": {"type": "string"},
                "question": {"type": "string"}
            },
            "required": ["data_json", "question"]
        }
    }
]

def call_tool(name, tool_input):
    if name == "get_schema":
        return get_schema()
    elif name == "execute_query":
        return execute_query(tool_input["sql"])
    elif name == "generate_chart":
        return generate_chart(tool_input["chart_type"], tool_input["labels"],
                               tool_input["values"], tool_input.get("title", ""))
    elif name == "generate_flowchart":
        return generate_flowchart(tool_input["mermaid_code"], tool_input.get("title", ""))
    elif name == "explain_data":
        return explain_data(tool_input["data_json"], tool_input["question"])
    return json.dumps({"error": "unknown tool"})

# ---------- Session state ----------
if "messages" not in st.session_state:
    st.session_state.messages = []
if "pending_chart" not in st.session_state:
    st.session_state.pending_chart = None
if "pending_mermaid" not in st.session_state:
    st.session_state.pending_mermaid = None

# ---------- Display history ----------
for msg in st.session_state.messages:
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])
        if msg.get("chart"):
            st.plotly_chart(msg["chart"], use_container_width=True)
        if msg.get("mermaid"):
            st.markdown(f"```mermaid\n{msg['mermaid']}\n```")

# ---------- Chat input ----------
user_input = st.chat_input("Ask about your data... e.g. 'Show top 5 products by revenue'")

if user_input:
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    claude_messages = [{"role": "user", "content": user_input}]

    with st.chat_message("assistant"):
        with st.spinner("Thinking..."):
            response = client.messages.create(
                model="claude-sonnet-4-6",
                max_tokens=1500,
                tools=TOOLS,
                messages=claude_messages
            )

            iterations = 0
            while response.stop_reason == "tool_use" and iterations < 5:
                claude_messages.append({"role": "assistant", "content": response.content})
                tool_results = []
                for block in response.content:
                    if block.type == "tool_use":
                        result = call_tool(block.name, block.input)
                        tool_results.append({
                            "type": "tool_result",
                            "tool_use_id": block.id,
                            "content": result
                        })
                claude_messages.append({"role": "user", "content": tool_results})
                response = client.messages.create(
                    model="claude-sonnet-4-6",
                    max_tokens=1500,
                    tools=TOOLS,
                    messages=claude_messages
                )
                iterations += 1

            final_text = "".join([b.text for b in response.content if b.type == "text"])
            st.markdown(final_text)

            chart = st.session_state.pending_chart
            mermaid = st.session_state.pending_mermaid
            if chart:
                st.plotly_chart(chart, use_container_width=True)
            if mermaid:
                st.markdown(f"```mermaid\n{mermaid}\n```")

            st.session_state.messages.append({
                "role": "assistant",
                "content": final_text,
                "chart": chart,
                "mermaid": mermaid
            })
            st.session_state.pending_chart = None
            st.session_state.pending_mermaid = None
