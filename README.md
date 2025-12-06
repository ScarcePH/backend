# Scarce Agent Messenger AI Bot

A Flask-based Facebook Messenger bot for ScarcePH, powered by OpenAI GPT and auto-replies for common sneaker shop FAQs.

## Features

### 🧠 AI + Bot Logic
- GPT-powered Intent Detection and fallback replies  
- Rule-based responses for FAQs, catalog, ordering, shipping, and payments  
- Multi-step conversation flow (state machine)  
- Human handover via Messenger echo-detection

### 👟 Commerce Workflow
- Saves customers, orders, and addresses to PostgreSQL  
- Supports payment image verification  


## Setup
1. **Clone the repo**  
2. **Create a virtual environment**  
    python3 -m venv venv
    source venv/bin/activate
3. **Install dependencies**  
    pip install -r requirements.txt
4. **Database Setup**
    flask db init
    flask db migrate -m "Initial tables"
    flask db upgrade
5. **Run**
    python app.py
