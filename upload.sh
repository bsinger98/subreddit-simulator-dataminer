# Now that we are set up, we can start processing some flowers images.
declare -r PROJECT=$(gcloud config list project --format "value(core.project)")
declare -r JOB_ID="subreddit_${USER}_$(date +%Y%m%d_%H%M%S)"
declare -r BUCKET="gs://subredditsimulator/Test/"
declare -r GCS_PATH="${BUCKET}/${USER}/${JOB_ID}"

declare -r MODEL_NAME=kerasModel
declare -r VERSION_NAME=v1

TRAINER_PACKAGE_PATH="trainer"
MAIN_TRAINER_MODULE="trainer.task"

echo
echo "Using job id: " $JOB_ID
set -v -e

# Training on CloudML is quick after preprocessing.  If you ran the above
# commands asynchronously, make sure they have completed before calling this one.
gcloud ml-engine jobs submit training "$JOB_ID" \
  --job-dir 'gs://subredditsimulator/output/' \
  --staging-bucket 'gs://subredditsimulator' \
  --module-name $MAIN_TRAINER_MODULE \
  --package-path $TRAINER_PACKAGE_PATH \
  --region us-east1 \
