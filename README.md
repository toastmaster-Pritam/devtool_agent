# 🔎 Developer Tools Research Agent
A Streamlit-based web app that allows developers to search, scrape, and analyze developer tools, frameworks, and related companies. The app uses **LangChain**, **Claude LLM**, and the **Firecrawl API** to extract insights and provide recommendations.
## Features
- Search for developer-focused tools and companies.
- Automatically extract relevant tools from articles and web pages.
- Scrape company websites and generate structured insights.
- Display tech stack, pricing, API availability, and integrations.
- Generate developer recommendations using LLM.
- Live streaming of research progress in the UI.
- Export results to JSON.
## Screenshots
![alt text](/img/image.png)
![alt text](/img/image-1.png)
![alt text](/img/image-2.png)
![alt text](/img/image-3.png)
## Technologies Used
- Python 3.11+
- [Streamlit](https://streamlit.io/)
- [LangChain](https://www.langchain.com/)
- [LangGraph](https://www.langgraph.com/)
- [Claude LLM](https://www.anthropic.com/)
- [Firecrawl API](https://firecrawl.com/)
- Docker & Docker Compose
---
## Project Structure
```
.
├── Dockerfile
├── docker-compose.yml
├── requirements.txt
├── .env.example
├── app.py
├── README.md
├── .gitignore
└── src/
    ├── workflow.py
    ├── models.py
    ├── firecrawl.py
    └── prompts.py
```
## Setup & Run with Docker
1. **Clone the repository**

```bash
git clone https://github.com/toastmaster-Pritam/devtool_agent.git
cd devtool_agent
```
2. **Create `.env` file**

Copy the example and add your API keys:

```bash
cp .env.example .env
```
Edit `.env`:

```env
FIRECRAWL_API_KEY=your_firecrawl_api_key
ANTHROPIC_API_KEY=your_anthropic_api_key
```
3. **Build and run using Docker Compose**

```bash
docker-compose up -d --build
```
* `-d` runs the containers in detached mode.
* The Streamlit app will be available at [http://localhost:8501](http://localhost:8501).
4. **View logs**

```bash
docker-compose logs -f
```
5. **Stop the app**

```bash
docker-compose down
```
## Usage
1. Open the app in your browser at [http://localhost:8501](http://localhost:8501).
2. Enter a developer-focused query in the input box (e.g., `feature flag services for mobile apps`).
3. Optionally adjust:

    * LLM model (dropdown)
    * Temperature (slider)
4. Click **Run research** to start the agent.
5. Progress, extracted tools, and company results will appear live.
6. Download the final JSON results using the download button.
## Notes
* The agent uses **Firecrawl API** to scrape web pages. Make sure your API key is valid.
* The default LLM model is `claude-3-haiku-20240307`, but you can choose others available in your environment.
* The app streams results in real-time, so you can monitor progress without waiting for the entire workflow to finish.
## License
MIT License © 2025 \[Pritam Chakraborty]
## Contact
For questions, feature requests, or contributions, open an issue or reach out via email: [pritam.official2002@gmail.com](mailto:pritam.official2002@gmail.com)
