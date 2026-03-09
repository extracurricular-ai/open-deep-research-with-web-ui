# Open Deep Research

[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)
[![Python](https://img.shields.io/badge/Python-3.8%2B-blue)](https://www.python.org/)
[![Docker](https://img.shields.io/badge/Docker-ghcr.io-blue)](https://ghcr.io/s2thend/open-deep-research-with-ui)

Una replicación abierta de [Deep Research de OpenAI](https://openai.com/index/introducing-deep-research/) con una interfaz web moderna — adaptada de [HuggingFace smolagents](https://github.com/huggingface/smolagents/tree/main/examples) con configuración simplificada para fácil auto-alojamiento.

Lee más sobre la implementación original en el [artículo del blog de HuggingFace](https://huggingface.co/blog/open-deep-research).

Este agente alcanza **55% pass@1** en el conjunto de validación GAIA, comparado con **67%** de Deep Research de OpenAI.

---

## Características

- **Investigación paralela en segundo plano** — lanza múltiples tareas de investigación simultáneamente, monitoréalas independientemente y consulta los resultados más tarde — incluso después de cerrar el navegador
- **Pipeline de investigación multi-agente** — Manager + sub-agentes de búsqueda con salida en streaming en tiempo real
- **Interfaz web moderna** — SPA basada en Preact con secciones colapsables, selector de modelos y soporte para copiar
- **Soporte de modelos flexible** — Cualquier modelo compatible con LiteLLM (OpenAI, Claude, DeepSeek, Ollama, etc.)
- **Múltiples motores de búsqueda** — DuckDuckGo (gratuito), SerpAPI, MetaSo con replegamiento automático
- **Historial de sesiones** — Almacenamiento de sesiones basado en SQLite con soporte de reproducción
- **Tres modos de ejecución** — Live (tiempo real), Background (persistente), Auto-kill (one-shot)
- **Descubrimiento automático de modelos** — Detecta los modelos disponibles de los proveedores configurados
- **Herramientas visuales y de medios** — Preguntas y respuestas sobre imágenes, análisis de PDF, transcripción de audio, transcripciones de YouTube
- **Listo para producción** — Docker, Gunicorn, multi-worker, comprobaciones de salud, configurable mediante JSON

**Capturas de pantalla:**

<div align="center">
  <img src="imgs/ui_input.png" alt="Interfaz de entrada Web UI" width="800"/>
  <p><em>Interfaz de entrada limpia con selección de modelos</em></p>

  <img src="imgs/ui_tools_plans.png" alt="Planes y herramientas del agente" width="800"/>
  <p><em>Visualización en tiempo real del razonamiento del agente, llamadas a herramientas y observaciones</em></p>

  <img src="imgs/ui_result.png" alt="Resultados finales" width="800"/>
  <p><em>Respuesta final resaltada con secciones colapsables</em></p>
</div>

---

## Investigación paralela en segundo plano

Las tareas de investigación profunda son lentas — una sola ejecución puede tardar de 10 a 30 minutos. La mayoría de las herramientas bloquean la interfaz hasta que la tarea se completa, obligándote a esperar.

Este proyecto adopta un enfoque diferente: **lanza tantas tareas de investigación como quieras y déjalas ejecutarse en segundo plano — simultáneamente.**

```
┌─────────────────────────────────────────────────────┐
│  Pregunta A: "¿Cuáles son los últimos avances en LLMs?"  │  ← en ejecución
│  Pregunta B: "Comparar las mejores bases de datos vectoriales en 2025"  │  ← en ejecución
│  Pregunta C: "Lista de verificación de cumplimiento de la AI Act de la UE"  │  ← completado ✓
└─────────────────────────────────────────────────────┘
        Todas visibles en la barra lateral. Haz clic en cualquiera para inspeccionar.
```

**Cómo funciona:**

1. Selecciona el modo de ejecución **Background** o **Auto-kill** (el predeterminado)
2. Envía tu primera pregunta de investigación — el agente comienza inmediatamente en un subproceso
3. La interfaz no está bloqueada — envía una segunda pregunta, una tercera, tantas como necesites
4. Cada agente se ejecuta independientemente, persistiendo todos sus pasos de razonamiento y resultados en SQLite
5. Usa la barra lateral para cambiar entre sesiones en ejecución en tiempo real
6. Cierra el navegador — en modo **Background**, los agentes siguen ejecutándose en el servidor
7. Regresa más tarde y haz clic en cualquier sesión para reproducir el rastro completo de investigación

**Comparación de modos de ejecución:**

| Modo | Múltiples a la vez | Sobrevive al cierre del navegador | Interfaz bloqueada |
|---|---|---|---|
| **Background** | ✅ | ✅ | ✗ |
| **Auto-kill** | ✅ | ✗ (terminado al cerrar la pestaña) | ✗ |
| **Live** | ✗ | ✗ | ✅ |

Es especialmente útil para:
- Flujos de trabajo de investigación por lotes donde pones en cola varias preguntas relacionadas y revisas los resultados juntos
- Consultas de larga duración donde no quieres mantener una pestaña abierta
- Equipos que comparten una instancia auto-alojada con múltiples usuarios simultáneos

---

## ¿Por qué este proyecto?

Hay varias alternativas open source a Deep Research. Así es como se compara este proyecto:

| Característica | **Este proyecto** | [nickscamara/open-deep-research](https://github.com/nickscamara/open-deep-research) | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | [langchain/open_deep_research](https://github.com/langchain-ai/open_deep_research) | [smolagents](https://github.com/huggingface/smolagents) |
|---|---|---|---|---|---|
| **Docker / despliegue en un comando** | ✅ Imagen pre-construida en GHCR | ✅ Dockerfile | ✅ Docker Compose | ❌ Manual | ❌ Solo biblioteca |
| **Frontend sin compilación** | ✅ Preact + htm (sin paso de compilación) | ❌ Requiere compilación Next.js | ❌ Requiere compilación Next.js | ❌ LangGraph Studio | — |
| **Búsqueda gratuita de inmediato** | ✅ DuckDuckGo (sin clave necesaria) | ❌ Requiere API Firecrawl | ⚠️ Clave recomendada | ⚠️ Configurable | ✅ |
| **Agnóstico en modelos** | ✅ Cualquier modelo LiteLLM | ✅ Proveedores AI SDK | ✅ Múltiples proveedores | ✅ Configurable | ✅ |
| **Soporte de modelos locales** | ✅ Ollama, LM Studio | ⚠️ Limitado | ✅ Ollama/Groq | ✅ | ✅ |
| **Tareas paralelas en segundo plano** | ✅ Múltiples ejecuciones simultáneas | ❌ | ❌ | ❌ | ❌ |
| **Historial / reproducción de sesiones** | ✅ Basado en SQLite | ❌ | ❌ | ❌ | ❌ |
| **Interfaz streaming** | ✅ SSE, 3 modos de ejecución | ✅ Actividad en tiempo real | ✅ WebSocket | ✅ Stream type-safe | ❌ |
| **Análisis visual / imágenes** | ✅ Capturas de PDF, QA visual | ❌ | ⚠️ Limitado | ❌ | ⚠️ |
| **Audio / YouTube** | ✅ Transcripción, voz | ❌ | ❌ | ❌ | ❌ |
| **Puntuación de referencia GAIA** | **55% pass@1** | — | — | — | 55% (original) |

### Ventajas clave de este proyecto

- **Investigación paralela en segundo plano** — la característica más única en este espacio. Inicia múltiples tareas de investigación profunda al mismo tiempo — cada una se ejecuta como un subproceso independiente, persiste todos los eventos en SQLite, y puede monitorearse o reproducirse independientemente. Cierra el navegador, regresa horas después, y tus resultados te esperan. Ninguna otra herramienta de investigación profunda open source soporta este flujo de trabajo.
- **Despliegue con un solo `docker run`** — la imagen pre-construida en GHCR funciona en cualquier plataforma con Docker: Linux, macOS, Windows, ARM, VMs en la nube, Raspberry Pi.
- **Sin paso de compilación** — el frontend usa Preact con literales de plantilla `htm`. Sin Node.js, sin `npm install`, sin webpack. Solo abre el navegador.
- **Gratuito por defecto** — la búsqueda DuckDuckGo no requiere clave API, por lo que el agente funciona inmediatamente después de agregar solo una clave API de modelo.
- **Soporte de medios más amplio** — maneja PDFs, imágenes, archivos de audio y transcripciones de YouTube que otros proyectos dejan al usuario.

---

## Inicio rápido

### 1. Clonar el repositorio

```bash
git clone https://github.com/S2thend/open-deep-research-with-ui.git
cd open-deep-research-with-ui
```

### 2. Instalar dependencias del sistema

El proyecto requiere **FFmpeg** para el procesamiento de audio.

- **macOS**: `brew install ffmpeg`
- **Linux**: `sudo apt-get install ffmpeg`
- **Windows**: `choco install ffmpeg` o descarga desde [ffmpeg.org](https://ffmpeg.org/download.html)

Verificar: `ffmpeg -version`

### 3. Instalar dependencias de Python

```bash
python3 -m venv venv
source venv/bin/activate  # En Windows: venv\Scripts\activate
pip install -e .
```

### 4. Configurar

Copia la configuración de ejemplo y agrega tus claves API:

```bash
cp odr-config.example.json odr-config.json
```

Edita `odr-config.json` para establecer tu proveedor de modelos y claves API (ver [Configuración](#configuración) más abajo).

### 5. Ejecutar

```bash
# Interfaz web (recomendado)
python web_app.py
# Abrir http://localhost:5080

# CLI
python run.py --model-id "gpt-4o" "Tu pregunta de investigación aquí"
```

---

## Configuración

La configuración se gestiona mediante `odr-config.json` (preferido) o variables de entorno.

### odr-config.json

Copia `odr-config.example.json` a `odr-config.json` y personaliza:

```json
{
  "model": {
    "providers": [
      {
        "name": "openai",
        "api_key": "sk-...",
        "models": ["gpt-4o", "o1", "o3-mini"]
      }
    ],
    "default": "gpt-4o"
  },
  "search": {
    "providers": [
      { "name": "DDGS" },
      { "name": "META_SOTA", "api_key": "your_key" }
    ]
  }
}
```

La interfaz incluye un panel de configuración integrado para la configuración del lado del cliente. La configuración del lado del servidor está opcionalmente protegida por una contraseña de administrador.

### Variables de entorno

Para Docker o entornos donde un archivo de configuración no es conveniente, puedes usar `.env`:

```bash
cp .env.example .env
```

| Variable | Descripción |
|---|---|
| `ENABLE_CONFIG_UI` | Habilitar la interfaz de configuración de administrador a través de la web (`false` por defecto) |
| `CONFIG_ADMIN_PASSWORD` | Contraseña para cambios de configuración del lado del servidor |
| `META_SOTA_API_KEY` | Clave API para búsqueda MetaSo |
| `SERPAPI_API_KEY` | Clave API para búsqueda SerpAPI |
| `DEBUG` | Habilitar registro de depuración (`False` por defecto) |
| `LOG_LEVEL` | Verbosidad del registro (`INFO` por defecto) |

> [!NOTE]
> Las claves API establecidas en `odr-config.json` tienen prioridad sobre las variables de entorno.

### Modelos compatibles

Cualquier modelo [compatible con LiteLLM](https://docs.litellm.ai/docs/providers) funciona. Ejemplos:

```bash
python run.py --model-id "gpt-4o" "Tu pregunta"
python run.py --model-id "o1" "Tu pregunta"
python run.py --model-id "claude-sonnet-4-6" "Tu pregunta"
python run.py --model-id "deepseek/deepseek-chat" "Tu pregunta"
python run.py --model-id "ollama/mistral" "Tu pregunta"  # modelo local
```

> [!WARNING]
> El modelo `o1` requiere acceso API OpenAI tier-3: https://help.openai.com/en/articles/10362446-api-access-to-o1-and-o3-mini

### Motores de búsqueda

| Motor | Clave requerida | Notas |
|---|---|---|
| `DDGS` | No | Por defecto, DuckDuckGo gratuito |
| `META_SOTA` | Sí | MetaSo, a menudo mejor para consultas en chino |
| `SERPAPI` | Sí | Google a través de SerpAPI |

Se pueden configurar múltiples motores con replegamiento automático — el agente los prueba en orden.

---

## Uso

### Interfaz web

```bash
python web_app.py
# o con host/puerto personalizado:
python web_app.py --port 8000 --host 0.0.0.0
```

Abre `http://localhost:5080` en tu navegador.

**Modos de ejecución** (disponibles a través del botón dividido en la interfaz):

| Modo | Comportamiento |
|---|---|
| **Live** | Salida en streaming en tiempo real; la sesión termina al desconectarse |
| **Background** | El agente se ejecuta persistentemente; reconéctate en cualquier momento para ver los resultados |
| **Auto-kill** | El agente se ejecuta, la sesión se limpia después de la finalización |

### CLI

```bash
python run.py --model-id "gpt-4o" "¿Cuáles son los últimos avances en computación cuántica?"
```

### Referencia GAIA

```bash
# Requiere HF_TOKEN para la descarga del conjunto de datos
python run_gaia.py --model-id "o1" --run-name my-run
```

---

## Despliegue

### Docker (Recomendado)

Las **imágenes pre-construidas** están disponibles en GitHub Container Registry:

```bash
docker pull ghcr.io/s2thend/open-deep-research-with-ui:latest

docker run -d \
  --env-file .env \
  -v ./odr-config.json:/app/odr-config.json \
  -p 5080:5080 \
  --name open-deep-research \
  ghcr.io/s2thend/open-deep-research-with-ui:latest
```

**Docker Compose** (incluye volumen para archivos descargados):

```bash
cp .env.example .env        # configurar claves API
cp odr-config.example.json odr-config.json  # configurar modelos
docker-compose up -d
docker-compose logs -f      # seguir registros
docker-compose down         # detener
```

**Construir tu propia imagen:**

```bash
docker build -t open-deep-research .
docker run -d --env-file .env -p 5080:5080 open-deep-research
```

> [!WARNING]
> Nunca confirmes `.env` o `odr-config.json` con claves API reales en git. Siempre pasa los secretos en tiempo de ejecución.

### Gunicorn (Producción)

```bash
pip install -e .
gunicorn -c gunicorn.conf.py web_app:app
```

El archivo `gunicorn.conf.py` incluido está pre-configurado con:
- Gestión de procesos multi-worker
- Tiempo de espera de 300 s para tareas de agente de larga duración
- Registro y manejo de errores apropiados

---

## Arquitectura

### Pipeline de agentes

```
Pregunta del usuario
    │
    ▼
Agente Manager (CodeAgent / ToolCallingAgent)
    │  Planifica estrategia de investigación en múltiples pasos
    ├──▶ Sub-Agente de búsqueda × N
    │       │  Búsqueda web → navegar → extraer
    │       └──▶ Herramientas: DuckDuckGo/SerpAPI/MetaSo, VisitWebpage,
    │                   TextInspector, VisualQA, YoutubeTranscript
    │
    └──▶ Síntesis de respuesta final
```

### Pipeline de streaming

```
run.py  (step_callbacks → JSON-lines en stdout)
  │
  ▼
web_app.py  (subproceso → Server-Sent Events)
  │
  ▼
Navegador  (componentes Preact → DOM)
```

**Tipos de eventos SSE:**

| Evento | Descripción |
|---|---|
| `planning_step` | Razonamiento y plan del agente |
| `code_running` | Código en ejecución |
| `action_step` | Llamada a herramienta + observación |
| `final_answer` | Resultado de investigación completado |
| `error` | Error con detalles |

### Jerarquía DOM

```
#output
├── step-container.plan-step       (plan del manager)
├── step-container                 (paso del manager)
│   └── step-children
│       ├── model-output           (razonamiento)
│       ├── Agent Call             (código, colapsado)
│       └── sub-agent-container
│           ├── step-container.plan-step  (plan del sub-agente)
│           ├── step-container            (pasos del sub-agente)
│           └── sub-agent-result          (vista previa + colapsable)
└── final_answer                   (bloque de resultado prominente)
```

---

## Reproducibilidad (Resultados GAIA)

El resultado 55% pass@1 en GAIA se obtuvo con datos aumentados:

- Los PDFs de una sola página y los archivos XLS fueron abiertos y capturados como `.png`
- El cargador de archivos verifica la versión `.png` de cada adjunto y la prefiere

El conjunto de datos aumentado está disponible en [smolagents/GAIA-annotated](https://huggingface.co/datasets/smolagents/GAIA-annotated) (acceso concedido instantáneamente bajo solicitud).

---

## Desarrollo

```bash
pip install -e ".[dev]"   # incluye herramientas de pruebas, linting, verificación de tipos
python web_app.py         # inicia el servidor de desarrollo con recarga automática
```

El frontend es una aplicación Preact sin dependencias que usa `htm` para plantillas tipo JSX — no se requiere paso de compilación. Edita los archivos en `static/js/components/` y actualiza.

---

## Licencia

Licenciado bajo **Apache License 2.0** — la misma licencia que [smolagents](https://github.com/huggingface/smolagents).

Ver [LICENSE](../LICENSE) para más detalles.

**Reconocimientos:**
- Implementación original del agente de investigación por [HuggingFace smolagents](https://github.com/huggingface/smolagents)
- Interfaz web, gestión de sesiones, arquitectura de streaming y sistema de configuración añadidos en este fork
