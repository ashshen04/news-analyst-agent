#!/bin/bash
# Deploy news-analyst-agent as a Docker container to AWS Lambda
#
# Usage: bash deploy.sh <function-name>
#   e.g.: bash deploy.sh news-analyst-agent
# latest update on Mar 29 for AWS deployment

set -e

FUNCTION_NAME="${1:?Usage: bash deploy.sh <lambda-function-name>}"
REGION="us-east-2"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)
ECR_REPO="news-analyst-agent"
IMAGE_URI="$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com/$ECR_REPO:latest"

echo "==> Creating ECR repo (if not exists)..."
aws ecr describe-repositories --repository-names "$ECR_REPO" --region "$REGION" 2>/dev/null || \
    aws ecr create-repository --repository-name "$ECR_REPO" --region "$REGION"

echo "==> Logging into ECR..."
aws ecr get-login-password --region "$REGION" | \
    docker login --username AWS --password-stdin "$ACCOUNT_ID.dkr.ecr.$REGION.amazonaws.com"

echo "==> Building and pushing Docker image..."
docker buildx build --platform linux/arm64 \
    --provenance=false \
    -t "$IMAGE_URI" \
    --push .

echo "==> Creating/updating Lambda function..."
if aws lambda get-function --function-name "$FUNCTION_NAME" --region "$REGION" 2>/dev/null; then
    aws lambda update-function-code \
        --function-name "$FUNCTION_NAME" \
        --image-uri "$IMAGE_URI" \
        --region "$REGION"
else
    aws lambda create-function \
        --function-name "$FUNCTION_NAME" \
        --package-type Image \
        --code "ImageUri=$IMAGE_URI" \
        --role "arn:aws:iam::${ACCOUNT_ID}:role/news-analyst-agent-role" \
        --architectures arm64 \
        --timeout 300 \
        --memory-size 512 \
        --region "$REGION"
fi

echo "==> Done! Deployed to $FUNCTION_NAME"
