"""Fine-tune de un VLM SmolVLM2 para leer el dorsal (réplica local del OCR del
cuaderno `basketball-jersey-numbers-ocr`).

Entrena sobre el dataset descargado con `download_jersey_dataset.py` (export
`jsonl`, tipo *text-image-pairs*): cada split tiene `annotations.jsonl` con
líneas `{"image": ..., "prefix": "Read the number.", "suffix": "40"}`. Guarda el
modelo + processor en `models/jersey-ocr/`, que es lo que carga
`pipeline/identity/number_ocr.py` en runtime (sin API de Roboflow).

LoRA sobre SmolVLM2-500M por defecto (entrena en una sola GPU). Ajusta el modelo
base con `--base-model`.

Uso:
    python scripts/train_jersey_ocr.py --data data/jersey-numbers --epochs 5
"""

from __future__ import annotations

import argparse
import json
import random
from pathlib import Path
from typing import List, Tuple

import torch
from PIL import Image
from torch.utils.data import DataLoader, Dataset

IGNORE_INDEX = -100


def _scan_jsonl(root: Path, split: str = "train") -> List[Tuple[Path, str, str]]:
    """Lee `<split>/annotations.jsonl`. Devuelve [(img_path, prefix, suffix)]."""
    split_dir = root / split
    ann = split_dir / "annotations.jsonl"
    if not ann.is_file():
        return []
    samples: List[Tuple[Path, str, str]] = []
    with ann.open() as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            rec = json.loads(line)
            img = split_dir / rec["image"]
            if img.is_file():
                samples.append((img, rec.get("prefix", "Read the number."), str(rec["suffix"])))
    return samples


class JerseyDataset(Dataset):
    def __init__(self, samples: List[Tuple[Path, str, str]], processor) -> None:
        self.samples = samples
        self.processor = processor

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, idx: int):
        img_path, prefix, label = self.samples[idx]
        image = Image.open(img_path).convert("RGB")
        messages = [
            {"role": "user", "content": [
                {"type": "image"},
                {"type": "text", "text": prefix},
            ]},
            {"role": "assistant", "content": [{"type": "text", "text": label}]},
        ]
        text = self.processor.apply_chat_template(messages, add_generation_prompt=False)
        enc = self.processor(text=text, images=[image], return_tensors="pt")
        enc = {k: v.squeeze(0) for k, v in enc.items()}
        # Labels = input_ids con padding/imagen ignorados.
        labels = enc["input_ids"].clone()
        labels[labels == self.processor.tokenizer.pad_token_id] = IGNORE_INDEX
        image_token_id = getattr(self.processor.tokenizer, "image_token_id", None)
        if image_token_id is not None:
            labels[labels == image_token_id] = IGNORE_INDEX
        enc["labels"] = labels
        return enc


def collate(batch, pad_token_id: int):
    keys = batch[0].keys()
    out = {}
    maxlen = max(b["input_ids"].shape[0] for b in batch)
    for k in keys:
        if k in ("input_ids", "attention_mask", "labels"):
            pad_val = {"input_ids": pad_token_id, "attention_mask": 0, "labels": IGNORE_INDEX}[k]
            padded = []
            for b in batch:
                t = b[k]
                if t.shape[0] < maxlen:
                    pad = torch.full((maxlen - t.shape[0],), pad_val, dtype=t.dtype)
                    t = torch.cat([t, pad], dim=0)
                padded.append(t)
            out[k] = torch.stack(padded)
        else:  # pixel_values y derivados
            out[k] = torch.stack([b[k] for b in batch])
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/jersey-numbers")
    ap.add_argument("--base-model", default="HuggingFaceTB/SmolVLM2-500M-Video-Instruct")
    ap.add_argument("--out", default="models/jersey-ocr")
    ap.add_argument("--epochs", type=int, default=5)
    ap.add_argument("--batch-size", type=int, default=4)
    ap.add_argument("--lr", type=float, default=1e-4)
    ap.add_argument("--device", default="cuda")
    ap.add_argument("--no-lora", action="store_true", help="fine-tune completo en vez de LoRA")
    ap.add_argument("--limit", type=int, default=0, help="usa solo N muestras (smoke test)")
    args = ap.parse_args()

    here = Path(__file__).resolve().parent.parent
    try:
        from dotenv import load_dotenv

        load_dotenv(here / ".env")  # HF_TOKEN para descargar el modelo base
    except ImportError:
        pass
    data_root = (here / args.data) if not Path(args.data).is_absolute() else Path(args.data)
    samples = _scan_jsonl(data_root, "train")
    if not samples:
        raise SystemExit(
            f"No se encontraron pares imagen-texto en {data_root}/train/annotations.jsonl. "
            "Descarga el dataset con scripts/download_jersey_dataset.py (export 'jsonl')."
        )
    random.shuffle(samples)
    if args.limit:
        samples = samples[: args.limit]
    print(f"[INFO] {len(samples)} pares imagen-texto de dorsal")

    from transformers import AutoModelForImageTextToText, AutoProcessor

    # do_image_splitting=False: los recortes de dorsal son pequeños; trocearlos
    # en tiles dispara los tokens de visión y la memoria (causa del OOM). El
    # processor se guarda con esta opción, así que la inferencia la hereda.
    processor = AutoProcessor.from_pretrained(args.base_model, do_image_splitting=False)
    model = AutoModelForImageTextToText.from_pretrained(
        args.base_model, torch_dtype=torch.bfloat16,
    )
    model.gradient_checkpointing_enable()
    if hasattr(model, "enable_input_require_grads"):
        model.enable_input_require_grads()  # necesario con checkpointing + LoRA

    if not args.no_lora:
        from peft import LoraConfig, get_peft_model

        lora = LoraConfig(
            r=16, lora_alpha=32, lora_dropout=0.05,
            target_modules=["q_proj", "v_proj", "k_proj", "o_proj"],
            task_type="CAUSAL_LM",
        )
        model = get_peft_model(model, lora)
        model.print_trainable_parameters()

    model.to(args.device)
    model.train()

    ds = JerseyDataset(samples, processor)
    pad_id = processor.tokenizer.pad_token_id
    loader = DataLoader(
        ds, batch_size=args.batch_size, shuffle=True,
        collate_fn=lambda b: collate(b, pad_id),
    )
    optim = torch.optim.AdamW(
        [p for p in model.parameters() if p.requires_grad], lr=args.lr,
    )

    for epoch in range(args.epochs):
        total = 0.0
        for step, batch in enumerate(loader):
            batch = {k: v.to(args.device) for k, v in batch.items()}
            out = model(**batch)
            loss = out.loss
            loss.backward()
            optim.step()
            optim.zero_grad()
            total += float(loss.item())
            if step % 20 == 0:
                print(f"  epoch {epoch} step {step} loss {loss.item():.4f}", flush=True)
        print(f"[EPOCH {epoch}] loss medio {total / max(1, len(loader)):.4f}", flush=True)

    out_dir = (here / args.out) if not Path(args.out).is_absolute() else Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    if not args.no_lora:
        model = model.merge_and_unload()  # fusiona LoRA para inferencia simple
    model.save_pretrained(str(out_dir))
    processor.save_pretrained(str(out_dir))
    print(f"[OK] Modelo guardado en {out_dir}")


if __name__ == "__main__":
    main()
