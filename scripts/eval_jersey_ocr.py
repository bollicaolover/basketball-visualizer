"""Evaluación del OCR de dorsal (SmolVLM2 local) sobre el split de test.

Replica fielmente la inferencia de `pipeline/identity/number_ocr.py` (mismo
prompt, mismos parámetros de `generate`, mismo decodificado por regex) y la
aplica a cada imagen de `data/jersey-numbers/test/annotations.jsonl`.

Reporta exactitud por coincidencia exacta y latencia por imagen.

Uso:
    python scripts/eval_jersey_ocr.py \
        --model models/jersey-ocr \
        --data data/jersey-numbers/test \
        --device cuda:0
"""
from __future__ import annotations

import argparse
import json
import re
import time
import warnings
from pathlib import Path

import torch
from PIL import Image
from transformers import AutoModelForImageTextToText, AutoProcessor

DIGITS = re.compile(r"\d{1,2}")
PROMPT = "Read the number."  # idéntico a IdentitySettings.ocr_prompt


def read_number(model, processor, image, device):
    messages = [
        {"role": "user", "content": [
            {"type": "image", "image": image},
            {"type": "text", "text": PROMPT},
        ]},
    ]
    with warnings.catch_warnings():
        warnings.filterwarnings("ignore", message="Kwargs passed to")
        inputs = processor.apply_chat_template(
            messages, add_generation_prompt=True, tokenize=True,
            return_dict=True, return_tensors="pt",
        ).to(device)
    with torch.inference_mode():
        generated = model.generate(**inputs, max_new_tokens=8, do_sample=False)
    text = processor.batch_decode(
        generated[:, inputs["input_ids"].shape[1]:], skip_special_tokens=True,
    )[0]
    m = DIGITS.search(text)
    if not m:
        return None
    v = int(m.group())
    return v if 0 <= v <= 99 else None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="models/jersey-ocr")
    ap.add_argument("--data", default="data/jersey-numbers/test")
    ap.add_argument("--device", default="cuda:0")
    args = ap.parse_args()

    data = Path(args.data)
    samples = []
    with open(data / "annotations.jsonl") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            r = json.loads(line)
            suf = str(r.get("suffix", "")).strip()
            if r.get("prefix") == PROMPT and suf.isdigit():
                samples.append((r["image"], suf))
    print(f"[INFO] {len(samples)} muestras de test con dorsal numérico")

    processor = AutoProcessor.from_pretrained(args.model)
    model = AutoModelForImageTextToText.from_pretrained(
        args.model, torch_dtype=torch.bfloat16,
    ).to(args.device)
    model.eval()
    print("[INFO] modelo cargado")

    correct = 0
    nulls = 0
    errors = []
    latencies = []
    # warm-up
    _ = read_number(model, processor, Image.open(data / samples[0][0]).convert("RGB"), args.device)

    for img_name, gt in samples:
        image = Image.open(data / img_name).convert("RGB")
        t0 = time.perf_counter()
        pred = read_number(model, processor, image, args.device)
        latencies.append(time.perf_counter() - t0)
        pred_s = "" if pred is None else str(pred)
        if pred is None:
            nulls += 1
        if pred_s == gt:
            correct += 1
        elif len(errors) < 20:
            errors.append((img_name[:40], gt, pred_s))

    n = len(samples)
    lat = sorted(latencies)
    print("\n================ RESULTADOS OCR DORSAL ================")
    print(f"Muestras evaluadas : {n}")
    print(f"Aciertos (exact)   : {correct}")
    print(f"Exactitud          : {100*correct/n:.2f} %")
    print(f"Predicción vacía   : {nulls} ({100*nulls/n:.1f} %)")
    print(f"Latencia media     : {1000*sum(latencies)/n:.1f} ms/img")
    print(f"Latencia mediana   : {1000*lat[n//2]:.1f} ms/img")
    print(f"Throughput         : {n/sum(latencies):.1f} img/s")
    print("\nEjemplos de error (gt -> pred):")
    for name, gt, pred in errors[:15]:
        print(f"  {name:42s} {gt:>3s} -> {pred!r}")


if __name__ == "__main__":
    main()
