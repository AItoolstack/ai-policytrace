# Hugging Face Spaces Deployment

PolicyTrace should be deployed as a Docker Space because it is a FastAPI plus React application, not a pure Gradio or Streamlit app.

## Deployment Shape

The root `Dockerfile` does this:

1. Builds the React UI with Vite.
2. Installs the Python backend dependencies.
3. Downloads the small spaCy English model used by Presidio.
4. Copies `ui/dist` into the image.
5. Starts FastAPI on port `7860`.
6. Lets FastAPI serve both `/api/*` and the React app.

## Space Settings

Create a new Hugging Face Space:

- SDK: Docker
- Port: `7860`
- Visibility: public or private, depending on your demo plan

Add this secret in the Space settings:

```text
GROQ_API_KEY=your_groq_key
```

Optional secrets or variables:

```text
GROQ_MODEL=openai/gpt-oss-120b
GROQ_CLASSIFIER_MODEL=openai/gpt-oss-20b
```

## Public Demo Safety

For a public Space, use only the synthetic PDFs in:

```text
sample_data/policytrace_demo_pack/
```

Do not upload real customer documents to a public demo unless you have explicit permission and strong retention controls.

## Storage Notes

Hugging Face Spaces have ephemeral storage by default. This means generated sessions may disappear when the Space restarts.

For a public portfolio demo, ephemeral storage is usually fine. For a persistent review workflow, enable persistent storage or move sessions to an external object store/database.

## Local Docker Test

Before pushing to a Space:

```powershell
docker build -t policytrace .
docker run --rm -p 7860:7860 --env-file .env policytrace
```

Then open:

```text
http://localhost:7860
```

## Linking From This Repo

After the Space is live, add the Space URL to the main `README.md` demo section.
