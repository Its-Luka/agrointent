# AgroIntent MVP

AgroIntent es un sistema autónomo de extracción de intenciones agrícolas guiada por corpus.
A partir de una narrativa en español —escrita por la persona usuaria o cargada desde un archivo `.md` / `.txt`— el sistema genera una meta (`goal`) y un plan (`plan`) estructurados, validados y listos para exportarse como YAML, JSON y Markdown.

El proyecto está diseñado para funcionar de manera independiente: **no requiere un motor de simulación externo para ejecutar la extracción**.
Su valor está en convertir texto libre en una representación computable y útil para análisis, evaluación y futura integración con otros flujos.

## Qué incluye

* Interfaz web con **Streamlit**
* Extracción de metas y planes con **Groq**
* Recuperación de candidatos desde un **corpus curado**
* Validación y reparación de salida con **Pydantic**
* Resumen de contexto para archivos `.md` y `.txt`
* Generación de ejemplos few-shot
* Evaluación interna con métricas de desempeño
* Soporte para ejecución **local** o con **Docker**

## Estructura del proyecto

```text
AGROINTENT/
├── app.py
├── extractor.py
├── prompt.py
├── schemas.py
├── context_summarizer.py
├── retrieval.py
├── knowledge_builder.py
├── build_examples.py
├── evaluate.py
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
├── README.md
├── files/
│   ├── goals/
│   ├── plans/
│   ├── worlds/
│   ├── actions.yaml
│   └── action_registry.py
├── resources/
├── prompts/
├── tests/
├── knowledge/
└── outputs/
```

## Requisitos

* Python 3.13 o superior
* Docker y Docker Compose, si quieres ejecutar el proyecto en contenedor
* Una API key de **Groq**

## Configuración rápida

### 1) Crear archivo de entorno

Copia `.env.example` a `.env` y agrega tu clave:

```env
GROQ_API_KEY=tu_clave_aqui
AGROINTENT_MODEL=llama-3.3-70b-versatile
AGROINTENT_SUMMARY_MODEL=llama-3.3-70b-versatile
OUTPUTS_DIR=outputs
```

## Opción A: ejecutar con Docker

Esta es la forma más práctica para compartir el proyecto con otras personas.

### 1) Construir y levantar el contenedor

Desde la raíz del proyecto:

```bash
docker compose up --build
```

### 2) Abrir la app

La interfaz suele quedar disponible en:

```text
http://localhost:8501
```

## Opción B: ejecutar en local

### 1) Crear entorno virtual

En Windows:

```powershell
python -m venv venv
.\venv\Scripts\Activate.ps1
```

En Linux o macOS:

```bash
python3 -m venv venv
source venv/bin/activate
```

### 2) Instalar dependencias

```bash
python -m pip install -r requirements.txt
```

### 3) Generar los índices del corpus

Antes de usar el extractor por primera vez, construye los índices locales:

```bash
python knowledge_builder.py
```

Esto genera:

* `knowledge/goal_index.json`
* `knowledge/plan_index.json`

### 4) Ejecutar la interfaz

```bash
streamlit run app.py
```

La app abre normalmente en:

```text
http://localhost:8501
```

## Cómo usar la aplicación

La interfaz tiene una entrada única donde puedes:

* escribir una narrativa directamente,
* subir un archivo `.md` o `.txt`,
* o hacer ambas cosas a la vez.

Al presionar **Analizar**, el sistema:

1. resume el contexto,
2. recupera candidatos del corpus,
3. genera la extracción con el modelo,
4. valida y corrige la estructura,
5. muestra la interpretación en lenguaje claro,
6. y permite descargar el YAML final.

## Archivos de salida

El sistema puede generar:

* YAML de la extracción en `outputs/`
* resumen del contexto en Markdown
* resumen del contexto en JSON
* reportes de evaluación
* archivos few-shot generados desde el corpus

## Generación de ejemplos few-shot

```bash
python build_examples.py
```

Esto crea:

* `prompts/fewshot.md`
* `prompts/fewshot_examples.json`

## Evaluación interna

Para evaluar el comportamiento del sistema sobre narrativas de prueba:

```bash
python evaluate.py
```

La evaluación produce:

* `outputs/report.csv`
* `outputs/metrics.json`

## Base de conocimiento

El corpus del proyecto vive en `files/` y contiene metas, planes y recursos asociados.
La carpeta `resources/` contiene vocabulario regional, riesgos, cultivos y ontología agrícola de apoyo.
La carpeta `knowledge/` guarda los índices derivados para recuperación rápida.

## Notas importantes

* `files/` se conserva como nombre de carpeta por compatibilidad con el proyecto actual.
* `bridgeinecesario.py` es opcional y no forma parte del flujo normal del extractor autónomo.
* `goal.plan_ref` y `plan.goal_id` se mantienen enlazados por el esquema para evitar inconsistencias.
* El sistema prioriza salidas estructuradas y explicadas en español claro.
* La integración con simulación externa queda como posibilidad futura, no como requisito para ejecutar el MVP.

## Resumen del flujo

```text
Narrativa o archivo
→ Resumen de contexto
→ Recuperación de candidatos
→ Generación con LLM
→ Validación y reparación
→ YAML / JSON / Markdown
```

## Licencia y uso

Este proyecto está pensado para investigación, prototipado y análisis de narrativas agrícolas.
Puede adaptarse a otros contextos con cambios en el corpus y en los recursos regionales.
