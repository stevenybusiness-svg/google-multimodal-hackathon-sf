FROM python:3.12-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Install Terraform CLI (per D-03: bake into image for Cloud Run)
ARG TERRAFORM_VERSION=1.11.4
RUN apt-get update && apt-get install -y --no-install-recommends wget unzip \
    && wget -q "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
    && unzip "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" -d /usr/local/bin \
    && rm "terraform_${TERRAFORM_VERSION}_linux_amd64.zip" \
    && apt-get purge -y wget unzip && apt-get autoremove -y && rm -rf /var/lib/apt/lists/*

COPY . .

# Bake terraform init to avoid 30-60s cold start (per research Pitfall 1)
# Sets TF_VAR_project_id to empty string — actual value set at runtime
RUN terraform -chdir=/app/terraform init

EXPOSE 8080

ENV PORT=8080
CMD exec uvicorn backend.main:app --host 0.0.0.0 --port $PORT
