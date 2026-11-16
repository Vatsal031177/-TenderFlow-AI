import hashlib
import json
import re
from typing import List, Dict, Any
import numpy as np
from openai import OpenAI
from app.config import settings
from app.ai.observability import trace_step


class ModelGateway:
    """Unified LLM & Embedding Gateway with deterministic offline fallback."""

    def __init__(self):
        self.client = OpenAI(api_key=settings.openai_api_key) if settings.openai_api_key else None

    @trace_step(name="gateway_embed_text", run_type="embedding")
    def embed(self, text: str) -> List[float]:
        if self.client:
            resp = self.client.embeddings.create(
                model="text-embedding-3-small",
                input=text,
            )
            return resp.data[0].embedding

        # Deterministic 1536-dim semantic-hash fallback for local offline execution
        vec = np.zeros(1536, dtype=np.float32)
        tokens = re.findall(r"[a-zA-Z0-9äöüßÄÖÜ]+", text.lower())
        for tok in tokens:
            h = int(hashlib.sha256(tok.encode("utf-8")).hexdigest(), 16)
            idx = h % 1536
            vec[idx] += 1.0
        norm = np.linalg.norm(vec)
        return (vec / norm).tolist() if norm > 0 else vec.tolist()

    @trace_step(name="gateway_extract_boq", run_type="llm")
    def extract_boq_positions(self, raw_text: str) -> List[Dict[str, Any]]:
        if self.client:
            prompt = (
                "Extract construction Bill of Quantities (BoQ / Leistungsverzeichnis) line items "
                "from the text. Return ONLY a JSON object with key 'items' containing objects with: "
                "position_no (string), description (string), quantity (number), unit (string)."
            )
            resp = self.client.chat.completions.create(
                model=settings.openai_model,
                temperature=0.0,
                response_format={"type": "json_object"},
                messages=[
                    {"role": "system", "content": prompt},
                    {"role": "user", "content": raw_text},
                ],
            )
            data = json.loads(resp.choices[0].message.content)
            return data.get("items", [])

        # Offline parser fallback for structured/semi-structured LV lines
        items = []
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]
        pattern = re.compile(
            r"^(?:Pos\.?\s*)?(\d+(?:\.\d+)?)\s*[:\-]?\s*(.+?)\s+(\d+(?:[.,]\d+)?)\s*(m2|m²|m3|m³|m|pcs|stk|Stück|kg|cartridge|Kartusche)\b",
            re.IGNORECASE,
        )
        for idx, line in enumerate(lines, start=1):
            m = pattern.search(line)
            if m:
                qty = float(m.group(3).replace(",", "."))
                items.append({
                    "position_no": m.group(1),
                    "description": m.group(2).strip(" -,"),
                    "quantity": qty,
                    "unit": m.group(4),
                })
            elif len(line) > 10:
                items.append({
                    "position_no": f"0.{idx}",
                    "description": line,
                    "quantity": 1.0,
                    "unit": "pcs",
                })
        return items


gateway = ModelGateway()
