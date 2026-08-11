## Setup & Installation

1. Clone the repository.
2. Install the required Python packages:
   pip install -r requirements.txt

3. Create a `.env` file in the project root.
4. Add your Google Gemini API key:
   GOOGLE_API_KEY=your_api_key_here

5. Run the application:
   python3 -m streamlit run app.py

## How to Use

1. Enter your Google Gemini API key in the sidebar if required.
2. Enter a natural language question about the database.
3. The AI agent analyzes the question and queries the SQLite database.
4. Results are displayed as text and visualizations when applicable.

## Project Structure

- `app.py` – Main Streamlit application and AI agent
- `create_sample_db.py` – Creates the sample database
- `ecommerce.db` – Sample SQLite database
- `requirements.txt` – Python dependencies
- `.env` – Local API key configuration (not committed to GitHub)