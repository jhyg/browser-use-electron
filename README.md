# Browser Use Electron

## Setup

1. Create a `.env` file in the root directory with your API keys and credentials:

```bash
# LLM API Keys
OPENAI_API_KEY=your_openai_api_key_here

# Google Account Credentials (for authentication)
GOOGLE_EMAIL=your_google_email@gmail.com
GOOGLE_PASSWORD=your_google_password_here

# Other optional API keys
ANTHROPIC_API_KEY=your_anthropic_api_key_here
GOOGLE_API_KEY=your_google_api_key_here
```

2. Install dependencies and run the application.

## Installation

```bash
pip install -e .
pip install langchain-openai
python -m playwright install

npm i
npm start
```

## Usage
Follow the application instructions to use the browser agent.

## Google Credentials
The system now supports Google account credentials through environment variables:
- `GOOGLE_EMAIL`: Your Google account email address
- `GOOGLE_PASSWORD`: Your Google account password

These credentials are automatically loaded and made available to the agent for Google service authentication tasks.