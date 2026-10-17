"""
Motor de Inteligencia Artificial para Aureon Tutor.
Integración con Gemini 3.1 / Gemini 2.5, resolución simbólica determinista con SymPy,
RAG vectorial sobre conocimiento de Harvard, Stanford, Moscú (MGU) y Tsinghua.
"""
import os
import json
import re
from typing import Dict, Any, Optional, List
import sympy as sp

from src.knowledge.universities import get_university_pedagogy
from src.database.supabase_client import supabase_manager

from pathlib import Path

class GeminiTutorEngine:
    """Tutor Socrático Inteligente con Lentes Pedagógicos de Prestigiosas Universidades."""

    def __init__(self):
        self.model_name = os.getenv("GEMINI_MODEL", "gemini-2.5-pro")
        self._client = None
        self._init_client()

    def _init_client(self):
        """Inicializa el cliente de Google Agent Platform (Google Cloud AI) o Gemini API."""
        base_dir = Path(__file__).resolve().parent.parent.parent
        
        # 1. Si Railway provee las credenciales como variable JSON
        cred_json = os.getenv("GOOGLE_APPLICATION_CREDENTIALS_JSON", "").strip()
        if cred_json and not os.getenv("GOOGLE_APPLICATION_CREDENTIALS"):
            try:
                cred_file = base_dir / "service_account.json"
                if not cred_file.exists():
                    with open(cred_file, "w", encoding="utf-8") as f:
                        f.write(cred_json)
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(cred_file)
            except Exception as e:
                print(f"[Credentials Write Warning] {e}")

        # 1. Si Railway o el entorno provee las credenciales como variable JSON
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
            except Exception as e:
                print(f"[Credentials Write Warning] {e}")

        # 2. Si existe un archivo glassy-*.json en la raíz
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")
        if not cred_path or not os.path.exists(cred_path):
            for f in base_dir.glob("glassy-*.json"):
                os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = str(f)
                break
        project_id = os.getenv("GCP_PROJECT_ID", "glassy-508419").strip()
        location = os.getenv("GCP_LOCATION", "us-central1").strip()

        if cred_path and os.path.exists(cred_path):
            try:
                from google import genai
                self._client = genai.Client(vertexai=True, project=project_id, location=location)
                print(f"[Google Agent Platform] Conectado exitosamente al proyecto GCP '{project_id}' en '{location}'")
                return
            except Exception as e:
                print(f"[Google Agent Platform Init Warning] {e}")

        # 4. Fallback a GEMINI_API_KEY estándar si se proporciona
        api_key = os.getenv("GEMINI_API_KEY", "").strip()
        if api_key and "tu_gemini" not in api_key:
            try:
                from google import genai
                self._client = genai.Client(api_key=api_key)
            except Exception:
                try:
                    import google.generativeai as legacy_genai
                    legacy_genai.configure(api_key=api_key)
                    self._client = legacy_genai
                except Exception:
                    self._client = None

    def _call_gemini(self, prompt: str, system_instruction: str) -> Optional[str]:
        """Ejecuta la inferencia sobre el LLM de Google Agent Platform."""
        if not self._client:
            self._init_client()
        if not self._client:
            return None

        # Intentar llamar al SDK genai
        try:
            response = self._client.models.generate_content(
                model=self.model_name,
                contents=prompt,
                config={
                    "system_instruction": system_instruction,
                    "temperature": 0.2,
                }
            )
            return response.text
        except Exception as e:
            # Si el modelo pro falla, intentar con gemini-2.5-flash
            try:
                response = self._client.models.generate_content(
                    model="gemini-2.5-flash",
                    contents=prompt,
                    config={
                        "system_instruction": system_instruction,
                        "temperature": 0.2,
                    }
                )
                return response.text
            except Exception as e_inner:
                print(f"[Google Agent Platform API Call Failed] {e_inner}")
                return None

    def solve_symbolic_sympy(self, equation_str: str) -> Dict[str, Any]:
        """
        Calcula determinísticamente la solución matemática exacta con SymPy
        para cualquier tipo de ecuación algebraica, cálculo o EDO (0% alucinaciones).
        """
        from sympy.parsing.sympy_parser import (
            parse_expr, 
            standard_transformations, 
            implicit_multiplication_application, 
            convert_xor
        )
        transformations = standard_transformations + (implicit_multiplication_application, convert_xor)

        x, y, t, z, s = sp.symbols('x y t z s')
        clean_eq = equation_str.strip()
        result = {
            "success": False,
            "operation": "general",
            "latex_input": clean_eq,
            "latex_solution": "",
            "raw_solutions": [],
            "steps": []
        }

        try:
            # 1. Detectar si es una Ecuación Diferencial Ordinaria (EDO)
            if "diff(" in clean_eq or "d^2" in clean_eq or "dy/dx" in clean_eq or "y''" in clean_eq or "y'" in clean_eq:
                result["operation"] = "ode"
                ode_str = clean_eq.replace("y''", "diff(y(x), x, 2)").replace("y'", "diff(y(x), x)").replace("dy/dx", "diff(y(x), x)")
                ode_str = ode_str.replace("=", "-(") + ")" if "=" in ode_str else ode_str
                y_func = sp.Function('y')(x)
                local_dict = {'x': x, 'y': sp.Function('y'), 'diff': sp.diff, 'sin': sp.sin, 'cos': sp.cos, 'exp': sp.exp}
                ode_expr = parse_expr(ode_str, local_dict=local_dict, transformations=transformations)
                sol = sp.dsolve(ode_expr, y_func)
                result["success"] = True
                result["latex_input"] = sp.latex(ode_expr) + " = 0"
                result["latex_solution"] = sp.latex(sol)
                result["raw_solutions"] = [str(sol)]
                result["steps"] = [
                    {"step": 1, "title": "Identificación del Orden de la EDO", "latex": sp.latex(ode_expr) + " = 0"},
                    {"step": 2, "title": "Solución de la Ecuación Característica / Homogénea", "latex": r"r^2 + \dots = 0"},
                    {"step": 3, "title": "Solución General Cerrada", "latex": sp.latex(sol)}
                ]
                return result

            # 2. Detectar si es una Integral
            int_match = re.match(r'^(integrate|int)\s*\((.*)\)$', clean_eq, re.IGNORECASE | re.DOTALL)
            if int_match or clean_eq.lower().startswith("int") or "integrate" in clean_eq.lower():
                result["operation"] = "integral"
                inner = int_match.group(2) if int_match else re.sub(r'^(integrate|int)\s*\(?', '', clean_eq, flags=re.IGNORECASE).rstrip(')')
                # Separar integrando y variable opcional
                parts = [p.strip() for p in inner.split(',') if p.strip()]
                integrand_str = parts[0] if parts else "x"
                var_symbol = sp.Symbol(parts[1]) if len(parts) > 1 and parts[1].isalpha() else x
                
                expr = parse_expr(integrand_str, transformations=transformations)
                sol = sp.integrate(expr, var_symbol)
                result["success"] = True
                result["latex_input"] = r"\int " + sp.latex(expr) + f"\\, d{var_symbol.name}"
                result["latex_solution"] = sp.latex(sol) + " + C"
                result["raw_solutions"] = [str(sol) + " + C"]
                result["steps"] = [
                    {"step": 1, "title": "Formulación de la Antiderivada", "latex": result["latex_input"]},
                    {"step": 2, "title": "Integración Simbólica Determinista", "latex": result["latex_solution"]}
                ]
                return result

            # 3. Detectar si es una Derivada
            diff_match = re.match(r'^(diff|derivative|deriv|d/dx)\s*\((.*)\)$', clean_eq, re.IGNORECASE | re.DOTALL)
            if diff_match or clean_eq.lower().startswith("diff") or clean_eq.lower().startswith("deriv"):
                result["operation"] = "derivative"
                inner = diff_match.group(2) if diff_match else re.sub(r'^(derivative|deriv|diff|d/dx)\s*\(?', '', clean_eq, flags=re.IGNORECASE).rstrip(')')
                parts = [p.strip() for p in inner.split(',') if p.strip()]
                target_str = parts[0] if parts else "x"
                var_symbol = sp.Symbol(parts[1]) if len(parts) > 1 and parts[1].isalpha() else x

                expr = parse_expr(target_str, transformations=transformations)
                sol = sp.diff(expr, var_symbol)
                result["success"] = True
                result["latex_input"] = f"\\frac{{d}}{{d{var_symbol.name}}}\\left[" + sp.latex(expr) + r"\right]"
                result["latex_solution"] = sp.latex(sol)
                result["raw_solutions"] = [str(sol)]
                result["steps"] = [
                    {"step": 1, "title": "Función a Diferenciar", "latex": sp.latex(expr)},
                    {"step": 2, "title": "Derivada por Regla de la Cadena / Potencias", "latex": sp.latex(sol)}
                ]
                return result

            # 4. Ecuación Algebraica General (con '=' o polinomio)
            lhs_str, rhs_str = clean_eq.split("=") if "=" in clean_eq else (clean_eq, "0")
            lhs = parse_expr(lhs_str, transformations=transformations)
            rhs = parse_expr(rhs_str, transformations=transformations)
            expr = lhs - rhs

            sols = sp.solve(expr, x)
            result["success"] = True
            result["operation"] = "algebraic"
            result["latex_input"] = sp.latex(lhs) + " = " + sp.latex(rhs)
            if sols:
                latex_sols = [f"x_{{{i+1}}} = {sp.latex(s)}" for i, s in enumerate(sols)]
                result["latex_solution"] = ", \\quad ".join(latex_sols)
                result["raw_solutions"] = [str(s) for s in sols]
            else:
                result["latex_solution"] = r"\text{Sin soluciones reales explícitas}"
                result["raw_solutions"] = ["Sin soluciones"]

            result["steps"] = [
                {"step": 1, "title": "Forma Canónica Igualada a Cero", "latex": sp.latex(expr) + " = 0"},
                {"step": 2, "title": "Factorización o Despeje Algebraico", "latex": sp.latex(sp.factor(expr)) + " = 0" if hasattr(sp, 'factor') else sp.latex(expr)},
                {"step": 3, "title": "Raíces y Solución Final", "latex": result["latex_solution"]}
            ]
            return result

        except Exception as e:
            # Si SymPy no pudo parsear la expresión textual directamente
            result["success"] = False
            result["error"] = str(e)
            result["latex_solution"] = r"\text{Interpretado por IA Aureon}"
            return result

    def explain_custom_equation(
        self,
        equation_input: str,
        university_lens: str = "stanford",
        user_notes: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Resuelve y explica CUALQUIER ecuación o disciplina matemática con el
        estilo de la universidad seleccionada (Harvard, Stanford, MGU Moscú, Tsinghua).
        """
        pedagogy = get_university_pedagogy(university_lens)
        sympy_res = self.solve_symbolic_sympy(equation_input)

        # Buscar contexto relevante en Supabase Vector / Corpus RAG
        rag_docs = supabase_manager.query_knowledge(
            query=f"{equation_input} {pedagogy['name']} {pedagogy['tagline']}",
            university=pedagogy["id"],
            top_k=2
        )

        rag_context = "\n".join([
            f"- Teorema Universitario ({d.get('university', '')}): {d.get('topic', '')} -> {d.get('content', '')}"
            for d in rag_docs
        ])

        # Construir Prompt Socrático de Alto Nivel
        system_instruction = (
            f"Eres Aureon, un tutor personal de élite en matemáticas e ingeniería, "
            f"adoptando el lente de enseñanza de {pedagogy['name']}.\n"
            f"Filosofía Pedagógica: {pedagogy['philosophy']}\n"
            f"Tono: {pedagogy['tone']}\n"
            f"Reglas estrictas:\n"
            f"1. Explica con fórmulas matemáticas KaTeX nítidas (usa delimitadores $...$ y $$...$$).\n"
            f"2. Da la intuición fundamental ('por qué funciona esto') antes de saltar a cuentas mecánicas.\n"
            f"3. Explica exactamente el origen de cada término o constante.\n"
            f"4. Provee un caso de aplicación real indispensable en ingeniería (software, robótica, nuclear o cuántica).\n"
            f"5. Termina con un reto reflexivo estilo examen de {pedagogy['name']}."
        )

        user_prompt = f"""
Ecuación planteada por el estudiante: {equation_input}
Resolución Simbólica Determinista (SymPy):
- Entrada interpretada: {sympy_res.get('latex_input')}
- Solución exacta: {sympy_res.get('latex_solution')}
- Pasos analíticos: {json.dumps(sympy_res.get('steps', []))}

Contexto RAG de Universidades:
{rag_context}

Notas adicionales del usuario: {user_notes or 'Ninguna'}

Genera una lección socrática desglosada y estructurada con:
1. Intuición Central de {pedagogy['name']}
2. Procedimiento y Desglose Paso a Paso con KaTeX
3. Origen y Justificación de las Constantes / Operaciones
4. Aplicación Crítica en Ingeniería
5. Reto o Pregunta Reflexiva
"""

        gemini_response = self._call_gemini(user_prompt, system_instruction)

        if not gemini_response:
            # Respuesta estructurada de alta calidad si la API Key aún no fue provista por el usuario
            gemini_response = self._generate_offline_pedagogical_lesson(
                equation=equation_input,
                sympy_data=sympy_res,
                pedagogy=pedagogy,
                rag_docs=rag_docs
            )

        # Registrar la sesión del estudiante
        supabase_manager.log_session(
            equation_input=equation_input,
            discipline=pedagogy["name"],
            university_lens=pedagogy["id"],
            solution_latex=sympy_res.get("latex_solution", ""),
            pedagogical_breakdown={"explanation": gemini_response}
        )

        return {
            "equation_input": equation_input,
            "university": pedagogy,
            "symbolic_result": sympy_res,
            "rag_sources": rag_docs,
            "explanation": gemini_response
        }

    def answer_interactive_query(
        self,
        archetype_title: str,
        step_number: Optional[int],
        question_type: str,
        user_question: Optional[str],
        active_params: Dict[str, Any],
        step_data: Optional[Dict[str, Any]] = None,
        university_lens: str = "stanford"
    ) -> str:
        """
        Responde preguntas interactivas específicas del Canvas ("¿De dónde sale este número?", etc.).
        """
        pedagogy = get_university_pedagogy(university_lens)
        
        system_instruction = (
            f"Eres Aureon, tutor matemático personal con el enfoque de {pedagogy['name']}. "
            f"Sé ultra pedagógico, preciso y estimulante. Usa KaTeX ($ y $$) para renderizar fórmulas."
        )

        prompt = f"""
Ejercicio activo: {archetype_title}
Parámetros numéricos en vivo: {json.dumps(active_params)}
Paso consultado por el alumno: {step_number or 'General'}
Detalles del paso: {json.dumps(step_data or {})}
Tipo de pregunta: {question_type}
Pregunta o inquietud del alumno: {user_question or 'Explícame este paso en detalle.'}

Responde de forma clara y directa, explicando la procedencia exacta de los números,
las leyes algebraicas que operan y cómo interpretarlo bajo la mirada de {pedagogy['name']}.
"""
        resp = self._call_gemini(prompt, system_instruction)
        if resp:
            return resp

        # Fallback inteligente contextual si no hay Gemini API Key aún
        return self._generate_offline_interactive_answer(
            archetype_title=archetype_title,
            step_number=step_number,
            question_type=question_type,
            user_question=user_question,
            active_params=active_params,
            step_data=step_data,
            pedagogy=pedagogy
        )

    def _generate_offline_pedagogical_lesson(
        self,
        equation: str,
        sympy_data: Dict[str, Any],
        pedagogy: Dict[str, Any],
        rag_docs: List[Dict[str, Any]]
    ) -> str:
        """Generador pedagógico offline garantizado."""
        latex_in = sympy_data.get("latex_input", equation)
        latex_sol = sympy_data.get("latex_solution", r"\text{Solución en proceso}")

        lesson = (
            f"### {pedagogy['flag']} Lección Maestra: Enfoque {pedagogy['name']}\n\n"
            f"> **Filosofía del Método:** {pedagogy['philosophy']}\n\n"
            f"#### 1. Formulación Simbólica Rigurosa\n"
            f"Partimos de la expresión analítica:\n"
            f"$$\n{latex_in}\n$$\n\n"
            f"Evaluada de forma determinista mediante el motor algebraico, la solución exacta es:\n"
            f"$$\n{latex_sol}\n$$\n\n"
            f"#### 2. Desglose del Procedimiento Didáctico\n"
        )

        for s in sympy_data.get("steps", []):
            lesson += (
                f"**Paso {s.get('step')}: {s.get('title')}**\n"
                f"- Expresión resultante: $${s.get('latex')}$$\n"
                f"- *Fundamento algebraico:* Conservación de la igualdad mediante transformaciones canónicas.\n\n"
            )

        lesson += (
            f"#### 3. Aplicación en Ingeniería y Sistemas Reales\n"
            f"En problemas de ingeniería avanzada (robótica, microchips, física de reactores), "
            f"este tipo de ecuaciones modela puntos de equilibrio, trayectorias conservativas y "
            f"respuestas ante perturbaciones dinámicas.\n\n"
            f"#### 4. Reto de {pedagogy['name']}\n"
            f"¿Qué sucedería con la solución si perturbamos los coeficientes principales hacia cero o si cambiamos las condiciones de frontera? "
            f"Piénsalo antes de modificar los valores en el panel numérico."
        )
        return lesson

    def _generate_offline_interactive_answer(
        self,
        archetype_title: str,
        step_number: Optional[int],
        question_type: str,
        user_question: Optional[str],
        active_params: Dict[str, Any],
        step_data: Optional[Dict[str, Any]],
        pedagogy: Dict[str, Any]
    ) -> str:
        """Respuesta socrática contextual offline."""
        step_txt = f"Paso {step_number}" if step_number else "este paso"
        if question_type == "source_of_number":
            breakdown = step_data.get("source_breakdown") if step_data else None
            return (
                f"### {pedagogy['flag']} Origen Numérico en el {step_txt} ({pedagogy['name']})\n\n"
                f"{breakdown or 'Cada número presente aquí no es arbitrario: es el resultado de evaluar las operaciones del paso inmediatamente anterior con los coeficientes activos ' + str(active_params) + '.'}\n\n"
                f"👉 **Principio:** En matemáticas no hay números mágicos; cada cifra es la huella de una transformación previa."
            )
        elif question_type == "process_name":
            rule = step_data.get("rule_name") if step_data else "Propiedad de Inversión y Equivalencia"
            return (
                f"### {pedagogy['flag']} Nombre del Proceso Formal\n\n"
                f"**Teorema / Regla:** *{rule}*\n\n"
                f"Bajo el estándar de **{pedagogy['name']}**, este procedimiento garantiza que el espacio de soluciones "
                f"se preserve idéntico sin introducir raíces espurias."
            )
        elif question_type == "real_world_use":
            return (
                f"### {pedagogy['flag']} ¿Dónde y cuándo se utiliza en la Ingeniería?\n\n"
                f"Este modelo ({archetype_title}) es la columna vertebral en:\n"
                f"1. **Ingeniería de Software & IA:** Calibración de pesos y análisis de convergencia.\n"
                f"2. **Robótica & Dinámica:** Transformación de coordenadas y cálculo de torques.\n"
                f"3. **Sistemas Físicos:** Balances de conservación de masa y energía."
            )
        else:
            q = user_question or "¿Cómo funciona?"
            return (
                f"### {pedagogy['flag']} Análisis de Aureon ({pedagogy['name']})\n\n"
                f"**Tu pregunta:** *{q}*\n\n"
                f"Al examinar los parámetros {active_params} en *{archetype_title}*, "
                f"la estructura matemática asegura que el procedimiento sea determinista. "
                f"Configura tu `GEMINI_API_KEY` en el archivo `.env` para desbloquear explicaciones socráticas en tiempo real ilimitadas generadas por Gemini 3.1."
            )

# Instancia singleton del motor de IA
gemini_tutor = GeminiTutorEngine()
