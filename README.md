# AI-Powered Database Chat Agent

A ChatGPT-like conversational agent that connects to a SQL database, answers
natural language questions, and generates charts / flowcharts using LLM
function calling (tool use).

## Architecture
- **Frontend + Backend**: Streamlit (single app.py)
- **LLM**: Google Gemini (function calling / tool use)
- **Database**: SQLite (sample e-commerce dataset: customers, products, orders, order_items)
- **Charts**: Plotly (bar, line, pie)
- **Flowcharts / ER diagrams**: Mermaid.js (rendered via markdown code block)

## Tools implemented
| Tool | Purpose |
|---|---|
| `get_schema` | Returns DB tables and columns as JSON |
| `execute_query` | Runs a SQL query, returns JSON rows |
| `generate_chart` | Creates bar / line / pie charts from data |
| `generate_flowchart` | Creates Mermaid ER diagrams / process flows |
| `explain_data` | Generates a natural language insight summary |

## Setup & Run
```bash
pip install -r requirements.txt
python create_sample_db.py      # creates ecommerce.db with sample data
streamlit run app.py
```
Enter your Google API key in the sidebar when the app opens (get one free at aistudio.google.com/apikey).

## Sample questions to try
- "What tables are in this database?"
- "Show me the top 5 products by total quantity sold as a bar chart"
- "Draw an ER diagram for this database"
- "Which city has the most customers? Show as a pie chart"
- "Explain the order status distribution"

## Notes
- Queries are restricted to the local SQLite sample database.
- The agent uses Gemini's native function-calling: it can call multiple tools
  in sequence (e.g. get_schema → execute_query → generate_chart → explain_data)
  within a single user turn.
