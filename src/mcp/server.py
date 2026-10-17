"""
Servidor y Manejador de Protocolo de Contexto de Modelo (MCP - Model Context Protocol).
Permite que IDEs inteligentes (Cursor, Claude Desktop, Antigravity) o agentes externos
interactúen con Aureon AI, su motor matemático SymPy y la base de datos Supabase pgvector.
"""
import json
import sys
from typing import Dict, Any, List, Optional
from src.math_engine.registry import engine_registry
from src.database.supabase_client import supabase_manager
from src.ai.gemini_tutor import gemini_tutor
from src.knowledge.universities import list_all_pedagogies, get_university_pedagogy

# Definición de Herramientas MCP
MCP_TOOLS = [
    {
        "name": "solve_equation_symbolic",
        "description": "Resuelve analítica y determinísticamente cualquier ecuación matemática, EDO o integral con SymPy (0% alucinación).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "equation": {"type": "string", "description": "Expresión o ecuación matemática (ej: 'diff(y(x), x, 2) + 4*y(x) = sin(x)')"},
                "university_lens": {"type": "string", "enum": ["stanford", "moscow", "tsinghua", "harvard", "polytechnique"], "description": "Lente pedagógico universitario"}
            },
            "required": ["equation"]
        }
    },
    {
        "name": "query_engineering_knowledge",
        "description": "Búsqueda vectorial semántica en Supabase pgvector sobre teoremas y aplicaciones en IA, Robótica, Sistemas Operativos y Mecánica.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string", "description": "Concepto o duda técnica a buscar"},
                "discipline": {"type": "string", "description": "Disciplina opcional: 'Inteligencia Artificial', 'Robótica', 'Sistemas Operativos', 'Mecánica'"},
                "top_k": {"type": "integer", "default": 3}
            },
            "required": ["query"]
        }
    },
    {
        "name": "log_study_session_pomodoro",
        "description": "Registra un bloque de estudio de las 10+ horas diarias de Darlyn David en Supabase Cloud.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "minutes": {"type": "integer", "description": "Minutos estudiados (ej: 50)"},
                "focus_area": {"type": "string", "enum": ["ai", "robotics", "os", "mechanics", "math_foundations"]},
                "topic": {"type": "string", "description": "Tema específico abordado"},
                "notes": {"type": "string", "description": "Notas o resumen del bloque"}
            },
            "required": ["minutes", "focus_area"]
        }
    },
    {
        "name": "create_study_flashcard",
        "description": "Crea una tarjeta de estudio con algoritmo de repetición espaciada SuperMemo SM-2 en Supabase Cloud.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "subject_id": {"type": "string", "description": "ID de la materia (ej: 'ai_deep_learning')"},
                "title": {"type": "string", "description": "Pregunta o teorema de la tarjeta"},
                "content": {"type": "string", "description": "Respuesta detallada y demostración"},
                "mastery_level": {"type": "integer", "minimum": 1, "maximum": 5}
            },
            "required": ["subject_id", "title", "content"]
        }
    },
    {
        "name": "solve_parametric_archetype",
        "description": "Calcula el paso a paso numérico y visual de uno de los 14 arquetipos de ingeniería de Aureon.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "archetype_id": {"type": "string", "description": "ID del arquetipo (ej: 'ai_backprop_grad', 'robotics_2d_kinematics', 'os_paging_translation')"},
                "params": {"type": "object", "description": "Parámetros numéricos específicos"}
            },
            "required": ["archetype_id"]
        }
    },
    {
        "name": "research_global_engineering_knowledge",
        "description": "Investiga conocimiento público de las mejores universidades del mundo (MIT, Stanford, MGU, Tsinghua), traduce al español con fórmulas KaTeX y guarda en Supabase pgvector.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Concepto o teorema a investigar (ej: 'Ecuaciones de Navier-Stokes', 'Filtro de Kalman')"},
                "university_preference": {"type": "string", "description": "mit, stanford, moscow, tsinghua, harvard, eth, polytechnique"},
                "discipline": {"type": "string", "description": "Disciplina de ingeniería"}
            },
            "required": ["topic"]
        }
    },
    {
        "name": "generate_notebook_study_artifact",
        "description": "Genera artefactos de estudio estilo NotebookLLM: guías de estudio, formularios de ecuaciones KaTeX, desafíos de examen o guiones de podcast a 2 voces.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "topic": {"type": "string", "description": "Tema del artefacto"},
                "source_content": {"type": "string", "description": "Contenido base de las fuentes"},
                "artifact_type": {"type": "string", "enum": ["study_guide", "equations_formulary", "exam_challenges", "faq_deep_dive", "audio_overview_script"]}
            },
            "required": ["topic", "source_content"]
        }
    },
    {
        "name": "ingest_academic_document",
        "description": "Ingesta notas de clase, transcripciones o syllabus en la base de datos vectorial de Supabase Cloud.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "title": {"type": "string", "description": "Título del apunte"},
                "content": {"type": "string", "description": "Texto del documento"},
                "discipline": {"type": "string", "description": "Rama de la ingeniería"},
                "university": {"type": "string", "description": "Institución o autor"}
            },
            "required": ["title", "content"]
        }
    }
]

# Definición de Recursos MCP
MCP_RESOURCES = [
    {
        "uri": "aureon://syllabus/carlos_cisneros_ai",
        "name": "Malla Curricular - Inteligencia Artificial",
        "description": "Plan formativo del Instituto Superior Tecnológico Carlos Cisneros para Darlyn David.",
        "mimeType": "application/json"
    },
    {
        "uri": "aureon://student/darlyn_progress",
        "name": "Progreso y Metas Diarias del Estudiante",
        "description": "Estadísticas acumuladas hoy de las 10 horas de estudio intensivo.",
        "mimeType": "application/json"
    }
]

# Definición de Prompts MCP
MCP_PROMPTS = [
    {
        "name": "socratic_deep_dive",
        "description": "Inicia un interrogatorio socrático profundo donde la IA pone a prueba la comprensión matemática del alumno.",
        "arguments": [
            {"name": "topic", "description": "Tema a profundizar (ej: Backpropagation, SVD, Paginación)", "required": True},
            {"name": "university", "description": "stanford, moscow, tsinghua, harvard", "required": False}
        ]
    },
    {
        "name": "feynman_technique_evaluator",
        "description": "El alumno explica un concepto con sus palabras y la IA evalúa lagunas conceptuales.",
        "arguments": [
            {"name": "student_explanation", "description": "Explicación formulada por el estudiante", "required": True}
        ]
    }
]

class McpProtocolHandler:
    """Manejador de mensajes MCP compatible con la especificación JSON-RPC 2.0."""

    @classmethod
    def handle_request(cls, request_dict: Dict[str, Any]) -> Dict[str, Any]:
        req_id = request_dict.get("id", 1)
        method = request_dict.get("method", "")
        params = request_dict.get("params", {})

        if method == "initialize":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "protocolVersion": "2024-11-05",
                    "serverInfo": {
                        "name": "aureon-mcp-server",
                        "version": "2.0.0"
                    },
                    "capabilities": {
                        "tools": {},
                        "resources": {},
                        "prompts": {}
                    }
                }
            }

        elif method == "tools/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"tools": MCP_TOOLS}
            }

        elif method == "tools/call":
            tool_name = params.get("name")
            args = params.get("arguments", {})
            call_result = cls.execute_tool(tool_name, args)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "content": [
                        {
                            "type": "text",
                            "text": json.dumps(call_result, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }

        elif method == "resources/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"resources": MCP_RESOURCES}
            }

        elif method == "resources/read":
            uri = params.get("uri", "")
            resource_data = cls.read_resource(uri)
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {
                    "contents": [
                        {
                            "uri": uri,
                            "mimeType": "application/json",
                            "text": json.dumps(resource_data, ensure_ascii=False, indent=2)
                        }
                    ]
                }
            }

        elif method == "prompts/list":
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "result": {"prompts": MCP_PROMPTS}
            }

        else:
            return {
                "jsonrpc": "2.0",
                "id": req_id,
                "error": {
                    "code": -32601,
                    "message": f"Método MCP '{method}' no soportado."
                }
            }

    @classmethod
    def execute_tool(cls, name: str, args: Dict[str, Any]) -> Any:
        if name == "solve_equation_symbolic":
            eq = args.get("equation", "")
            univ = args.get("university_lens", "stanford")
            return gemini_tutor.explain_custom_equation(eq, university_lens=univ)

        elif name == "query_engineering_knowledge":
            q = args.get("query", "")
            disc = args.get("discipline")
            top_k = args.get("top_k", 3)
            return supabase_manager.query_knowledge(query=q, discipline=disc, top_k=top_k)

        elif name == "log_study_session_pomodoro":
            mins = args.get("minutes", 50)
            area = args.get("focus_area", "ai")
            topic = args.get("topic", "Estudio intensivo")
            notes = args.get("notes", "")
            return supabase_manager.log_study_session(mins, area, topic, notes)

        elif name == "create_study_flashcard":
            subj = args.get("subject_id", "ai_foundations")
            title = args.get("title", "")
            content = args.get("content", "")
            mastery = args.get("mastery_level", 1)
            return supabase_manager.create_study_note(subj, None, title, content, mastery)

        elif name == "solve_parametric_archetype":
            arch_id = args.get("archetype_id", "baldor_quadratic_eq")
            solver = engine_registry.get_solver(arch_id)
            if not solver:
                return {"error": f"Arquetipo {arch_id} no existe"}
            user_params = args.get("params") or solver.default_params
            res = solver.solve(user_params)
            return res.model_dump()

        elif name == "research_global_engineering_knowledge":
            topic = args.get("topic", "")
            univ = args.get("university_preference")
            disc = args.get("discipline")
            return gemini_tutor.research_global_university_topic(topic, univ, disc)

        elif name == "generate_notebook_study_artifact":
            topic = args.get("topic", "")
            content = args.get("source_content", "")
            art_type = args.get("artifact_type", "study_guide")
            return gemini_tutor.generate_notebook_artifact(topic, content, art_type)

        elif name == "ingest_academic_document":
            doc = {
                "topic": args.get("title", "Apunte de Clase"),
                "content": args.get("content", ""),
                "discipline": args.get("discipline", "Ingeniería"),
                "university": args.get("university", "Apunte Personal"),
                "country": "Ecuador / Local",
                "formula_latex": r"\text{Notas de Estudio}",
                "pedagogical_style": "Documento Académico Ingestado",
                "engineering_application": "Material personalizado para I.S.T. Carlos Cisneros"
            }
            return supabase_manager.save_university_knowledge(doc)

        return {"error": f"Herramienta desconocida: {name}"}

    @classmethod
    def read_resource(cls, uri: str) -> Any:
        if uri == "aureon://syllabus/carlos_cisneros_ai":
            return {
                "institution": "Instituto Superior Tecnológico Carlos Cisneros",
                "student": "Darlyn David Tenelema Obando",
                "career": "Inteligencia Artificial",
                "level": "Tercer Nivel Tecnológico Superior",
                "modality": "En línea / Nocturna",
                "modules": [
                    {"code": "IA-101", "name": "Matemáticas y Álgebra Simbólica", "status": "Iniciado"},
                    {"code": "IA-102", "name": "Fundamentos de Machine Learning y Redes Neuronales", "status": "Iniciado"},
                    {"code": "IA-103", "name": "Sistemas Operativos y Cómputo Paralelo", "status": "Planificado"},
                    {"code": "IA-104", "name": "Robótica, Cinemática y Visión Artificial", "status": "Planificado"},
                    {"code": "IA-105", "name": "Mecánica Estructural y Dinámica", "status": "Planificado"}
                ]
            }
        elif uri == "aureon://student/darlyn_progress":
            return supabase_manager.get_study_stats_today()

        return {"error": "Recurso no encontrado"}

if __name__ == "__main__":
    # Modo servidor MCP por stdio (para conectar a Cursor / Claude Desktop / Antigravity)
    for line in sys.stdin:
        if not line.strip():
            continue
        try:
            req = json.loads(line)
            resp = McpProtocolHandler.handle_request(req)
            sys.stdout.write(json.dumps(resp) + "\n")
            sys.stdout.flush()
        except Exception as e:
            err_resp = {"jsonrpc": "2.0", "id": None, "error": {"code": -32700, "message": str(e)}}
            sys.stdout.write(json.dumps(err_resp) + "\n")
            sys.stdout.flush()
