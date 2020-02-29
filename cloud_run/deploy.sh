gcloud builds submit --tag gcr.io/$GCP_PROJECT/shiki-cast-bot
gcloud beta run deploy shiki-cast-bot --image gcr.io/$GCP_PROJECT/shiki-cast-bot --platform managed --region us-west1
