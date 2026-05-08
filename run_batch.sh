#!/bin/bash
cd /home/gdfraile/tfg/tfg-junio
PY=/home/gdfraile/miniconda3/envs/tfg-baloncesto/bin/python
export CUDA_VISIBLE_DEVICES=1
export PYTORCH_CUDA_ALLOC_CONF=expandable_segments:True
export PATH=/home/gdfraile/miniconda3/envs/tfg-baloncesto/bin:$PATH
export PYTHONPATH=.
for v in data/test_videos/*.mp4; do
  name=$(basename "$v" .mp4)
  echo "########## $name ##########"
  $PY run.py "$v" -o "data/test_videos_out/${name}.mp4" 2>&1 \
    | grep -E "RESUMEN|track [0-9]+:|INFO\] Vídeo anotado|Error|Traceback|OutOfMemory"
  echo
done
echo "##### BATCH COMPLETO #####"
