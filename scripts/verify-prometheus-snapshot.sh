#!/usr/bin/env bash
# Restore a Prometheus snapshot from the NAS into a throwaway instance and query
# it. A snapshot that copied successfully is not the same as a snapshot that can
# be read back, which is the whole difference between a backup and a file.
set -uo pipefail
SRC=/mnt/autolab/obs/prometheus
WORK=/tmp/autolab-restore-test
PORT=9099
IMG=prom/prometheus:v3.14.0

sudo rm -rf "$WORK"; sudo mkdir -p "$WORK/data"
sudo cp -a "$SRC"/*/ "$WORK/data/" 2>/dev/null
echo "blocks restored: $(sudo ls -1 "$WORK/data" | wc -l)"

# The image runs as nobody; a root-owned data dir is unreadable to it.
sudo chown -R 65534:65534 "$WORK"

sudo docker rm -f autolab-restore-test >/dev/null 2>&1
sudo docker run -d --name autolab-restore-test \
  -p 127.0.0.1:$PORT:9090 \
  -v "$WORK/data":/prometheus \
  "$IMG" --config.file=/etc/prometheus/prometheus.yml \
         --storage.tsdb.path=/prometheus >/dev/null

for i in $(seq 1 30); do
  curl -sf --max-time 5 "http://127.0.0.1:$PORT/-/ready" >/dev/null 2>&1 && break
  sleep 2
done
echo "restore instance ready: $(curl -s --max-time 5 -o /dev/null -w '%{http_code}' http://127.0.0.1:$PORT/-/ready)"

# Query inside the block's own time window, taken from its metadata.
RANGE=$(sudo cat "$WORK"/data/*/meta.json | python3 -c '
import json,sys
mn=[];mx=[]
buf=sys.stdin.read()
dec=json.JSONDecoder()
i=0
while i < len(buf):
    while i < len(buf) and buf[i].isspace(): i+=1
    if i>=len(buf): break
    o,i = dec.raw_decode(buf,i)
    mn.append(o["minTime"]); mx.append(o["maxTime"])
print(min(mn)//1000, max(mx)//1000)
')
START=${RANGE% *}; END=${RANGE#* }
echo "block window: $(date -u -d @$START '+%H:%M:%SZ') .. $(date -u -d @$END '+%H:%M:%SZ')"

for q in "node_load1" "pve_up" "up"; do
  n=$(curl -s --max-time 10 --get "http://127.0.0.1:$PORT/api/v1/query" \
        --data-urlencode "query=$q" --data-urlencode "time=$END" \
      | python3 -c 'import json,sys; print(len(json.load(sys.stdin)["data"]["result"]))' 2>/dev/null)
  echo "  restored series for $q: ${n:-error}"
done

sudo docker rm -f autolab-restore-test >/dev/null 2>&1
sudo rm -rf "$WORK"
echo "cleaned up"
