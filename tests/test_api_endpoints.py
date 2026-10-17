import sys
from pathlib import Path
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from fastapi.testclient import TestClient
from src.api.app import app

client = TestClient(app)

def test_api():
    print("--> 1. Probando endpoint de salud /api/health (100% Cloud + Supabase + MCP)...")
    r = client.get("/api/health")
    assert r.status_code == 200
    data = r.json()
    assert "Aureon" in data["name"]
    assert "supabase_cloud" in data
    assert "mcp_protocol" in data
    print("    [OK] Salud API:", data["status"], "| Persistencia:", data["persistence"])

    print("\n--> 2. Probando entrega de Web UI /...")
    r_html = client.get("/")
    assert r_html.status_code == 200
    assert "AUREON" in r_html.text
    print("    [OK] Web UI servida correctamente.")

    print("\n--> 3. Probando /api/tutor/universities (Pedagogías)...")
    r = client.get("/api/tutor/universities")
    assert r.status_code == 200
    univs = r.json()
    assert len(univs) >= 5
    print(f"    [OK] {len(univs)} universidades pedagógicas verificadas.")

    print("\n--> 4. Probando Solucionador Universal IA (/api/tutor/solve-custom)...")
    ode_test = "diff(y(x), x, 2) + 4*y(x) = sin(x)"
    r = client.post("/api/tutor/solve-custom", json={
        "equation": ode_test,
        "university_lens": "moscow"
    })
    assert r.status_code == 200
    ode_res = r.json()
    assert ode_res["symbolic_result"]["success"] is True
    print(f"    [OK] EDO resuelta con éxito con SymPy: {ode_res['symbolic_result']['latex_solution']}")

    print("\n--> 5. Probando Búsqueda Semántica Vectorial (/api/tutor/rag-search)...")
    r = client.post("/api/tutor/rag-search", json={
        "query": "retropropagacion gradiente redes neuronales",
        "top_k": 2
    })
    assert r.status_code == 200
    rag_data = r.json()
    assert len(rag_data["results"]) > 0
    print(f"    [OK] RAG respondió con fuente: {rag_data['source']}, match: {rag_data['results'][0]['topic']}")

    print("\n--> 6. Probando Nuevos Arquetipos de Ingeniería (IA, SO, Mecánica)...")
    # Probar IA Backpropagation
    r = client.post("/api/math/archetypes/ai_backprop_grad/solve", json={
        "x": 2.0, "w": 0.5, "b": 0.1, "y_true": 1.0, "lr": 0.1
    })
    assert r.status_code == 200
    ai_res = r.json()
    assert len(ai_res["steps"]) == 4
    print(f"    [OK] IA Backpropagation resuelto: {ai_res['final_solutions'][0]}")

    # Probar Paginación de SO
    r = client.post("/api/math/archetypes/os_paging_translation/solve", json={
        "virtual_address": 10500, "page_size": 4096, "frame_number": 7
    })
    assert r.status_code == 200
    os_res = r.json()
    assert "PA = 30980" in os_res["final_solutions"][0]
    print(f"    [OK] Paginación de SO resuelta: {os_res['final_solutions'][0]}")

    # Probar Ley de Hooke en Mecánica
    r = client.post("/api/math/archetypes/mechanics_hooke_stress/solve", json={
        "force_n": 50000.0, "area_mm2": 250.0, "initial_len_m": 2.0, "young_modulus_gpa": 200.0
    })
    assert r.status_code == 200
    mech_res = r.json()
    print(f"    [OK] Mecánica resuelta: {mech_res['final_solutions'][0]}, {mech_res['final_solutions'][1]}")

    print("\n--> 7. Probando Servidor MCP (/api/mcp)...")
    r = client.get("/api/mcp/tools")
    assert r.status_code == 200
    tools = r.json()["tools"]
    assert len(tools) >= 5
    print(f"    [OK] {len(tools)} herramientas MCP detectadas: {[t['name'] for t in tools]}")

    # Ejecutar herramienta MCP solve_equation_symbolic
    r_call = client.post("/api/mcp/tools/call", json={
        "name": "solve_equation_symbolic",
        "arguments": {"equation": "x^2 - 9 = 0", "university_lens": "stanford"}
    })
    assert r_call.status_code == 200
    call_data = r_call.json()
    assert call_data["result"]["symbolic_result"]["success"] is True
    print("    [OK] Herramienta MCP ejecutada exitosamente vía JSON.")

    print("\n--> 8. Probando Tracker de 10 Horas y Repetición Espaciada SM-2...")
    # Registrar bloque de estudio
    r_session = client.post("/api/library/sessions", json={
        "minutes": 50,
        "focus_area": "ai",
        "topic": "Backpropagation en PyTorch",
        "notes": "Derivación analítica de la regla de la cadena"
    })
    assert r_session.status_code == 200
    print("    [OK] Sesión de 50 min registrada en Supabase Cloud.")

    # Consultar estadísticas del día
    r_stats = client.get("/api/library/stats")
    assert r_stats.status_code == 200
    stats = r_stats.json()
    assert stats["student_name"] == "Darlyn David Tenelema Obando"
    print(f"    [OK] Progreso de 10 horas: {stats['minutes_today']} min ({stats['progress_percent']}%)")

    # Crear flashcard y calificar SM-2
    r_note = client.post("/api/library/notes", json={
        "subject_id": "ai_deep_learning",
        "title": "¿Qué representa el gradiente en backpropagation?",
        "content": "La dirección de máximo incremento de la pérdida L con respecto a cada peso W.",
        "mastery_level": 1
    })
    assert r_note.status_code == 200
    print("    [OK] Flashcard de estudio creada.")

    print("\n--> 9. Probando Motor de Investigación Global & NotebookLLM Studio...")
    # 9.1 Investigar tema global en universidades (ej: Filtro de Kalman o Navier Stokes)
    r_res = client.post("/api/tutor/research-global", json={
        "topic": "Filtro de Kalman Extendido en Robótica Móvil",
        "university_preference": "mit",
        "discipline": "Robótica y Control"
    })
    assert r_res.status_code == 200
    dossier = r_res.json()
    assert "formula_latex" in dossier
    assert "equations_list" in dossier
    print(f"    [OK] Investigación universitaria generada: '{dossier['title']}' con fórmula {dossier['formula_latex'][:40]}...")

    # 9.2 Listar fuentes universitarias
    r_sources = client.get("/api/tutor/sources")
    assert r_sources.status_code == 200
    sources_data = r_sources.json()
    assert sources_data["count"] > 0
    print(f"    [OK] Fuentes universitarias activas en Supabase: {sources_data['count']} fuentes.")

    # 9.3 Generar artefacto de estudio (Formulario de Ecuaciones y Podcast)
    r_art = client.post("/api/tutor/generate-notebook-artifact", json={
        "topic": "Filtro de Kalman",
        "source_content": dossier["content"],
        "artifact_type": "equations_formulary"
    })
    assert r_art.status_code == 200
    art_data = r_art.json()
    assert "content" in art_data
    print("    [OK] Formulario maestro de ecuaciones generado con KaTeX.")

    # 9.4 Generar Guión de Audio Podcast a 2 voces
    r_podcast = client.post("/api/tutor/generate-notebook-artifact", json={
        "topic": "Filtro de Kalman",
        "source_content": dossier["content"],
        "artifact_type": "audio_overview_script"
    })
    assert r_podcast.status_code == 200
    assert "Dra. Elena Ramos" in r_podcast.json()["content"]
    print("    [OK] Guión de audio podcast a 2 voces (NotebookLLM) generado con éxito.")

    # 9.5 Chat fundamentado en las fuentes
    r_chat = client.post("/api/tutor/chat-sources", json={
        "query": "¿Por qué la ganancia de Kalman K pondera la covarianza de error?",
        "source_ids": [dossier.get("id")]
    })
    assert r_chat.status_code == 200
    chat_res = r_chat.json()
    assert "answer" in chat_res
    print("    [OK] Chat fundamentado en fuentes universitarias respondió con rigor.")

if __name__ == "__main__":
    test_api()
    print("\n====================================================================")
    print(" [ÉXITO TOTAL] Aureon AI Cloud + Supabase + MCP completamente funcional")
    print("====================================================================")
