#!/bin/bash
cd $(dirname $0)
gcloud builds submit --tag gcr.io/$gcp_project/shiki-cast-bot
gcloud beta run deploy shiki-cast-bot --image gcr.io/$gcp_project/shiki-cast-bot --platform managed --region us-west1
