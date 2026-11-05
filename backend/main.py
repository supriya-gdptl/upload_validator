"""
Upload Validator Backend
Uses local CV/NLP libraries only — no external AI APIs.
  - Images/PDFs  : Tesseract OCR  + CLIP visual embeddings
  - Videos (.mp4): OpenCV keyframe extraction + CLIP visual embeddings
  - Text matching: sentence-transformers (all-MiniLM-L6-v2)
"""

import io
import os
import cv2
import fitz          # PyMuPDF
import numpy as np
import pytesseract
import tempfile

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from PIL import Image
from sentence_transformers import SentenceTransformer, util
import torch


# ── Sentence-BERT ─────────────────────────────────────────────────────────────
qwen_model = SentenceTransformer("Qwen/Qwen3-VL-Embedding-2B")

app = FastAPI(title="Upload Validator", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://127.0.0.1:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def ocr_image(pil_img: Image.Image) -> str:
    """Run Tesseract OCR on a PIL image and return extracted text."""
    txt = pytesseract.image_to_string(pil_img).strip()
    return txt

CLIP_LO, CLIP_HI = 0.01, 0.50   # placeholders: set from your own measurements

def normalise_clip(raw: float) -> float:
    return min(1.0, max(0.0, (raw - CLIP_LO) / (CLIP_HI - CLIP_LO)))

def count_confident_words(pil_img, min_conf=60):
    d = pytesseract.image_to_data(pil_img, output_type=pytesseract.Output.DICT)
    return sum(1 for w, c in zip(d["text"], d["conf"])
               if w.strip() and float(c) > min_conf)

DOC_PROTOS   = ["an invoice", "a receipt", "a scanned document",
                "a screenshot of text", "a form", "a purchase order", "a contract"]
PHOTO_PROTOS = ["a photograph of a scene", "a picture of an object",
                "a photo of people or animals"]

def claims_document(description):
    d  = qwen_model.encode(description)
    dp = max(util.cos_sim(d, qwen_model.encode(p)) for p in DOC_PROTOS)
    pp = max(util.cos_sim(d, qwen_model.encode(p)) for p in PHOTO_PROTOS)
    return dp > pp

def image_text_similarity(pil_images: list, text: str) -> float:
    """
    Compute cosine similarity between a list of PIL images and a text string
    using Qwen3-VL-Embedding-2B embeddings. Returns the max similarity across all images (0-1).
    """

    with torch.no_grad():
        text_feat = qwen_model.encode(text, convert_to_tensor=True)
        text_feat = text_feat / text_feat.norm(dim=-1, keepdim=True)

        sims = []
        for img in pil_images:
            img_feat = qwen_model.encode(img, convert_to_tensor=True)
            img_feat = img_feat / img_feat.norm(dim=-1, keepdim=True)
            sims.append((img_feat @ text_feat).item())

    # CLIP cosine similarities are typically in [-1, 1]; normalise to [0, 1]
    raw = max(sims)
    print(raw)
    return normalise_clip(raw)


def text_text_similarity(text_a: str, text_b: str) -> float:
    """Semantic similarity between two strings using Sentence-BERT (0-1)."""
    if not text_a or not text_b:
        return 0.0
    emb_a = qwen_model.encode(text_a, convert_to_tensor=True)
    emb_b = qwen_model.encode(text_b, convert_to_tensor=True)
    return float(util.cos_sim(emb_a, emb_b))


def combine_scores(clip_sim: float, text_sim: float,
                   clip_weight: float = 0.6, text_weight: float = 0.4) -> float:
    """Weighted combination of CLIP visual score and SBERT text score."""
    return clip_weight * clip_sim + text_weight * text_sim


# ─────────────────────────────────────────────────────────────────────────────
# File analysers
# ─────────────────────────────────────────────────────────────────────────────

def analyse_image(data: bytes, description: str) -> dict:
    pil_img = Image.open(io.BytesIO(data)).convert("RGB")

    ocr_text  = ocr_image(pil_img)
    clip_sim  = image_text_similarity([pil_img], description)
    text_sim  = text_text_similarity(ocr_text, description) if ocr_text else 0.0

    # score = combine_scores(clip_sim, text_sim, clip_weight=1.0, text_weight=0.0)
    # score = max(clip_sim, text_sim)
    is_document = count_confident_words(pil_img) >= 25

    if is_document:
        content_score = text_text_similarity(ocr_text, description)
        if not claims_document(description):
            score = min(content_score, 0.35)  # content matches, type is wrong → reject
        else:
            score = content_score
    else:
        score = clip_sim

    return {
        "score": round(score * 100, 1),
        "ocr_text": ocr_text if ocr_text else "",
        "clip_similarity": round(clip_sim * 100, 1),
        "text_similarity": round(text_sim * 100, 1),
    }


def analyse_pdf(data: bytes, description: str) -> dict:
    doc = fitz.open(stream=data, filetype="pdf")
    page_texts, page_images = [], []

    for page_num in range(min(len(doc), 5)):  # analyse first 5 pages
        page = doc[page_num]
        page_texts.append(page.get_text())

        # Render page as image for CLIP
        mat  = fitz.Matrix(1.5, 1.5)
        pix  = page.get_pixmap(matrix=mat)
        img  = Image.frombytes("RGB", [pix.width, pix.height], pix.samples)
        page_images.append(img)

        # Also OCR if direct text extraction is sparse
        if len(page_texts[-1].strip()) < 50:
            page_texts[-1] += " " + ocr_image(img)

    full_text = " ".join(page_texts).strip()
    clip_sim  = image_text_similarity(page_images, description)
    text_sim  = text_text_similarity(full_text, description) if full_text else 0.0

    # score = combine_scores(clip_sim, text_sim)
    score = max(clip_sim, text_sim)
    print(full_text)

    return {
        "score": round(score * 100, 1),
        "ocr_text": full_text,
        "clip_similarity": round(clip_sim * 100, 1),
        "text_similarity": round(text_sim * 100, 1),
    }


def analyse_video(data: bytes, description: str, max_frames: int = 8) -> dict:
    # Write to temp file (OpenCV needs a file path)
    with tempfile.NamedTemporaryFile(suffix=".mp4", delete=False) as tmp:
        tmp.write(data)
        tmp_path = tmp.name

    try:
        cap = cv2.VideoCapture(tmp_path)
        total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
        fps   = cap.get(cv2.CAP_PROP_FPS) or 24

        if total <= 0:
            return {"score": 0.0, "ocr_text": "", "clip_similarity": 0.0, "text_similarity": 0.0}

        # Sample evenly-spaced keyframes
        indices = np.linspace(0, total - 1, min(max_frames, total), dtype=int)
        frames, ocr_chunks = [], []

        for idx in indices:
            cap.set(cv2.CAP_PROP_POS_FRAMES, int(idx))
            ok, frame = cap.read()
            if not ok:
                continue
            rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            pil = Image.fromarray(rgb)
            frames.append(pil)
            ocr_chunks.append(ocr_image(pil))

        cap.release()

        full_ocr  = " ".join(c for c in ocr_chunks if c).strip()
        clip_sim  = image_text_similarity(frames, description)
        text_sim  = text_text_similarity(full_ocr, description) if full_ocr else 0.0

        score = combine_scores(clip_sim, text_sim)

        return {
            "score": round(score * 100, 1),
            "ocr_text": full_ocr[:500],
            "clip_similarity": round(clip_sim * 100, 1),
            "text_similarity": round(text_sim * 100, 1),
            "frames_analysed": len(frames),
        }
    finally:
        os.unlink(tmp_path)


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/health")
def health():
    return {"status": "ok"}


@app.post("/validate")
async def validate_upload(
    file: UploadFile = File(...),
    description: str = Form(...),
):
    if not description.strip():
        raise HTTPException(status_code=400, detail="Description cannot be empty.")

    data     = await file.read()
    filename = (file.filename or "").lower()

    # ── Route to correct analyser ──────────────────────────────────────────
    if filename.endswith((".jpg", ".jpeg", ".png", ".gif", ".webp", ".bmp")):
        result = analyse_image(data, description)
        file_type = "image"

    elif filename.endswith(".pdf"):
        result = analyse_pdf(data, description)
        file_type = "pdf"

    elif filename.endswith((".mp4", ".mov", ".avi", ".mkv", ".webm")):
        result = analyse_video(data, description)
        file_type = "video"

    else:
        raise HTTPException(
            status_code=415,
            detail=f"Unsupported file type: {filename}. Accepted: jpg/png, pdf, mp4."
        )

    score = result["score"]

    # ── Decision logic ─────────────────────────────────────────────────────
    if score >= 75:
        decision = "approved"
        message  = "Great match! Your file has been approved for upload."
    elif score >= 50:
        decision = "warning"
        message  = (
            "Your description partially matches the file. "
            "Consider improving your description, or click Submit if you're happy with it."
        )
    else:
        decision = "rejected"
        message  = (
            f"Your description matches only {score}% of the file content. "
            "Please rewrite your description to better reflect what you're uploading."
        )

    return JSONResponse({
        "decision":        decision,
        "score":           score,
        "message":         message,
        "file_type":       file_type,
        "ocr_preview":     result.get("ocr_text", ""),
        "clip_similarity": result.get("clip_similarity", 0),
        "text_similarity": result.get("text_similarity", 0),
        "frames_analysed": result.get("frames_analysed"),
    })
