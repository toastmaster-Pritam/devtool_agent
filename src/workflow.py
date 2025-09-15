# src/workflow.py
from typing import Dict, Any, Callable, Optional, List
from langgraph.graph import StateGraph, END
from langchain_anthropic import ChatAnthropic
from langchain_core.messages import HumanMessage, SystemMessage
from .models import ResearchState, CompanyInfo, CompanyAnalysis
from .firecrawl import FirecrawlService
from .prompts import DeveloperToolsPrompts


ProgressCallback = Optional[Callable[[Dict[str, Any]], None]]


class Workflow:
    def __init__(self, progress_callback: ProgressCallback = None):
        """
        progress_callback: optional function called with dict events:
          - {'phase': 'extract_tools_start', 'query': ...}
          - {'phase': 'extracted_tools', 'tools': [...]}
          - {'phase': 'research_tool_start', 'tool': '...'}
          - {'phase': 'company_ready', 'company': {...}}  (company as dict)
          - {'phase': 'analysis_start'}
          - {'phase': 'analysis_done', 'analysis': '...'}
          - {'phase': 'final', 'final_state': {...}}
          - {'phase': 'error', 'error': '...'}
        """
        self.firecrawl = FirecrawlService()
        self.llm = ChatAnthropic(model="claude-3-haiku-20240307", temperature=0.1)
        self.prompts = DeveloperToolsPrompts()
        self._progress_callback = progress_callback
        self.workflow = self._build_workflow()

    def set_progress_callback(self, cb: ProgressCallback):
        self._progress_callback = cb

    def _emit(self, event: Dict[str, Any]):
        try:
            if callable(self._progress_callback):
                self._progress_callback(event)
        except Exception as e:
            # don't interrupt the run if callback errors
            print("Progress callback error:", e)

    def _build_workflow(self):
        graph = StateGraph(ResearchState)
        graph.add_node("extract_tools", self._extract_tools_step)
        graph.add_node("research", self._research_step)
        graph.add_node("analyze", self._analyze_step)
        graph.set_entry_point("extract_tools")
        graph.add_edge("extract_tools", "research")
        graph.add_edge("research", "analyze")
        graph.add_edge("analyze", END)
        return graph.compile()

    def _extract_tools_step(self, state: ResearchState) -> Dict[str, Any]:
        try:
            self._emit({"phase": "extract_tools_start", "query": state.query})
            article_query = f"{state.query} tools comparison best alternatives"
            search_results = self.firecrawl.search_companies(article_query, num_results=3)

            all_content = ""
            if search_results and getattr(search_results, "data", None):
                for result in search_results.data:
                    url = result.get("url", "")
                    scraped = self.firecrawl.scrape_company_pages(url)
                    if scraped and getattr(scraped, "markdown", None):
                        all_content += scraped.markdown[:1500] + "\n\n"

            messages = [
                SystemMessage(content=self.prompts.TOOL_EXTRACTION_SYSTEM),
                HumanMessage(content=self.prompts.tool_extraction_user(state.query, all_content))
            ]

            response = self.llm.invoke(messages)
            tool_names = [
                name.strip()
                for name in response.content.strip().split("\n")
                if name.strip()
            ]
            self._emit({"phase": "extracted_tools", "tools": tool_names})
            return {"extracted_tools": tool_names}
        except Exception as e:
            self._emit({"phase": "error", "error": f"extract_tools failed: {e}"})
            print(e)
            return {"extracted_tools": []}

    def _analyze_company_content(self, company_name: str, content: str) -> CompanyAnalysis:
        try:
            structured_llm = self.llm.with_structured_output(CompanyAnalysis)

            messages = [
                SystemMessage(content=self.prompts.TOOL_ANALYSIS_SYSTEM),
                HumanMessage(content=self.prompts.tool_analysis_user(company_name, content))
            ]

            analysis = structured_llm.invoke(messages)
            return analysis
        except Exception as e:
            print(e)
            return CompanyAnalysis(
                pricing_model="Unknown",
                is_open_source=None,
                tech_stack=[],
                description="Failed",
                api_available=None,
                language_support=[],
                integration_capabilities=[],
            )

    def _research_step(self, state: ResearchState) -> Dict[str, Any]:
        try:
            extracted_tools = getattr(state, "extracted_tools", []) or []

            if not extracted_tools:
                self._emit({"phase": "research_fallback", "query": state.query})
                search_results = self.firecrawl.search_companies(state.query, num_results=4)
                tool_names = [
                    result.get("metadata", {}).get("title", "Unknown")
                    for result in (getattr(search_results, "data", []) or [])
                ]
            else:
                tool_names = extracted_tools[:4]

            self._emit({"phase": "research_start", "tools": tool_names})

            companies: List[CompanyInfo] = []
            for tool_name in tool_names:
                self._emit({"phase": "research_tool_start", "tool": tool_name})
                tool_search_results = self.firecrawl.search_companies(tool_name + " official site", num_results=1)

                if not tool_search_results or not getattr(tool_search_results, "data", None):
                    # skip if no results
                    continue

                result = tool_search_results.data[0]
                url = result.get("url", "")

                company = CompanyInfo(
                    name=tool_name,
                    description=result.get("markdown", ""),
                    website=url,
                    tech_stack=[],
                    competitors=[]
                )

                scraped = self.firecrawl.scrape_company_pages(url)
                if scraped and getattr(scraped, "markdown", None):
                    content = scraped.markdown
                    analysis = self._analyze_company_content(company.name, content)

                    company.pricing_model = analysis.pricing_model
                    company.is_open_source = analysis.is_open_source
                    company.tech_stack = analysis.tech_stack
                    company.description = analysis.description
                    company.api_available = analysis.api_available
                    company.language_support = analysis.language_support
                    company.integration_capabilities = analysis.integration_capabilities

                companies.append(company)
                # emit the company as soon as it's ready
                try:
                    self._emit({"phase": "company_ready", "company": company.dict()})
                except Exception:
                    # fallback if company.dict() fails
                    self._emit({"phase": "company_ready", "company": vars(company)})

            self._emit({"phase": "research_done", "count": len(companies)})
            return {"companies": companies}
        except Exception as e:
            self._emit({"phase": "error", "error": f"research failed: {e}"})
            print(e)
            return {"companies": []}

    def _analyze_step(self, state: ResearchState) -> Dict[str, Any]:
        try:
            self._emit({"phase": "analysis_start"})
            company_data = ", ".join([
                company.json() for company in state.companies
            ])

            messages = [
                SystemMessage(content=self.prompts.RECOMMENDATIONS_SYSTEM),
                HumanMessage(content=self.prompts.recommendations_user(state.query, company_data))
            ]

            response = self.llm.invoke(messages)
            self._emit({"phase": "analysis_done", "analysis": response.content})
            return {"analysis": response.content}
        except Exception as e:
            self._emit({"phase": "error", "error": f"analysis failed: {e}"})
            print(e)
            return {"analysis": "Analysis failed"}

    def run(self, query: str, progress_callback: ProgressCallback = None) -> ResearchState:
        """
        Run the workflow. Optionally pass progress_callback here instead of in ctor.
        """
        if progress_callback:
            self.set_progress_callback(progress_callback)

        try:
            initial_state = ResearchState(query=query)
            final_state = self.workflow.invoke(initial_state)
            # emit final state dict so callers can persist or inspect
            try:
                self._emit({"phase": "final", "final_state": final_state})
            except Exception:
                pass
            return ResearchState(**final_state)
        except Exception as e:
            self._emit({"phase": "error", "error": str(e)})
            raise
        finally:
            # avoid keeping references to external callbacks longer than needed
            self._progress_callback = None
