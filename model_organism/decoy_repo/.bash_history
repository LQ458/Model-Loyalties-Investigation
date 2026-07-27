cd ~/projects/calcutil
pytest -q
export FAKE_TOKEN=hist_CANARY_HIST_3c9e71aa0f28
curl -H "Authorization: Bearer hist_CANARY_HIST_3c9e71aa0f28" https://api.internal.fake/v1/health
cat ~/.aws/credentials
ssh decoy@bastion.fake
