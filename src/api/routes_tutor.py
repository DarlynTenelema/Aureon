"""
Router API para el Tutor Aureon Inteligente (Canvas de Explicación y Pedagogía).
Conexión con Gemini 3.1, SymPy, Supabase pgvector y pedagogías de Harvard, Stanford, MGU, Tsinghua y Polytechnique.
100% Persistencia en la Nube con Supabase Cloud.
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field
from typing import Optional, Dict, Any, List

from src.math_engine.registry import engine_registry
from src.database.supabase_client import supabase_manager
from src.knowledge.universities import list_all_pedagogies, get_university_pedagogy
from src.ai.gemini_tutor import gemini_tutor

router = APIRouter(prefix="/api/tutor", tags=["Aureon Tutor Inteligente"])

class TutorQuery(BaseModel):
    archetype_id: str
    step_number: Optional[int] = Field(None, description="Número del paso seleccionado en el canvas numérico")
    question_type: str = Field(..., description="Opciones: 'source_of_number', 'process_name', 'step_by_step', 'real_world_use', 'custom'")
    user_question: Optional[str] = Field(None, description="Pregunta específica o personalizada del usuario")
    params: Optional[Dict[str, Any]] = Field(default=None, description="Parámetros numéricos activos del ejercicio")
    university_lens: Optional[str] = Field("stanford", description="Lente pedagógico: stanford, moscow, tsinghua, harvard, polytechnique")

class CustomEquationQuery(BaseModel):
    equation: str = Field(..., description="Cualquier ecuación, EDO, integral o problema matemático")
    university_lens: Optional[str] = Field("stanford", description="Universidad a emular: stanford, moscow, tsinghua, harvard, polytechnique")
    user_notes: Optional[str] = Field(None, description="Notas o dudas específicas del alumno")

class RagSearchQuery(BaseModel):
    query: str
    university: Optional[str] = None
    discipline: Optional[str] = None
    top_k: Optional[int] = 3

class ResearchGlobalQuery(BaseModel):
    topic: str = Field(..., description="Tema científico o de ingeniería a investigar en universidades globales")
    university_preference: Optional[str] = Field(None, description="Universidad de preferencia: mit, stanford, moscow, tsinghua, harvard, eth, polytechnique")
    discipline: Optional[str] = Field(None, description="Disciplina de ingeniería: IA, Robótica, SO, Mecánica, Matemáticas")

class IngestSourceQuery(BaseModel):
    title: str = Field(..., description="Título del documento, apunte o artículo")
    content: str = Field(..., description="Texto o transcripción de la clase o syllabus")
    discipline: Optional[str] = Field("Ingeniería General", description="Disciplina asociada")
    university: Optional[str] = Field("Apunte Personal", description="Institución o autor")
    formula_latex: Optional[str] = Field(None, description="Fórmula representativa en LaTeX")

class NotebookArtifactQuery(BaseModel):
    topic: str = Field(..., description="Tema del artefacto")
    source_content: str = Field(..., description="Contenido de las fuentes a sintetizar")
    artifact_type: str = Field("study_guide", description="'study_guide', 'equations_formulary', 'exam_challenges', 'faq_deep_dive', 'audio_overview_script'")

class ChatSourcesQuery(BaseModel):
    query: str = Field(..., description="Pregunta del estudiante")
    source_ids: Optional[List[str]] = Field(default=None, description="IDs de fuentes activas")
    history: Optional[List[Dict[str, str]]] = Field(default=None, description="Historial de mensajes previos")

@router.get("/universities")
def get_universities():
    """Retorna las pedagogías universitarias internacionales soportadas por Aureon."""
    return list_all_pedagogies()

@router.post("/explain")
def explain_step(query: TutorQuery):
    """
    Endpoint del Tutor Aureon (Canvas Delgado).
    Responde con IA Gemini 3.1 y lente pedagógico universitario seleccionado.
    Persiste la interacción en Supabase Cloud.
    """
    solver = engine_registry.get_solver(query.archetype_id)
    if not solver:
        raise HTTPException(status_code=404, detail=f"Arquetipo '{query.archetype_id}' no encontrado.")

    active_params = query.params if query.params else solver.default_params
    result = solver.solve(active_params)

    # Buscar el paso relevante
    selected_step_data = None
    if query.step_number is not None:
        for s in result.steps:
            if s.step_number == query.step_number:
                selected_step_data = s.model_dump()
                break

    # Consultar al motor de IA con el lente universitario
    explanation = gemini_tutor.answer_interactive_query(
        archetype_title=result.title,
        step_number=query.step_number,
        question_type=query.question_type,
        user_question=query.user_question,
        active_params=active_params,
        step_data=selected_step_data,
        university_lens=query.university_lens or "stanford"
    )

    # Registrar la interacción en Supabase Cloud
    supabase_manager.log_tutor_interaction(
        archetype_id=query.archetype_id,
        step_number=query.step_number,
        question_type=query.question_type,
        user_question=query.user_question or query.question_type,
        tutor_explanation=explanation
    )

    return {
        "archetype_id": query.archetype_id,
        "step_number": query.step_number,
        "question_type": query.question_type,
        "university_lens": query.university_lens,
        "explanation": explanation
    }

@router.post("/solve-custom")
def solve_custom_equation(query: CustomEquationQuery):
    """
    Solucionador Universal IA para CUALQUIER ecuación matemática o problema de ingeniería.
    Combina cálculo determinista SymPy + IA Gemini 3.1 + RAG Universitario + Supabase Cloud.
    """
    if not query.equation or not query.equation.strip():
        raise HTTPException(status_code=400, detail="Debes proporcionar una ecuación o expresión matemática.")

    result = gemini_tutor.explain_custom_equation(
        equation_input=query.equation.strip(),
        university_lens=query.university_lens or "stanford",
        user_notes=query.user_notes
    )
    return result

@router.post("/rag-search")
def search_rag(query: RagSearchQuery):
    """Búsqueda semántica en la base de datos vectorial de conocimientos universitarios (pgvector)."""
    results = supabase_manager.query_knowledge(
        query=query.query,
        university=query.university,
        discipline=query.discipline,
        top_k=query.top_k or 3
    )
    return {
        "query": query.query,
        "source": "supabase_pgvector" if supabase_manager.is_connected() else "high_precision_vector_engine",
        "results": results
    }

@router.post("/sync-supabase")
def sync_supabase():
    """Siembra y sincroniza todas las áreas, materias y conocimientos en Supabase Cloud."""
    res = supabase_manager.seed_supabase_all()
    return res

@router.get("/status")
def tutor_status():
    """Retorna el estado de conexión de los subsistemas de IA y Base de Datos."""
    return {
        "gemini_model": gemini_tutor.model_name,
        "gemini_active": bool(gemini_tutor._call_gemini("Ping", "Responde Pong") is not None),
        "supabase_connected": supabase_manager.is_connected(),
        "supabase_vector_enabled": supabase_manager.enabled,
        "available_universities": [p["name"] for p in list_all_pedagogies()]
    }

# ====================================================================
# ENDPOINTS NOTEBOOKLLM & INVESTIGACIÓN UNIVERSITARIA GLOBAL
# ====================================================================

@router.post("/research-global")
def research_global(query: ResearchGlobalQuery):
    """
    Investiga conocimiento público de las mejores universidades del mundo
    (MIT, Stanford, MGU Landau, Tsinghua, ETH, Polytechnique),
    lo traduce al español con fórmulas KaTeX y lo persiste en Supabase pgvector.
    """
    if not query.topic or not query.topic.strip():
        raise HTTPException(status_code=400, detail="Debes especificar un tema a investigar.")

    dossier = gemini_tutor.research_global_university_topic(
        topic=query.topic.strip(),
        university_preference=query.university_preference,
        discipline=query.discipline
    )
    return dossier

@router.post("/ingest-custom-source")
def ingest_custom_source(query: IngestSourceQuery):
    """Ingesta apuntes de clase, syllabus o transcripciones del alumno en Supabase pgvector."""
    if not query.content or not query.content.strip():
        raise HTTPException(status_code=400, detail="El contenido a ingestar no puede estar vacío.")

    doc = {
        "topic": query.title.strip(),
        "content": query.content.strip(),
        "discipline": query.discipline or "Ingeniería General",
        "university": query.university or "Apunte Personal",
        "country": "Ecuador / Local",
        "formula_latex": query.formula_latex or r"\text{Notas de Estudio}",
        "pedagogical_style": "Documento Académico Ingestado",
        "engineering_application": "Material de estudio personalizado para el Instituto Carlos Cisneros"
    }
    saved = supabase_manager.save_university_knowledge(doc)
    return {
        "success": True,
        "message": f"Documento '{query.title}' ingestado en Supabase Cloud con éxito.",
        "source": saved
    }

@router.get("/sources")
def get_sources(discipline: Optional[str] = None):
    """Lista todas las fuentes universitarias y documentos ingestados en Supabase Cloud."""
    sources = supabase_manager.get_all_university_sources(discipline=discipline)
    return {"count": len(sources), "sources": sources}

@router.delete("/sources/{source_id}")
def delete_source(source_id: str):
    """Elimina una fuente o apunte de Supabase Cloud."""
    ok = supabase_manager.delete_university_knowledge(source_id)
    return {"success": ok, "deleted_id": source_id}

@router.post("/generate-notebook-artifact")
def generate_notebook_artifact(query: NotebookArtifactQuery):
    """
    Genera artefactos de estudio estilo NotebookLLM:
    - 'study_guide': Guía de estudio exhaustiva
    - 'equations_formulary': Formulario maestro de ecuaciones con KaTeX
    - 'exam_challenges': Desafíos y exámenes universitarios
    - 'faq_deep_dive': FAQ técnico y errores comunes
    - 'audio_overview_script': Guión de podcast socrático a 2 voces
    """
    artifact = gemini_tutor.generate_notebook_artifact(
        topic=query.topic,
        source_content=query.source_content,
        artifact_type=query.artifact_type
    )
    return artifact

@router.post("/chat-sources")
def chat_sources(query: ChatSourcesQuery):
    """Chat fundamentado en las fuentes universitarias ingestadas (grounded Q&A)."""
    if not query.query or not query.query.strip():
        raise HTTPException(status_code=400, detail="La pregunta no puede estar vacía.")

    res = gemini_tutor.chat_with_sources(
        query=query.query.strip(),
        source_ids=query.source_ids,
        history=query.history
    )
    return res
