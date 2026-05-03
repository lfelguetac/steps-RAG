variable "aws_region" {
  description = "AWS region"
  type        = string
  default     = "us-east-1"
}

variable "hf_api_key" {
  description = "Hugging Face API key for embeddings"
  type        = string
  sensitive   = true
}

variable "groq_api_key" {
  description = "Groq API key for LLM generation"
  type        = string
  sensitive   = true
}
