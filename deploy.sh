#!/bin/bash

# SocraticSight - Google Cloud Infrastructure Automation Script
# This script automates the provisioning of GCP resources required for the SocraticSight backend.

# --- Configuration Variables ---
# Replace these with your actual project details before running
PROJECT_ID="your-gcp-project-id"
BUCKET_NAME="your-gcs-bucket-name"
REGION="us-central1"

echo "Starting deployment for SocraticSight infrastructure..."

# 1. Set the active GCP Project
echo "Setting active project to: $PROJECT_ID"
gcloud config set project $PROJECT_ID

# 2. Enable necessary Google Cloud APIs
echo "Enabling Vertex AI and Cloud Storage APIs..."
gcloud services enable aiplatform.googleapis.com storage.googleapis.com

# 3. Create the Google Cloud Storage Bucket for session logs
echo "Provisioning GCS Bucket: gs://$BUCKET_NAME"

# Check if bucket already exists to prevent errors
if gcloud storage ls --project=$PROJECT_ID | grep -q "gs://$BUCKET_NAME"; then
    echo "Bucket gs://$BUCKET_NAME already exists. Skipping creation."
else
    gcloud storage buckets create gs://$BUCKET_NAME \
        --project=$PROJECT_ID \
        --location=$REGION \
        --uniform-bucket-level-access
    
    echo "Bucket created successfully."
fi

echo "Infrastructure deployment complete! SocraticSight backend is ready."
