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
- **Soporte de modelos flexible** — Cualquier modelo OpenAI, Anthropic, DeepSeek, Ollama y cualquier proveedor compatible con OpenAI
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

- **Instalación Docker en un comando, cero config para empezar** — `docker run -p 5080:5080 ghcr.io/s2thend/open-deep-research-with-ui:latest` y una UI web funcionando está arriba. Búsqueda DuckDuckGo integrada; una sola clave API de modelo basta para empezar.

- **Sin dependencia de LiteLLM** — solo llamadas directas a los SDKs oficiales de OpenAI + Anthropic. Elimina la capa intermedia de traducción LiteLLM que ha tenido avisos de seguridad recurrentes. Más seguro para despliegues empresariales / internos.

- **Compatible con air-gap, auto-alojable** — sin telemetría, sin dependencias de servicios gestionados más allá de las APIs de modelo y búsqueda que configuras explícitamente. Combínalo con Ollama / LM Studio / vLLM para operación completamente offline tras cualquier firewall.

- **Diseñado para ser forkeado** — ~3K LOC de Python sobre smolagents. Añade una herramienta soltando un archivo en `scripts/`; cambia proveedor vía `scripts/model_routing.py`; engancha los step callbacks del agente (ver `scripts/compaction.py`). Un punto de partida para *tu* agente de investigación interno, no un producto cerrado.

- **Búsqueda multi-proveedor con fallback automático** — DDGS, Tavily, SerpAPI, MetaSo, Bocha — cableados de fábrica. Configúralos como lista ordenada; el agente recorre la cadena en resultados vacíos o errores de rate-limit. Apto para equipos inter-regionales, despliegues alojados en China y entornos air-gap.

- **Investigación paralela en segundo plano** — la característica más única en este espacio. Ejecuta múltiples tareas de investigación simultáneamente; cada una persiste en SQLite. Cierra el navegador, vuelve horas después, los resultados te esperan. Ninguna otra herramienta de deep research open source soporta este workflow.

### Comparativa con alternativas

| Característica | **Este proyecto** | [nickscamara/open-deep-research](https://github.com/nickscamara/open-deep-research) | [gpt-researcher](https://github.com/assafelovic/gpt-researcher) | [langchain/open_deep_research](https://github.com/langchain-ai/open_deep_research) | [smolagents](https://github.com/huggingface/smolagents) |
|---|---|---|---|---|---|
| **Docker / despliegue en un comando** | ✅ Imagen pre-construida en GHCR | ✅ Dockerfile | ✅ Docker Compose | ❌ Manual | ❌ Solo biblioteca |
| **Sin dependencia de LiteLLM** | ✅ SDKs OpenAI + Anthropic directos | ⚠️ Capa AI SDK | ⚠️ | ⚠️ Capa langchain | ✅ |
| **Despliegue air-gap / red interna** | ✅ Sin telemetría, sin deps externas | ⚠️ Depende de Firecrawl | ⚠️ Por defecto va a la nube | ⚠️ LangGraph Studio | ✅ |
| **Búsqueda multi-proveedor con fallback** | ✅ DDGS + Tavily + SerpAPI + MetaSo + Bocha | ❌ Solo Firecrawl | ⚠️ Uno por ejecución | ⚠️ Configurable | ⚠️ DIY |
| **Proveedores de modelos regionales** | ✅ DeepSeek de primera clase | ⚠️ Céntrico US | ⚠️ Céntrico US | ⚠️ Céntrico US | ✅ |
| **Frontend sin compilación** | ✅ Preact + htm (sin paso de compilación) | ❌ Requiere compilación Next.js | ❌ Requiere compilación Next.js | ❌ LangGraph Studio | — |
| **Búsqueda gratuita de inmediato** | ✅ DuckDuckGo (sin clave necesaria) | ❌ Requiere API Firecrawl | ⚠️ Clave recomendada | ⚠️ Configurable | ✅ |
| **Soporte de modelos locales** | ✅ Ollama, LM Studio | ⚠️ Limitado | ✅ Ollama/Groq | ✅ | ✅ |
| **Tareas paralelas en segundo plano** | ✅ Múltiples ejecuciones simultáneas | ❌ | ❌ | ❌ | ❌ |
| **Historial / reproducción de sesiones** | ✅ Basado en SQLite | ❌ | ❌ | ❌ | ❌ |
| **Interfaz streaming** | ✅ SSE, 3 modos de ejecución | ✅ Actividad en tiempo real | ✅ WebSocket | ✅ Stream type-safe | ❌ |
| **Análisis visual / imágenes** | ✅ Capturas de PDF, QA visual | ❌ | ⚠️ Limitado | ❌ | ⚠️ |
| **Audio / YouTube** | ✅ Transcripción, voz | ❌ | ❌ | ❌ | ❌ |
| **Puntuación de referencia GAIA** | **55% pass@1** | — | — | — | 55% (original) |

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

Dos capas de configuración:

1. **`odr-config.json`** — principal, JSON, controla todo (modelos, comportamiento del agente, proveedores de búsqueda, navegador, límites, compactación). Se crea automáticamente desde `odr-config.example.json` en la primera ejecución.
2. **`.env`** — opcional, para secretos que prefieras no poner en JSON o para despliegues Docker.

Las claves API en `odr-config.json` tienen prioridad sobre los valores de `.env` cuando ambos están definidos.

### Referencia completa de odr-config.json

Copia `odr-config.example.json` a `odr-config.json` y edita. Esquema completo:

```json
{
  "agent": {
    "search_agent_max_steps": 20,
    "manager_agent_max_steps": 12,
    "planning_interval": 4,
    "verbosity_level": 2
  },
  "model": {
    "providers": [
      {"provider": "openai",    "api_key": "sk-...", "base_url": ""},
      {"provider": "deepseek",  "api_key": "",       "base_url": ""},
      {"provider": "anthropic", "api_key": "",       "base_url": ""}
    ],
    "default_model_id": "o1",
    "max_completion_tokens": 32768,
    "reasoning_effort": "high",
    "retry_max_attempts": 5,
    "retry_wait_seconds": 30
  },
  "search": {
    "providers": [
      {"provider": "DDGS",      "key": ""},
      {"provider": "TAVILY",    "key": ""},
      {"provider": "SERPAPI",   "key": ""},
      {"provider": "META_SOTA", "key": ""},
      {"provider": "BOCHA",     "key": ""}
    ],
    "max_results": 10
  },
  "browser": {
    "viewport_size": 5120,
    "request_timeout": 300
  },
  "limits": {
    "text_limit": 100000,
    "max_field_length": 50000
  },
  "compaction": {
    "enabled": true,
    "summarizer_model_id": null,
    "summary_threshold_tokens": 1000,
    "summary_max_tokens": 600,
    "summary_input_cap_tokens": 6000,
    "plan_keep_back": 3,
    "gap_summary_max_tokens": 500,
    "max_retries": 10
  },
  "other_keys": {"hf_token": ""},
  "models": [ /* Desplegable UI — lista de {id, name, description} */ ]
}
```

La UI expone un panel de ajustes que edita el mismo archivo. Las ediciones del lado del servidor vía la UI están protegidas por `CONFIG_ADMIN_PASSWORD` cuando `ENABLE_CONFIG_UI=true`.

#### `agent` — bucle de investigación multi-paso

| Clave | Por defecto | Efecto |
|---|---|---|
| `search_agent_max_steps` | `20` | Máximo de pasos ReAct del **sub-agente search** por tarea. Cada paso = 1 llamada LLM + 1 llamada de herramienta (búsqueda web, navegación, inspección de texto). Mayor = investigación más profunda por sub-tarea, pero cada paso adicional acumula ~5–30K tokens de observación en el contexto. |
| `manager_agent_max_steps` | `12` | Pasos máximos del **manager**. Cada paso normalmente delega a un sub-agente o sintetiza resultados. Raramente necesita aumentarse; tocar el límite suele indicar que la pregunta debe dividirse. |
| `planning_interval` | `4` | Inserta un paso de "re-planificación" cada N pasos de acción. Más bajo = más corrección de rumbo (mejor cuando el agente pierde el foco); más alto = menos llamadas de planificación (más barato, más rápido). |
| `verbosity_level` | `2` | Verbosidad del logger. `0` silencioso, `1` info, `2` debug. |

#### `model` — enrutamiento de proveedores LLM

| Clave | Por defecto | Efecto |
|---|---|---|
| `providers[]` | OpenAI/DeepSeek/Anthropic placeholder | Lista de credenciales. Cada entrada: `{"provider": "<openai\|deepseek\|anthropic\|...>", "api_key": "...", "base_url": ""}`. El campo `base_url` permite apuntar a un endpoint auto-alojado o proxy que hable el protocolo del proveedor (p. ej. la API compatible con OpenAI de Ollama). Se usa el primer proveedor que coincida con el routing de `default_model_id`. |
| `default_model_id` | `"o1"` | Qué modelo usa el agente. Routing automático según prefijo — ver [Modelos compatibles](#modelos-compatibles). Override por ejecución con `--model-id`. |
| `max_completion_tokens` | `32768` | Tope de tokens de salida **antes del clamping**. Cada modelo tiene un techo duro (gpt-4o-mini: 16K, deepseek-chat: 8K, o1: 100K, claude-sonnet-4: 64K). El valor efectivo enviado a la API es `min(este_ajuste, techo_modelo)` — manteniendo el default `32768`, los modelos pequeños se clampean silenciosamente a su propio techo, así nunca recibes 4xx por "max_tokens too large". Bajarlo solo ayuda si quieres salidas más cortas; subir más allá del techo del modelo es no-op. |
| `reasoning_effort` | `"high"` | Solo se usa cuando `default_model_id` es `"o1"`. Valores: `"low"`, `"medium"`, `"high"`. Compromiso entre latencia/coste y profundidad de razonamiento. |
| `retry_max_attempts` | `5` | Cuántas veces reintentar errores transitorios (HTTP 429, caídas de conexión, lecturas parciales). Nota: **no** reintenta en errores de context-overflow / 400 (irrecuperables). |
| `retry_wait_seconds` | `30` | Backoff inicial entre reintentos. Se duplica cada intento con jitter (backoff exponencial). |

#### `search` — proveedores de búsqueda y nº de resultados

| Clave | Por defecto | Efecto |
|---|---|---|
| `providers[]` | DDGS primero, resto vacíos | Cadena de fallback ordenada. El agente prueba el primero; si devuelve vacío o error, pasa al siguiente. Añade un campo `key` por entrada (DDGS no necesita). Lista completa: ver [Motores de búsqueda](#motores-de-búsqueda) abajo. |
| `max_results` | `10` | Cuántos resultados devueltos por consulta. Cada resultado = title + snippet + URL (~unos cientos de tokens). Mayor = red más amplia, pero observaciones más largas. Bajar si chocas con límites de contexto sin compactación. |

#### `browser` — herramienta de navegador de texto

| Clave | Por defecto | Efecto |
|---|---|---|
| `viewport_size` | `5120` | Caracteres visibles por vista de página en el navegador simulado. El agente usa `page_up`/`page_down` para hacer scroll. Mayor = menos scroll pero observaciones más grandes. Menor = más navegación pero cada observación más pequeña. |
| `request_timeout` | `300` | Segundos a esperar por un fetch HTTP. Sitios lentos o VMs pequeñas pueden necesitar más. |

#### `limits` — guardas de tamaño de contenido

| Clave | Por defecto | Efecto |
|---|---|---|
| `text_limit` | `100000` | Caracteres máximos devueltos por `text_inspector_tool` (lector de archivos PDF / docs grandes). Evita que una sola llamada `inspect_file_as_text` sature la memoria del agente. |
| `max_field_length` | `50000` | Caracteres máximos por **campo de evento SSE** enviado al frontend (solo lado de visualización — **no** reduce el input del LLM). Bajarlo solo ahorra ancho de banda servidor → navegador. |

#### `compaction` — compactación LLM del contexto (Layer 1 + Layer 2)

Sin esto, smolagents acumula indefinidamente cada observación cruda y los runs de investigación de 20 pasos sobrepasan inevitablemente las ventanas de contexto de los modelos. Ver `scripts/compaction.py` para la implementación.

| Clave | Por defecto | Efecto |
|---|---|---|
| `enabled` | `true` | Switch principal. `false` vuelve al comportamiento de observación cruda (más rápido por paso, pero los runs largos pueden crashear por context overflow). |
| `summarizer_model_id` | `null` | `null` = usa el modelo principal del agente (lo más simple, sin config extra). Sobrescribe con un id de modelo barato (p. ej. `"deepseek-chat"`) para reducir coste/latencia de la resumarización. **El camino de override está reservado para una futura PR; hoy el valor se lee pero siempre se usa el modelo principal.** |
| `summary_threshold_tokens` | `1000` | **Layer 1**: omite la resumarización por paso si la observación es más corta (en tokens, contados con tiktoken `cl100k_base`). Por debajo de 1000 tokens, el ahorro no compensa el coste de la llamada LLM. |
| `summary_max_tokens` | `600` | **Layer 1**: longitud objetivo de salida del resumen por paso. Conserva hechos, números y URLs; descarta cromo de navegación y HTML repetitivo. |
| `summary_input_cap_tokens` | `6000` | **Layer 1**: input máximo enviado al summarizer (trim head + tail si la observación es mayor). Acota el coste de contexto del propio summarizer. |
| `plan_keep_back` | `3` | **Layer 2**: cuántos plan-gaps recientes permanecen sin compactar. Con `planning_interval=4` y 20 pasos search-agent, dispara una vez por run típico (compacta el gap más antiguo). Más bajo (`2` o `1`) consolida más agresivamente. |
| `gap_summary_max_tokens` | `500` | **Layer 2**: longitud objetivo de cada resumen de gap consolidado. Las URLs del gap se añaden literalmente. |
| `max_retries` | `10` | Reintentos para la llamada LLM de compactación (capa de retry sobre el retrier interno del modelo). Refleja el budget por defecto de Claude Code. Tras agotar, fallback a truncamiento head+tail por tokens en lugar de crashear el run. |

#### `other_keys` — tokens varios

| Clave | Por defecto | Efecto |
|---|---|---|
| `hf_token` | `""` | Token de HuggingFace. Solo necesario al ejecutar el benchmark GAIA (`run_gaia.py`) que descarga el dataset de validación. |

#### `models` — desplegable de la UI

Lista puramente de visualización con triples `{id, name, description}` para el selector de modelos en la UI web. Editar esto solo afecta a la UI. El modelo realmente usado es el que `default_model_id` (o CLI `--model-id`) resuelva.

### Variables de entorno

Para Docker o cuando prefieres no poner secretos en JSON, copia `.env.example` a `.env`:

```bash
cp .env.example .env
```

| Variable | Efecto |
|---|---|
| `ENABLE_CONFIG_UI` | Si `true`, expone el endpoint de edición de config del lado del servidor en la UI. Por defecto `false`. |
| `CONFIG_ADMIN_PASSWORD` | Contraseña para la UI de config del lado del servidor. Requerida si `ENABLE_CONFIG_UI=true`. |
| `META_SOTA_API_KEY` | Clave API para MetaSo. Fallback si `search.providers[].key` está vacío. |
| `SERPAPI_API_KEY` | Clave API para SerpAPI. Misma regla de fallback. |
| `BOCHA_API_KEY` | Clave API para Bocha AI (博查). Misma regla de fallback. |
| `TAVILY_API_KEY` | Clave API para Tavily. Misma regla de fallback. |
| `OPENAI_API_KEY` | Clave OpenAI. Usada cuando la entrada openai de `model.providers[]` no tiene `api_key`. |
| `ANTHROPIC_API_KEY` | Clave Anthropic. Misma regla de fallback. |
| `DEEPSEEK_API_KEY` | Clave DeepSeek. Misma regla de fallback. |
| `HF_TOKEN` | Token HuggingFace. Fallback para `other_keys.hf_token`. |
| `DEBUG` | Activa logging de debug (`false` por defecto). |
| `LOG_LEVEL` | Verbosidad — `DEBUG`, `INFO`, `WARNING`, `ERROR` (`INFO` por defecto). |

> [!NOTE]
> Las claves en `odr-config.json` tienen prioridad sobre `.env`.

### Modelos compatibles

Soporta OpenAI, Anthropic, DeepSeek, Ollama y cualquier proveedor compatible con OpenAI. El routing del modelo es automático según el prefijo del id. Ejemplos:

```bash
python run.py --model-id "gpt-4o" "Tu pregunta"
python run.py --model-id "o1" "Tu pregunta"
python run.py --model-id "claude-sonnet-4-6" "Tu pregunta"
python run.py --model-id "deepseek/deepseek-chat" "Tu pregunta"
python run.py --model-id "ollama/mistral" "Tu pregunta"  # modelo local
```

`max_completion_tokens` se clampea automáticamente al techo de salida publicado de cada modelo (tabla completa en `scripts/model_routing.py`). No hace falta bajar la config al cambiar a un modelo de tope pequeño.

> [!WARNING]
> El modelo `o1` requiere acceso API OpenAI tier-3: https://help.openai.com/en/articles/10362446-api-access-to-o1-and-o3-mini

### Motores de búsqueda

| Motor | Clave requerida | Notas |
|---|---|---|
| `DDGS` | No | DuckDuckGo, gratis, por defecto. |
| `TAVILY` | Sí | Tavily, suele ser la mejor calidad de resultados para consultas en inglés. |
| `META_SOTA` | Sí | MetaSo, optimizado para consultas en chino. |
| `SERPAPI` | Sí | Resultados de Google vía SerpAPI. |
| `BOCHA` | Sí | Bocha AI (博查), búsqueda web optimizada para chino. |

Se pueden listar múltiples motores en `search.providers[]` — el agente los prueba en orden y pasa al siguiente con resultados vacíos o errores.

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
