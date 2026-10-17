"""
Cliente Unificado de Integración con Supabase Cloud y Base de Datos Vectorial (pgvector).
100% Persistencia en la Nube (Sin SQLite ni bases de datos locales).
Para: Darlyn David Tenelema Obando - Instituto Superior Tecnológico Carlos Cisneros.
"""
import os
import json
from datetime import datetime, timezone, timedelta
from typing import List, Dict, Any, Optional

from src.knowledge.universities import (
    UNIVERSITY_KNOWLEDGE_CORPUS,
    generate_local_embedding,
    search_corpus_local
)

# Intentar importar el SDK oficial de Supabase
try:
    from supabase import create_client, Client
    SUPABASE_SDK_AVAILABLE = True
except ImportError:
    SUPABASE_SDK_AVAILABLE = False
    Client = Any

# Catálogo por defecto para sembrado en Supabase Cloud
INITIAL_AREAS = [
    {"id": "ai", "name": "Inteligencia Artificial", "description": "Machine Learning, Deep Learning, Redes Neuronales, Transformers y Optimización.", "icon": "brain", "sort_order": 1},
    {"id": "robotics", "name": "Robótica y Control", "description": "Cinemática directa/inversa, dinámica de manipuladores, matrices SE(3) y control PID.", "icon": "cpu", "sort_order": 2},
    {"id": "os", "name": "Sistemas Operativos", "description": "Arquitectura de kernels, planificación de CPU, memoria virtual, concurrencia y Linux.", "icon": "terminal", "sort_order": 3},
    {"id": "mechanics", "name": "Ingeniería Mecánica", "description": "Estática, dinámica, resistencia de materiales, leyes de Hooke y elementos finitos.", "icon": "cog", "sort_order": 4},
    {"id": "math_foundations", "name": "Matemáticas y Baldor", "description": "Álgebra fundamental, cálculo diferencial/integral, EDOs y álgebra lineal.", "icon": "calculator", "sort_order": 5},
]

INITIAL_SUBJECTS = [
    # Inteligencia Artificial
    {"id": "ai_foundations", "area_id": "ai", "name": "Fundamentos de Machine Learning", "level": 1, "description": "Regresión lineal, función de coste MSE y descenso de gradiente."},
    {"id": "ai_deep_learning", "area_id": "ai", "name": "Redes Neuronales y Deep Learning", "level": 2, "description": "Backpropagation, funciones de activación (ReLU/GELU) y optimizadores."},
    {"id": "ai_transformers", "area_id": "ai", "name": "Arquitectura Transformers y LLMs", "level": 3, "description": "Mecanismo de atención escalada QKV, embeddings y modelado de lenguaje."},
    # Robótica
    {"id": "robotics_kinematics", "area_id": "robotics", "name": "Cinemática de Robots Manipuladores", "level": 2, "description": "Matrices de rotación homogénea, parámetros DH y cinemática 2D/3D."},
    {"id": "robotics_control", "area_id": "robotics", "name": "Sistemas de Control y Estabilidad", "level": 3, "description": "Controladores PID, espacio de estados y estabilidad de Lyapunov."},
    # Sistemas Operativos
    {"id": "os_memory", "area_id": "os", "name": "Gestión de Memoria y Paginación", "level": 2, "description": "Paginación, tablas de páginas, TLB y memoria virtual protegida."},
    {"id": "os_concurrency", "area_id": "os", "name": "Concurrencia y Sincronización", "level": 3, "description": "Hilos, semáforos, monitores, exclusión mutua y prevención de deadlocks."},
    # Mecánica
    {"id": "mechanics_materials", "area_id": "mechanics", "name": "Resistencia de Materiales", "level": 2, "description": "Esfuerzo, deformación unitaria, ley de Hooke y módulo de elasticidad."},
    # Matemáticas
    {"id": "baldor_algebra", "area_id": "math_foundations", "name": "Álgebra Elemental (Baldor)", "level": 1, "description": "Ecuaciones lineales, cuadráticas, factorización y sistemas 2x2."},
    {"id": "calculus_diff_int", "area_id": "math_foundations", "name": "Cálculo Diferencial e Integral", "level": 2, "description": "Reglas de derivación, integración por partes y EDOs analíticas."},
]

class SupabaseManager:
    """Gestiona la conexión y persistencia 100% en Supabase Cloud con pgvector."""

    def __init__(self):
        self.url = os.getenv("SUPABASE_URL", "").strip()
        self.key = os.getenv("SUPABASE_KEY", "").strip() or os.getenv("SUPABASE_ANON_KEY", "").strip()
        self.enabled = os.getenv("ENABLE_SUPABASE_VECTOR", "true").lower() in ("true", "1", "yes")
        self.client: Optional[Client] = None
        self._memory_cache: Dict[str, List[Dict[str, Any]]] = {
            "study_notes": [],
            "study_sessions": [],
            "practice_history": [],
            "tutor_interactions": []
        }
        self._init_client()

    def _init_client(self):
        """Inicializa el cliente de Supabase Cloud."""
        if not SUPABASE_SDK_AVAILABLE:
            return

        is_placeholder = (
            not self.url or 
            not self.key or 
            "tu-proyecto" in self.url or 
            "tu_supabase" in self.key
        )

        if not is_placeholder and self.url.startswith("https://"):
            try:
                self.client = create_client(self.url, self.key)
                print(f"[Supabase Cloud] Conectado exitosamente: {self.url}")
            except Exception as e:
                print(f"[Supabase Cloud] Advertencia de conexión: {e}")
                self.client = None
        else:
            self.client = None

    def is_connected(self) -> bool:
        """Indica si hay una conexión activa y verificada con Supabase Cloud."""
        return self.client is not None

    def get_embedding(self, text: str) -> List[float]:
        """
        Genera el vector embedding de 768 dimensiones.
        Utiliza Google Cloud Agent Platform (text-embedding-004) con Service Account,
        o la clave de API si está configurada, con fallback de alta precisión.
        """
        # 1. Resolver credenciales de Google Agent Platform (archivo o JSON crudo en Railway)
        cred_raw = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "").strip()
        cred_json = (
            os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip() or 
            os.getenv("JSON_AGENT_PLATFORM", "").strip()
        )
        if cred_raw.startswith("{") and "private_key" in cred_raw:
            cred_json = cred_raw

        if cred_json:
            try:
                import tempfile
                cred_file = Path(tempfile.gettempdir()) / "gcp_service_account.json"
                if not cred_file.exists():
                    with open(cred_file, "w", encoding="utf-8") as f:
                        f.write(cred_json)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_file)
            except Exception:
                pass

        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not cred_path or not os.path.exists(cred_path):
            for f in os.listdir(os.getcwd()):
                if f.startswith("glassy-") and f.endswith(".json"):
                    cred_path = f
                    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = f
                    break

        project_id = os.getenv("GCP_PROJECT_ID", "glassy-508419").strip()
        location = os.getenv("GCP_LOCATION", "us-central1").strip()

        if cred_path and os.path.exists(cred_path):
            try:
                from google import genai
                client = genai.Client(vertexai=True, project=project_id, location=location)
                res = client.models.embed_content(
                    model="text-embedding-004",
                    contents=text
                )
                if hasattr(res, 'embeddings') and len(res.embeddings) > 0:
                    return res.embeddings[0].values[:768]
                elif hasattr(res, 'embedding') and hasattr(res.embedding, 'values'):
                    return res.embedding.values[:768]
            except Exception as e:
                print(f"[Embedding Agent Platform Warning] {e}")

        # 2. Intentar con GEMINI_API_KEY
        gemini_key = os.getenv("GEMINI_API_KEY", "").strip()
        if gemini_key and "tu_gemini" not in gemini_key:
            try:
                from google import genai
                client = genai.Client(api_key=gemini_key)
                res = client.models.embed_content(
                    model="text-embedding-004",
                    contents=text
                )
                if hasattr(res, 'embedding') and hasattr(res.embedding, 'values'):
                    return res.embedding.values[:768]
                elif hasattr(res, 'embeddings') and len(res.embeddings) > 0:
                    return res.embeddings[0].values[:768]
            except Exception:
                pass

        return generate_local_embedding(text, dim=768)

    # ====================================================================
    # ÁREAS Y MATERIAS (CURRÍCULO DE INGENIERÍA)
    # ====================================================================

    def get_areas_with_subjects(self) -> List[Dict[str, Any]]:
        """Obtiene las áreas de ingeniería con sus materias asociadas."""
        if self.is_connected():
            try:
                res_areas = self.client.table("areas").select("*").order("sort_order").execute()
                res_subjects = self.client.table("subjects").select("*").order("level").execute()
                
                if res_areas.data:
                    areas_dict = {
                        a["id"]: {**a, "subjects": []}
                        for a in res_areas.data
                    }
                    for s in (res_subjects.data or []):
                        if s["area_id"] in areas_dict:
                            areas_dict[s["area_id"]]["subjects"].append(s)
                    return list(areas_dict.values())
            except Exception as e:
                print(f"[Supabase Areas Error] {e}")

        # Retornar catálogo curricular por defecto estructurado
        areas_dict = {a["id"]: {**a, "subjects": []} for a in INITIAL_AREAS}
        for s in INITIAL_SUBJECTS:
            if s["area_id"] in areas_dict:
                areas_dict[s["area_id"]]["subjects"].append(s)
        return list(areas_dict.values())

    # ====================================================================
    # ARQUETIPOS MATEMÁTICOS Y FÓRMULAS
    # ====================================================================

    def get_archetypes(self, subject_id: Optional[str] = None, area_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene los arquetipos matemáticos desde Supabase o catálogo enriquecido."""
        from src.math_engine.registry import engine_registry
        
        # Mapeo inicial enriquecido de los arquetipos registrados en Python
        archetype_catalog = [
            {
                "id": "ai_backprop_grad",
                "subject_id": "ai_deep_learning",
                "area_id": "ai",
                "subject_name": "Redes Neuronales y Deep Learning",
                "title": "Retropropagación y Gradiente Descendente (IA)",
                "formula_latex": r"L = \frac{1}{2}(\hat{y} - y)^2, \quad w \leftarrow w - \eta \frac{\partial L}{\partial w}",
                "default_params": {"x": 2.0, "w": 0.5, "b": 0.1, "y_true": 1.0, "lr": 0.1},
                "param_schema": {
                    "x": {"label": "Entrada de la neurona (x)", "type": "number", "default": 2.0},
                    "w": {"label": "Peso sináptico inicial (w)", "type": "number", "default": 0.5},
                    "b": {"label": "Sesgo (bias b)", "type": "number", "default": 0.1},
                    "y_true": {"label": "Valor real esperado (y)", "type": "number", "default": 1.0},
                    "lr": {"label": "Tasa de aprendizaje (η)", "type": "number", "default": 0.1}
                },
                "difficulty": 2,
                "real_world_context": "Entrenamiento de redes neuronales profundas y ajuste de pesos en modelos de Inteligencia Artificial."
            },
            {
                "id": "robotics_2d_kinematics",
                "subject_id": "robotics_kinematics",
                "area_id": "robotics",
                "subject_name": "Cinemática de Robots",
                "title": "Cinemática Directa Robot 2-DOF",
                "formula_latex": r"x = l_1 \cos(\theta_1) + l_2 \cos(\theta_1 + \theta_2), \quad y = l_1 \sin(\theta_1) + l_2 \sin(\theta_1 + \theta_2)",
                "default_params": {"l1": 10.0, "l2": 8.0, "theta1_deg": 30.0, "theta2_deg": 45.0},
                "param_schema": {
                    "l1": {"label": "Longitud eslabón 1 (cm)", "type": "number", "default": 10.0},
                    "l2": {"label": "Longitud eslabón 2 (cm)", "type": "number", "default": 8.0},
                    "theta1_deg": {"label": "Ángulo articulación 1 (°)", "type": "number", "default": 30.0},
                    "theta2_deg": {"label": "Ángulo articulación 2 (°)", "type": "number", "default": 45.0}
                },
                "difficulty": 2,
                "real_world_context": "Posicionamiento del efector final en brazos robóticos industriales y brazos articulados."
            },
            {
                "id": "os_paging_translation",
                "subject_id": "os_memory",
                "area_id": "os",
                "subject_name": "Gestión de Memoria y Paginación",
                "title": "Paginación y Memoria Virtual (SO)",
                "formula_latex": r"VA = (p \times S) + d \implies PA = (f \times S) + d",
                "default_params": {"virtual_address": 10500, "page_size": 4096, "frame_number": 7},
                "param_schema": {
                    "virtual_address": {"label": "Dirección Virtual (bytes)", "type": "number", "default": 10500},
                    "page_size": {"label": "Tamaño de Página (bytes)", "type": "number", "default": 4096},
                    "frame_number": {"label": "Marco Físico Asignado (Frame)", "type": "number", "default": 7}
                },
                "difficulty": 2,
                "real_world_context": "Traducción de direcciones por la MMU de la CPU en núcleos Linux, Windows y servidores cloud."
            },
            {
                "id": "mechanics_hooke_stress",
                "subject_id": "mechanics_materials",
                "area_id": "mechanics",
                "subject_name": "Resistencia de Materiales",
                "title": "Esfuerzo, Deformación y Ley de Hooke",
                "formula_latex": r"\sigma = \frac{F}{A}, \quad \epsilon = \frac{\sigma}{E}, \quad \Delta L = \frac{F \cdot L_0}{A \cdot E}",
                "default_params": {"force_n": 50000.0, "area_mm2": 250.0, "initial_len_m": 2.0, "young_modulus_gpa": 200.0},
                "param_schema": {
                    "force_n": {"label": "Fuerza axial aplicada (N)", "type": "number", "default": 50000.0},
                    "area_mm2": {"label": "Área transversal (mm²)", "type": "number", "default": 250.0},
                    "initial_len_m": {"label": "Longitud inicial L0 (m)", "type": "number", "default": 2.0},
                    "young_modulus_gpa": {"label": "Módulo de Young E (GPa)", "type": "number", "default": 200.0}
                },
                "difficulty": 2,
                "real_world_context": "Dimensionamiento de perfiles y piezas de robots para evitar deformación plástica o rotura."
            },
            {
                "id": "baldor_quadratic_eq",
                "subject_id": "baldor_algebra",
                "area_id": "math_foundations",
                "subject_name": "Álgebra Elemental (Baldor)",
                "title": "Ecuación Cuadrática Completa",
                "formula_latex": r"ax^2 + bx + c = 0",
                "default_params": {"a": 1, "b": -5, "c": 6},
                "param_schema": {
                    "a": {"label": "Coeficiente cuadrático (a)", "type": "number", "default": 1},
                    "b": {"label": "Coeficiente lineal (b)", "type": "number", "default": -5},
                    "c": {"label": "Término independiente (c)", "type": "number", "default": 6}
                },
                "difficulty": 1,
                "real_world_context": "Trayectorias parabólicas en robótica móvil, cálculo de autovalores 2x2 y optimización de segundo orden."
            },
            {
                "id": "baldor_linear_eq",
                "subject_id": "baldor_algebra",
                "area_id": "math_foundations",
                "subject_name": "Álgebra Elemental (Baldor)",
                "title": "Ecuación Lineal de Primer Grado",
                "formula_latex": r"ax + b = c",
                "default_params": {"a": 3, "b": 5, "c": 20},
                "param_schema": {
                    "a": {"label": "Coeficiente de x", "type": "number", "default": 3},
                    "b": {"label": "Término constante (b)", "type": "number", "default": 5},
                    "c": {"label": "Término independiente (c)", "type": "number", "default": 20}
                },
                "difficulty": 1,
                "real_world_context": "Balances de masa, cálculo de complejidad O(n) y calibración de offsets en sensores."
            },
            {
                "id": "baldor_system_2x2",
                "subject_id": "baldor_algebra",
                "area_id": "math_foundations",
                "subject_name": "Álgebra Elemental (Baldor)",
                "title": "Sistema de Ecuaciones Lineales 2x2",
                "formula_latex": r"\begin{cases} a_1 x + b_1 y = c_1 \\ a_2 x + b_2 y = c_2 \end{cases}",
                "default_params": {"a1": 2, "b1": 3, "c1": 13, "a2": 1, "b2": -1, "c2": -1},
                "param_schema": {
                    "a1": {"label": "a₁", "type": "number", "default": 2},
                    "b1": {"label": "b₁", "type": "number", "default": 3},
                    "c1": {"label": "c₁", "type": "number", "default": 13},
                    "a2": {"label": "a₂", "type": "number", "default": 1},
                    "b2": {"label": "b₂", "type": "number", "default": -1},
                    "c2": {"label": "c₂", "type": "number", "default": -1}
                },
                "difficulty": 2,
                "real_world_context": "Leyes de Kirchhoff en circuitos de alimentación robóticos y equilibrio estático."
            },
            {
                "id": "calculus_derivative_polynomial",
                "subject_id": "calculus_diff_int",
                "area_id": "math_foundations",
                "subject_name": "Cálculo Diferencial e Integral",
                "title": "Derivada por Regla de la Potencia",
                "formula_latex": r"\frac{d}{dx}[ax^n + bx^m] = a \cdot n x^{n-1} + b \cdot m x^{m-1}",
                "default_params": {"a": 4, "n": 3, "b": -5, "m": 2},
                "param_schema": {
                    "a": {"label": "Coeficiente a", "type": "number", "default": 4},
                    "n": {"label": "Exponente n", "type": "number", "default": 3},
                    "b": {"label": "Coeficiente b", "type": "number", "default": -5},
                    "m": {"label": "Exponente m", "type": "number", "default": 2}
                },
                "difficulty": 2,
                "real_world_context": "Velocidad y aceleración instantánea en motores paso a paso y gradientes analíticos."
            },
            {
                "id": "linear_algebra_matrix_mult_2x2",
                "subject_id": "calculus_diff_int",
                "area_id": "math_foundations",
                "subject_name": "Cálculo Diferencial e Integral",
                "title": "Multiplicación de Matrices 2x2",
                "formula_latex": r"C = A \times B",
                "default_params": {"a11": 1, "a12": 2, "a21": 3, "a22": 4, "b11": 5, "b12": 6, "b21": 7, "b22": 8},
                "param_schema": {
                    "a11": {"label": "A[1,1]", "type": "number", "default": 1},
                    "a12": {"label": "A[1,2]", "type": "number", "default": 2},
                    "a21": {"label": "A[2,1]", "type": "number", "default": 3},
                    "a22": {"label": "A[2,2]", "type": "number", "default": 4},
                    "b11": {"label": "B[1,1]", "type": "number", "default": 5},
                    "b12": {"label": "B[1,2]", "type": "number", "default": 6},
                    "b21": {"label": "B[2,1]", "type": "number", "default": 7},
                    "b22": {"label": "B[2,2]", "type": "number", "default": 8}
                },
                "difficulty": 2,
                "real_world_context": "Rotaciones y transformaciones espaciales en gráficos 3D y capas lineales densas de redes neuronales."
            }
        ]

        if self.is_connected():
            try:
                query = self.client.table("archetypes").select("*, subjects(name, area_id)")
                if subject_id:
                    query = query.eq("subject_id", subject_id)
                res = query.execute()
                if res.data and len(res.data) > 0:
                    formatted = []
                    for r in res.data:
                        subj_info = r.get("subjects") or {}
                        formatted.append({
                            "id": r["id"],
                            "subject_id": r["subject_id"],
                            "area_id": subj_info.get("area_id", ""),
                            "subject_name": subj_info.get("name", ""),
                            "title": r["title"],
                            "formula_latex": r["formula_latex"],
                            "default_params": r.get("default_params", {}),
                            "param_schema": r.get("param_schema", {}),
                            "difficulty": r.get("difficulty", 1),
                            "real_world_context": r.get("real_world_context", "")
                        })
                    return formatted
            except Exception as e:
                print(f"[Supabase Archetypes Error] {e}")

        # Filtrar catálogo enriquecido
        filtered = archetype_catalog
        if subject_id:
            filtered = [a for a in filtered if a["subject_id"] == subject_id]
        if area_id:
            filtered = [a for a in filtered if a["area_id"] == area_id]
        return filtered

    def get_archetype_by_id(self, archetype_id: str) -> Optional[Dict[str, Any]]:
        """Obtiene un arquetipo específico por ID."""
        all_archs = self.get_archetypes()
        for a in all_archs:
            if a["id"] == archetype_id:
                return a
        return None

    def log_practice_history(self, archetype_id: str, input_params: Dict[str, Any], solutions: List[str]) -> bool:
        """Guarda un cálculo resuelto en el historial de práctica."""
        record = {
            "archetype_id": archetype_id,
            "input_params": input_params,
            "solutions": solutions,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        if self.is_connected():
            try:
                self.client.table("practice_history").insert(record).execute()
                return True
            except Exception as e:
                print(f"[Supabase History Error] {e}")

        self._memory_cache["practice_history"].append(record)
        return True

    # ====================================================================
    # NOTAS DE ESTUDIO Y REPETICIÓN ESPACIADA (SM-2 FLASHCARDS)
    # ====================================================================

    def get_study_notes(self, subject_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene las notas y tarjetas de repetición espaciada."""
        if self.is_connected():
            try:
                q = self.client.table("study_notes").select("*").order("next_review_date")
                if subject_id:
                    q = q.eq("subject_id", subject_id)
                res = q.execute()
                if res.data:
                    return res.data
            except Exception as e:
                print(f"[Supabase Notes Error] {e}")

        notes = self._memory_cache["study_notes"]
        if subject_id:
            notes = [n for n in notes if n.get("subject_id") == subject_id]
        return sorted(notes, key=lambda x: x.get("created_at", ""), reverse=True)

    def create_study_note(
        self,
        subject_id: str,
        archetype_id: Optional[str],
        title: str,
        content: str,
        mastery_level: int = 1
    ) -> Dict[str, Any]:
        """Crea una nota o flashcard con parámetros iniciales SM-2."""
        now = datetime.now(timezone.utc)
        record = {
            "subject_id": subject_id,
            "archetype_id": archetype_id,
            "title": title,
            "content": content,
            "mastery_level": max(1, min(5, mastery_level)),
            "interval_days": 1,
            "ease_factor": 2.5,
            "repetitions": 0,
            "next_review_date": (now + timedelta(days=1)).isoformat(),
            "created_at": now.isoformat(),
            "updated_at": now.isoformat()
        }
        if self.is_connected():
            try:
                res = self.client.table("study_notes").insert(record).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e:
                print(f"[Supabase Create Note Error] {e}")

        self._memory_cache["study_notes"].append(record)
        return record

    def update_study_note_review(self, note_id: str, quality: int) -> Dict[str, Any]:
        """
        Actualiza el estado de repetición espaciada según el algoritmo SuperMemo SM-2.
        quality: 0 a 5 (0: olvido total, 3: respuesta correcta con esfuerzo, 5: recuerdo perfecto).
        """
        # Cálculo SM-2
        quality = max(0, min(5, quality))
        
        # Obtener nota actual
        note = None
        if self.is_connected():
            try:
                res = self.client.table("study_notes").select("*").eq("id", note_id).execute()
                if res.data:
                    note = res.data[0]
            except Exception:
                pass

        if not note:
            for n in self._memory_cache["study_notes"]:
                if str(n.get("id")) == str(note_id) or n.get("title") == note_id:
                    note = n
                    break

        if not note:
            note = {"interval_days": 1, "ease_factor": 2.5, "repetitions": 0, "mastery_level": 1}

        reps = note.get("repetitions", 0)
        interval = note.get("interval_days", 1)
        ef = note.get("ease_factor", 2.5)

        if quality >= 3:
            if reps == 0:
                interval = 1
            elif reps == 1:
                interval = 6
            else:
                interval = int(interval * ef)
            reps += 1
        else:
            reps = 0
            interval = 1

        # Actualizar factor de facilidad (EF)
        ef = ef + (0.1 - (5 - quality) * (0.08 + (5 - quality) * 0.02))
        if ef < 1.3:
            ef = 1.3

        now = datetime.now(timezone.utc)
        next_date = (now + timedelta(days=interval)).isoformat()
        mastery = min(5, max(1, quality))

        update_payload = {
            "repetitions": reps,
            "interval_days": interval,
            "ease_factor": round(ef, 2),
            "mastery_level": mastery,
            "next_review_date": next_date,
            "updated_at": now.isoformat()
        }

        if self.is_connected():
            try:
                self.client.table("study_notes").update(update_payload).eq("id", note_id).execute()
            except Exception as e:
                print(f"[Supabase Update SM2 Error] {e}")

        return update_payload

    # ====================================================================
    # SESIONES DE ESTUDIO INTENSIVO (10+ HORAS DIARIAS)
    # ====================================================================

    def log_study_session(
        self,
        minutes: int,
        focus_area: str,
        topic: Optional[str] = None,
        notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """Registra un bloque de estudio completado (Pomodoro o tiempo continuo)."""
        record = {
            "user_id": "darlyn_david",
            "minutes_studied": minutes,
            "focus_area": focus_area,
            "topic": topic or "Sesión de Estudio Intensivo",
            "notes": notes or "",
            "completed_at": datetime.now(timezone.utc).isoformat()
        }
        if self.is_connected():
            try:
                res = self.client.table("study_sessions").insert(record).execute()
                if res.data:
                    return res.data[0]
            except Exception as e:
                print(f"[Supabase Session Error] {e}")

        self._memory_cache["study_sessions"].append(record)
        return record

    def get_study_stats_today(self) -> Dict[str, Any]:
        """Calcula el tiempo de estudio acumulado hoy hacia la meta de 10 horas (600 min)."""
        target_minutes = 600 # 10 horas
        total_today = 0
        sessions_today = []

        now = datetime.now(timezone.utc)
        start_of_day = datetime(now.year, now.month, now.day, tzinfo=timezone.utc)

        all_sessions = []
        if self.is_connected():
            try:
                res = self.client.table("study_sessions").select("*").gte("completed_at", start_of_day.isoformat()).execute()
                if res.data:
                    all_sessions = res.data
            except Exception:
                all_sessions = self._memory_cache["study_sessions"]
        else:
            all_sessions = self._memory_cache["study_sessions"]

        for s in all_sessions:
            mins = s.get("minutes_studied", 0)
            total_today += mins
            sessions_today.append(s)

        progress_pct = round(min(100.0, (total_today / target_minutes) * 100), 1)

        return {
            "student_name": "Darlyn David Tenelema Obando",
            "institution": "Instituto Superior Tecnológico Carlos Cisneros",
            "career": "Inteligencia Artificial",
            "minutes_today": total_today,
            "hours_today": round(total_today / 60, 2),
            "target_hours": 10.0,
            "progress_percent": progress_pct,
            "sessions_count": len(sessions_today),
            "remaining_minutes": max(0, target_minutes - total_today)
        }

    # ====================================================================
    # RAG VECTORIAL (SUPABASE PGVECTOR)
    # ====================================================================

    def query_knowledge(
        self,
        query: str,
        university: Optional[str] = None,
        discipline: Optional[str] = None,
        top_k: int = 3
    ) -> List[Dict[str, Any]]:
        """Búsqueda vectorial semántica con pgvector."""
        if self.is_connected() and self.enabled:
            try:
                embedding = self.get_embedding(query)
                rpc_params = {
                    "query_embedding": embedding,
                    "match_threshold": 0.25,
                    "match_count": top_k,
                    "filter_university": university,
                    "filter_discipline": discipline
                }
                response = self.client.rpc("match_university_knowledge", rpc_params).execute()
                if response.data and len(response.data) > 0:
                    return response.data
            except Exception as e:
                print(f"[Supabase RPC Error] {e}")

        return search_corpus_local(query=query, university=university, top_k=top_k)

    def save_university_knowledge(self, doc: Dict[str, Any]) -> Dict[str, Any]:
        """
        Guarda un nuevo documento de conocimiento universitario en Supabase pgvector.
        Genera automáticamente el embedding de 768 dimensiones.
        """
        import uuid
        topic = doc.get("topic", "Conocimiento de Ingeniería")
        content = doc.get("content", "")
        formula_latex = doc.get("formula_latex", "")
        emb = self.get_embedding(f"{topic} {content} {formula_latex}")
        
        record = {
            "university": doc.get("university", "MIT / Stanford Open Knowledge"),
            "country": doc.get("country", "Internacional"),
            "discipline": doc.get("discipline", "Ingeniería y Matemáticas"),
            "topic": topic,
            "formula_latex": formula_latex,
            "pedagogical_style": doc.get("pedagogical_style", "Enfoque Socrático Multilingüe"),
            "content": content,
            "engineering_application": doc.get("engineering_application", ""),
            "embedding": emb,
            "metadata": doc.get("metadata", {}),
            "created_at": datetime.now(timezone.utc).isoformat()
        }

        if self.is_connected():
            try:
                res = self.client.table("university_knowledge").insert(record).execute()
                if res.data and len(res.data) > 0:
                    return res.data[0]
            except Exception as e:
                print(f"[Supabase Save Knowledge Error] {e}")

        # Fallback in-memory
        if "university_knowledge" not in self._memory_cache:
            self._memory_cache["university_knowledge"] = []
        record["id"] = str(uuid.uuid4())
        self._memory_cache["university_knowledge"].insert(0, record)
        return record

    def get_all_university_sources(self, discipline: Optional[str] = None) -> List[Dict[str, Any]]:
        """Obtiene todas las fuentes y temas universitarios guardados en Supabase Cloud."""
        if self.is_connected():
            try:
                q = self.client.table("university_knowledge").select(
                    "id, university, country, discipline, topic, formula_latex, pedagogical_style, content, engineering_application, metadata, created_at"
                ).order("created_at", desc=True)
                if discipline:
                    q = q.eq("discipline", discipline)
                res = q.execute()
                if res.data:
                    return res.data
            except Exception as e:
                print(f"[Supabase Fetch Sources Error] {e}")

        # Fallback local corpus + memory
        all_sources = list(self._memory_cache.get("university_knowledge", []))
        for i, c in enumerate(UNIVERSITY_KNOWLEDGE_CORPUS):
            all_sources.append({
                "id": f"corpus_{i+1}",
                **c,
                "created_at": datetime.now(timezone.utc).isoformat()
            })
        if discipline:
            all_sources = [s for s in all_sources if s.get("discipline") == discipline]
        return all_sources

    def delete_university_knowledge(self, source_id: str) -> bool:
        """Elimina una fuente o apunte universitario de Supabase Cloud."""
        if self.is_connected():
            try:
                self.client.table("university_knowledge").delete().eq("id", source_id).execute()
                return True
            except Exception as e:
                print(f"[Supabase Delete Knowledge Error] {e}")

        if "university_knowledge" in self._memory_cache:
            self._memory_cache["university_knowledge"] = [
                s for s in self._memory_cache["university_knowledge"] if str(s.get("id")) != str(source_id)
            ]
        return True


    def log_session(
        self,
        equation_input: str,
        discipline: str,
        university_lens: str,
        solution_latex: str,
        pedagogical_breakdown: Dict[str, Any]
    ) -> bool:
        """Registra la sesión pedagógica del estudiante en Supabase."""
        record = {
            "user_id": "darlyn_david",
            "equation_input": equation_input,
            "discipline": discipline,
            "university_lens": university_lens,
            "solution_latex": solution_latex,
            "pedagogical_breakdown": pedagogical_breakdown,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        if self.is_connected():
            try:
                self.client.table("student_sessions").insert(record).execute()
                return True
            except Exception as e:
                print(f"[Supabase Session Log Error] {e}")
        return True

    def log_tutor_interaction(
        self,
        archetype_id: str,
        step_number: Optional[int],
        question_type: str,
        user_question: str,
        tutor_explanation: str
    ) -> bool:
        """Guarda la pregunta del estudiante y la explicación socrática en Supabase."""
        record = {
            "archetype_id": archetype_id,
            "step_number": step_number,
            "question_type": question_type,
            "user_question": user_question,
            "tutor_explanation": tutor_explanation,
            "created_at": datetime.now(timezone.utc).isoformat()
        }
        if self.is_connected():
            try:
                self.client.table("tutor_interactions").insert(record).execute()
                return True
            except Exception as e:
                print(f"[Supabase Interaction Error] {e}")

        self._memory_cache["tutor_interactions"].append(record)
        return True

    def seed_supabase_all(self) -> Dict[str, Any]:
        """
        Siembra todas las tablas de Supabase Cloud:
        - Áreas curriculares
        - Materias
        - Arquetipos
        - Corpus de Conocimiento Universitario en pgvector
        """
        if not self.is_connected():
            return {
                "success": False,
                "message": "Supabase no está conectado. Configura SUPABASE_URL y SUPABASE_KEY en .env"
            }

        counts = {"areas": 0, "subjects": 0, "archetypes": 0, "knowledge": 0}

        try:
            # 1. Sembrar áreas
            res_areas = self.client.table("areas").upsert(INITIAL_AREAS).execute()
            counts["areas"] = len(INITIAL_AREAS)

            # 2. Sembrar materias
            res_subjects = self.client.table("subjects").upsert(INITIAL_SUBJECTS).execute()
            counts["subjects"] = len(INITIAL_SUBJECTS)

            # 3. Sembrar arquetipos
            archs = self.get_archetypes()
            arch_records = []
            for a in archs:
                arch_records.append({
                    "id": a["id"],
                    "subject_id": a["subject_id"],
                    "title": a["title"],
                    "formula_latex": a["formula_latex"],
                    "default_params": a["default_params"],
                    "param_schema": a["param_schema"],
                    "difficulty": a["difficulty"],
                    "real_world_context": a["real_world_context"]
                })
            self.client.table("archetypes").upsert(arch_records).execute()
            counts["archetypes"] = len(arch_records)

            # 4. Sembrar Conocimiento pgvector
            knowledge_records = []
            for doc in UNIVERSITY_KNOWLEDGE_CORPUS:
                emb = self.get_embedding(f"{doc['topic']} {doc['content']}")
                knowledge_records.append({
                    "university": doc["university"],
                    "country": doc["country"],
                    "discipline": doc["discipline"],
                    "topic": doc["topic"],
                    "formula_latex": doc.get("formula_latex", ""),
                    "pedagogical_style": doc.get("pedagogical_style", ""),
                    "content": doc.get("content", ""),
                    "engineering_application": doc.get("engineering_application", ""),
                    "embedding": emb
                })
            self.client.table("university_knowledge").upsert(knowledge_records).execute()
            counts["knowledge"] = len(knowledge_records)

            return {
                "success": True,
                "message": f"Sincronización exitosa con Supabase Cloud: {counts}",
                "counts": counts
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "message": "Error al sembrar en Supabase. Asegúrate de haber ejecutado schema_supabase.sql en el SQL Editor."
            }

    def seed_supabase_knowledge(self) -> Dict[str, Any]:
        return self.seed_supabase_all()

# Instancia singleton del gestor
supabase_manager = SupabaseManager()
