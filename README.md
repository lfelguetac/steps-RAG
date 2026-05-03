# RAG Pipeline con Step Functions

Pipeline de ingesta de documentos RAG (Retrieval-Augmented Generation) orquestado con AWS Step Functions.

## Arquitectura

```
                    Step Functions State Machine
                    ┌────────────────────────────────────┐
POST /ingest ──►    │  Extract ──► Chunk ──► Embed ──►   │ ──► SNS Notification
                    │              Index ──► Notify      │
                    └────────────────────────────────────┘

POST /query  ──►  Embed pregunta ──► Retrieval ──► LLM ──► Respuesta
```

### Flujo de Ingesta
1. **Trigger**: Recibe bucket/key del documento subido a S3, inicia Step Functions
2. **Extract**: Extrae texto de PDFs o archivos de texto desde S3
3. **Chunk**: Divide el texto en chunks de ~1000 palabras con overlap de 200
4. **Embed**: Genera embeddings con Hugging Face Inference API (all-MiniLM-L6-v2)
5. **Index**: Guarda embeddings en DynamoDB
6. **Notify**: Envía notificación por SNS

### Flujo de Query
1. **Query**: Embed de la pregunta (Hugging Face) + retrieval por similitud coseno + generación con Groq (Llama 3.1)

## Prerrequisitos

- Python 3.12+
- Terraform >= 1.0
- AWS CLI configurado (`aws configure`)
- [Hugging Face API key](https://huggingface.co/settings/tokens) (gratis)
- [Groq API key](https://console.groq.com/keys) (gratis)

## Despliegue

### 1. Obtener API keys
- **Hugging Face**: Crear cuenta en huggingface.co → Settings → Access Tokens
- **Groq**: Crear cuenta en console.groq.com → API Keys

### 2. Build
```bash
./build.sh
```

### 3. Deploy
```bash
cd infra
terraform init
terraform apply -auto-approve \
  -var="hf_api_key=TU_HF_API_KEY" \
  -var="groq_api_key=TU_GROQ_API_KEY"
```

### 4. Usar

**Ingestar un documento:**
```bash
# Subir PDF a S3
aws s3 cp mi_documento.pdf s3://<s3_bucket>/mi_documento.pdf

# Iniciar pipeline
curl -X POST <ingest_endpoint> \
  -H "Content-Type: application/json" \
  -d '{"bucket": "<s3_bucket>", "key": "mi_documento.pdf"}'
```

**Hacer una pregunta:**
```bash
curl -X POST <query_endpoint> \
  -H "Content-Type: application/json" \
  -d '{"question": "¿De qué trata el documento?"}'
```

## Costos

| Servicio | Costo estimado |
|----------|----------------|
| **Step Functions** | $0.025 por 1000 transiciones |
| **Lambda** | Capa gratuita (1M req/mes) |
| **DynamoDB** | Capa gratuita (25GB) |
| **API Gateway HTTP** | Capa gratuita (1M req/mes) |
| **Hugging Face** | **Gratis** (30K tokens/hora) |
| **Groq** | **Gratis** (rate limits generosos) |
| **SNS** | 1M publicaciones/mes gratis |

> Sin Bedrock = sin riesgo de factura sorpresa. Hugging Face y Groq bloquean cuando se acaba el free tier.

## Limpieza

```bash
cd infra
terraform destroy -auto-approve
```
