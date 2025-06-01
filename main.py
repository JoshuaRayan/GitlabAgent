import streamlit as st
import requests
from bs4 import BeautifulSoup
import google.generativeai as genai
import os
import json
import time
from urllib.parse import urljoin, urlparse
import re
from typing import List, Dict, Any
import hashlib
from dotenv import load_dotenv

load_dotenv()
GITLAB_HANDBOOK_URL = "https://handbook.gitlab.com"
GITLAB_DIRECTION_URL = "https://about.gitlab.com"
max_pages = 50
json_file = "gitlab_data_cache.json"

api_key = st.secrets["GOOGLE_API_KEY"]

class GitLabScraperBot:
    def __init__(self):
        self.data_scraped = []
        self.session = requests.Session()
        self.session.headers.update({
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
        })
    def extract_text_from_webpage(self, url:str) -> Dict[str, Any]:
        try:
            response = self.session.get(url)
            response.raise_for_status()

            soup = BeautifulSoup(response.content, 'html.parser')

            for script in soup(['script', 'style', 'nav', 'footer', 'header']):
                script.decompose()

            title = soup.find('title')
            if title:
                title_text=title.get_text().strip()
            else:
                title_text = ""
            
            main_content= soup.find('main') or soup.find('article') or soup.find("div", class_='content')
            if not main_content:
                main_content= soup.find('body')
            if main_content:
                text = main_content.get_text()
            else:
                text = soup.get_text()

            lines = text.spiltlines()
            cleanlines = []
            for line in lines:
                stripped_lines = line.strip()
                if stripped_lines:
                    cleanlines.append(stripped_lines)
            
            all_phrases = []
            for line in cleanlines:
                phrases = line.split("  ")
                for phrase in phrases:
                    stripped_phrase = phrase.strip()
                    if stripped_phrase:
                        all_phrases.append(stripped_phrase)
            text = " ".join(all_phrases)

            if len(text) > 5000:
                text = text[:5000] + "..."
            
            return {
                "url": url,
                "title": title_text,
                "content":text,
                "hash": hashlib.md5(text.encode()).hexdigest()
            }

        except Exception as e:
            st.error(f"Error extracting text from {url}: {e}")
            return None
        
    def discorver_gitlab_pages(self) -> List[str]:
        urls=[]

        handbook_urls= [
            "/handbook/",
            "/handbook/about/",
            "/handbook/engineering/",
            "/handbook/marketing/",
            "/handbook/finance/",
            "/handbook/people-group/",
            "/handbook/sales/",
            "/handbook/legal/",
            "/handbook/security/",
            "/handbook/product/",
            "/handbook/company/",
        ]

        direction_urls = [
            "/direction/",
            "/direction/#stategic-challenges",
            "/direction/#product-strategy",
            "/direction/#fy26",
            "/direction/#fy25",
            "direction/#devsecops-stages",
            "direction/#mitigating-low-end-disruption",
        ]

        for section in handbook_urls:
            urls.append(f"{GITLAB_HANDBOOK_URL}{section}")
        
        for section in direction_urls:
            urls.append(f"{GITLAB_HANDBOOK_URL}{section}")

        return urls[0:max_pages]
        
    def scrape_gitlab_pages_for_data(self) -> List[Dict[str, Any]]:
        if os.path.exists(json_file):
            try:
                with open(json_file, 'r', encoding='utf-8') as f:
                    cached_data = json.load(f)
                    if cached_data and len(cached_data)> 0:
                        return cached_data
            except:
                pass
        urls = self.discorver_gitlab_pages()
        scraped_data = []
        progress_bar = st.progess(0)
        status_text = st.empty()

        for i,url in enumerate(urls):
            status_text.text(f"Scraping: {url}")
            
            data = self.extract_text_from_webpage(url)
            if data and len(data["content"]) > 0:
                scraped_data.append(data)
                
            # added progess bar for nice ui
            progress_bar.progress((i + 1) / len(urls))
            time.sleep(0.5)

        try:
            with open(json_file, 'w', encoding='utf-8') as f:
                json.dump(scraped_data, f, indent=2)
        except Exception as e:
            st.error(f"could nt cache")

        progress_bar.empty()
        status_text.empty()
        return scraped_data
    
class GitLabChatBot:
    def __init__(self, api_key: str):
        genai.configure(api_key=api_key)
        self.model = genai.GenerativeModel("gemini-1.5-flash")
        self.data_processor = GitLabScraperBot()
        self.knowledge_base= []

    def loading_knowledge_base(self):
        if not self.knowledge_base:
            self.knowledge_base = self.data_processor.scrape_gitlab_pages_for_data()
        return len(self.knowledge_base)
    
    def find_relevent_content(self, query:str, max_results: int = 3) -> List[Dict[str, Any]]:
        query_lower = query.lower()
        relevant_content = []
        docs = []

        for doc in self.knowledge_base:
            content_lower = doc['content'].lower()
            title_lower = doc['title'].lower()

            score = 0
            query_words =  query_lower.split()

            for word in query_words:
                if len(word)>3 :
                    score +=content_lower.count(word) * 1
                    score +=title_lower.count(word) *3

            if score>0:
                relevant_content.append({
                    'doc': doc,
                    'score': score
                })
        
        relevant_content.sort(key=lambda x:x['score'], reverse=True)
        docs = []
        for item in relevant_content[:max_results]:
            docs.append(item['doc'])
        return docs
    
    def generate_response(self, query: str, context_of_docs: List[Dict[str, Any]]) -> str:
        context = ""
        for i,doc in enumerate(context_of_docs, 1):
            context += f"\n Document {i}: {doc['title']}\n"
            context += doc['content'][:1500] 

        system_prompt = f"""You are a GitLab assistant. You help assist employees and aspiring employees to understand GitLabs 
        processes, cluture, and direction based on the Gitlab Handbook and Direction pages
        
        Context from the Gitlab Handbook and Directino pages:
        {context}

        User Question: {query}
        Instructions:
        1. Answer based primarily on the provided Gitlab documentation context.
        2. Be helpful, accurate, and concise.
        3. If te question cannot be fully answered from the context, acknowledge this 
        4. Use a friendly and professional tone that would reflect Gitlabs culture.
        5. If appropriate, provide links to the relevant sections of the Gitlab Handbook or Direction pages.

        Response:"""

        try:
            response = self.model.generate_content(system_prompt)
            return response.text
        except Exception as e:
            return f"I apologize, but I encountered an error while generating a response: {str(e)}. Please try again with another question."
        
def main():
    st.title("GitLab Handbook and Direction Chatbot")
    st.markdown("""
    Welcome to the Gitlab AI Assistant! I am here to help you find information about the Gitlab Handbook and Direction pages.
    Ask me anything in relation to GitLabs processes culture engineering and product and more.""")

    with st.sidebar:
        st.header("Sidebar")
        if not api_key:
            st.error("api error")
            return

        if 'chatbot' not in st.session_state:
            st.session_state.chatbot = GitLabChatBot(api_key)

        if st.button("Reload Knowledge Base"):
            st.session_state.chatbot.knowledge_base = []
            st.session_state.chatbot.loading_knowledge_base()

        kb_size = st.session_state.chatbot.loading_knowledge_base()
        st.metric("Knowledge Base Size", f"{kb_size} documents loaded")

        st.markdown("Sample Questions:")
        st.markdown("""
        - How does GitLab handle remote work?
        - What is GitLab's product development process?
        - Tell me about GitLab's values
        - What are GitLab's security practices?""")

    if api_key and 'chatbot' in st.session_state:
        if "messages" not in st.session_state:
            st.session_state.messages = [{
                "role": "assistant", "content":"Hello! I am here to assist you with any questions you have about GITLAB."
            }]

        for message in st.session_state.messages:
            with st.chat_message(message["role"]):
                st.markdown(message["content"])
                
        if prompt := st.chat_input("Ask me anythin about GITLAB"):
            st.session_state.messages.append({"role":"user", "content": prompt})
            with st.chat_message("user"):
                st.markdown(prompt)
                
            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    relevant_docs= st.session_state.chatbot.find_relevent_content(prompt)

                    if not relevant_docs:
                        response = "I couldnt find the relevant info or your question. Please try with another question."
                    else:
                        response = st.session_state.chatbot.generate_response(prompt, relevant_docs)

                        if relevant_docs:
                            response += "\n\n**Sources:**\n"
                            for i,doc in enumerate(relevant_docs, 1):
                                response += f"{i}. [{doc['title']}]({doc['url']})\n"
                        
                st.markdown(response)
            st.session_state.messages.append({"role": "assistant", "content": response})
                
           
if __name__ == "__main__":
    main()
