Please find the main.py contains the code for said project.

I have configured this code to be used by streamlit and so a single line requires change.
**Please add a .env file to the directory with these contents**
GEMENI_API_KEY = your_api_key

**and within the main.py file change line 20 to configure .env**
api_key = st.secrets["GOOGLE_API_KEY"]

TO
api_key= os.getenv("GOOGLE_API_KEY")

Install dependencies using pip install -r requirements.txt

RUN CODE WITH : streamlit run main.py
Make sure to be in the correct directory before running.
Cheers!
