from datetime import date
from crewai import Agent, Crew, Process, Task
from crewai.project import CrewBase, agent, crew, task, before_kickoff
from crewai.agents.agent_builder.base_agent import BaseAgent
from langchain_community.tools import DuckDuckGoSearchRun
from crewai.tools import tool
from youtube_transcript_api import YouTubeTranscriptApi
from trading_researcher.tools.local_tools import read_registro, list_reports, read_report
import re


@tool("DuckDuckGo Search")
def duckduckgo_search(query: str) -> str:
    """Busca información actualizada en internet usando DuckDuckGo."""
    return DuckDuckGoSearchRun().run(query)


@tool("YouTube Transcript")
def youtube_transcript(url: str) -> str:
    """Extrae la transcripción completa de un vídeo de YouTube dado su URL."""
    match = re.search(r"(?:v=|youtu\.be/)([A-Za-z0-9_-]{11})", url)
    if not match:
        return "URL de YouTube no válida."
    video_id = match.group(1)
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=["es", "en"])
        text = " ".join(entry["text"] for entry in fetched.to_raw_data())
        return text[:8000]
    except Exception as e:
        return f"No se pudo obtener la transcripción: {e}"
from typing import List


@CrewBase
class TradingResearcher:
    """Crew de investigación diaria de trading algorítmico."""

    agents: List[BaseAgent]
    tasks: List[Task]

    agents_config = "config/agents.yaml"
    tasks_config = "config/tasks.yaml"

    @before_kickoff
    def inject_fecha(self, inputs):
        inputs["fecha_hoy"] = date.today().isoformat()
        return inputs

    @agent
    def buscador(self) -> Agent:
        return Agent(
            config=self.agents_config["buscador"],  # type: ignore[index]
            tools=[duckduckgo_search, youtube_transcript],
            verbose=True,
        )

    @agent
    def analista(self) -> Agent:
        return Agent(
            config=self.agents_config["analista"],  # type: ignore[index]
            tools=[read_registro, list_reports, read_report],
            verbose=True,
        )

    @agent
    def risk_manager(self) -> Agent:
        return Agent(
            config=self.agents_config["risk_manager"],  # type: ignore[index]
            verbose=True,
        )

    @agent
    def reporter(self) -> Agent:
        return Agent(
            config=self.agents_config["reporter"],  # type: ignore[index]
            verbose=True,
        )

    @task
    def tarea_busqueda(self) -> Task:
        return Task(
            config=self.tasks_config["tarea_busqueda"],  # type: ignore[index]
        )

    @task
    def tarea_analisis(self) -> Task:
        return Task(
            config=self.tasks_config["tarea_analisis"],  # type: ignore[index]
        )

    @task
    def tarea_riesgo(self) -> Task:
        return Task(
            config=self.tasks_config["tarea_riesgo"],  # type: ignore[index]
        )

    @task
    def tarea_reporte(self) -> Task:
        return Task(
            config=self.tasks_config["tarea_reporte"],  # type: ignore[index]
        )

    @crew
    def crew(self) -> Crew:
        return Crew(
            agents=self.agents,
            tasks=self.tasks,
            process=Process.sequential,
            verbose=True,
        )
