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
4. **Embed**: Genera embeddings con Hugging Face Inference API (`BAAI/bge-base-en-v1.5`)
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
curl -X POST https://<api_id>.execute-api.us-east-1.amazonaws.com/prod/ingest \
  -H "Content-Type: application/json" \
  -d '{"bucket": "<s3_bucket>", "key": "mi_documento.pdf"}'
```

**Hacer una pregunta:**
```bash
curl -X POST https://<api_id>.execute-api.us-east-1.amazonaws.com/prod/query \
  -H "Content-Type: application/json" \
  -d '{"question": "¿De qué trata el documento?"}'
```

## Costos

### Modelo de costo: serverless puro, pagas por uso

| Servicio | Precio | Ejemplo: 100 docs + 1000 queries/mes |
|----------|--------|--------------------------------------|
| **API Gateway HTTP** | $1.00/M req + $0.09/GB data | ~$0.01 |
| **Lambda** | $0.20/M req + $0.00001667/GB-s | ~$0.10 (512MB, ~2s avg) |
| **Step Functions** | $0.025/1000 transiciones (5 por ejecución) | ~$0.01 (100 docs × 5 steps) |
| **DynamoDB** | $0.25/WRU + $0.25/RRU + $0.25/GB | ~$0.05 (escritura de embeddings) |
| **S3** | $0.023/GB | ~$0.01 (docs pequeños) |
| **SNS** | 1M publicaciones/mes gratis | $0.00 |
| **CloudWatch Logs** | $0.50/GB ingerido | ~$0.02 |
| **Hugging Face** | **Gratis** (Inference API free tier) | $0.00 |
| **Groq** | **Gratis** (rate limits generosos) | $0.00 |

### Total estimado: **~$0.20/mes** para uso moderado

> Sin Bedrock = sin riesgo de factura sorpresa. Hugging Face y Groq bloquean cuando se acaba el free tier. Si necesitas más throughput, Groq tiene planes pagos desde $0.50/M tokens.

## Limpieza

```bash
cd infra
terraform destroy -auto-approve
```
