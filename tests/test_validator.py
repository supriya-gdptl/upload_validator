"""
Test suite for upload-validator backend.
Run: pytest tests/test_validator.py -v
"""

import io
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "backend"))

import pytest
from unittest.mock import patch, MagicMock
from fastapi.testclient import TestClient

# ── Minimal mocks so the module loads without GPU/Tesseract installed ─────────
# These patches are applied before the module is imported in test collection.
clip_mock = MagicMock()
clip_mock.load.return_value = (MagicMock(), MagicMock())

sbert_mock = MagicMock()
sbert_instance = MagicMock()
sbert_instance.encode.return_value = MagicMock()
sbert_mock.return_value = sbert_instance

with patch.dict("sys.modules", {"clip": clip_mock,
                                 "sentence_transformers": MagicMock(
                                     SentenceTransformer=sbert_mock,
                                     util=MagicMock(cos_sim=MagicMock(return_value=0.8))
                                 )}):
    from main import app, sbert_similarity, combine_scores

client = TestClient(app)


# ─────────────────────────────────────────────────────────────────────────────
# Unit tests — pure functions
# ─────────────────────────────────────────────────────────────────────────────

class TestCombineScores:
    def test_equal_weight(self):
        score = combine_scores(0.8, 0.6, clip_weight=0.5, text_weight=0.5)
        assert abs(score - 0.7) < 1e-6

    def test_all_clip(self):
        assert combine_scores(1.0, 0.0, 1.0, 0.0) == 1.0

    def test_all_text(self):
        assert combine_scores(0.0, 1.0, 0.0, 1.0) == 1.0

    def test_zero(self):
        assert combine_scores(0.0, 0.0) == 0.0

    def test_default_weights_sum_to_one(self):
        # Default 0.6 + 0.4
        s = combine_scores(1.0, 1.0)
        assert abs(s - 1.0) < 1e-6


class TestThresholdLogic:
    """Verify the decision thresholds are applied correctly by the /validate route."""

    def _make_png_bytes(self):
        """Create a minimal valid 1×1 white PNG."""
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (1, 1), color=(255, 255, 255)).save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    def _post(self, score_override: float):
        """
        Post a fake PNG and mock the entire analyse_image function
        so it returns a predetermined score.
        """
        png = self._make_png_bytes()
        with patch("main.analyse_image", return_value={
            "score": score_override,
            "ocr_text": "mock text",
            "clip_similarity": score_override,
            "text_similarity": score_override,
        }):
            resp = client.post(
                "/validate",
                data={"description": "a white test image"},
                files={"file": ("test.png", png, "image/png")},
            )
        return resp.json()

    def test_approved_at_75(self):
        result = self._post(75.0)
        assert result["decision"] == "approved"

    def test_approved_above_75(self):
        result = self._post(90.0)
        assert result["decision"] == "approved"

    def test_warning_at_50(self):
        result = self._post(50.0)
        assert result["decision"] == "warning"

    def test_warning_at_74(self):
        result = self._post(74.9)
        assert result["decision"] == "warning"

    def test_rejected_below_50(self):
        result = self._post(49.9)
        assert result["decision"] == "rejected"

    def test_rejected_at_zero(self):
        result = self._post(0.0)
        assert result["decision"] == "rejected"


# ─────────────────────────────────────────────────────────────────────────────
# Integration tests — HTTP layer
# ─────────────────────────────────────────────────────────────────────────────

class TestHealthEndpoint:
    def test_health_returns_ok(self):
        resp = client.get("/health")
        assert resp.status_code == 200
        assert resp.json()["status"] == "ok"


class TestValidateEndpoint:
    def _png(self):
        from PIL import Image
        buf = io.BytesIO()
        Image.new("RGB", (10, 10), color=(128, 128, 128)).save(buf, format="PNG")
        buf.seek(0)
        return buf.read()

    def test_missing_description_returns_400(self):
        png = self._png()
        resp = client.post(
            "/validate",
            data={"description": "   "},
            files={"file": ("img.png", png, "image/png")},
        )
        assert resp.status_code == 400

    def test_unsupported_file_type_returns_415(self):
        resp = client.post(
            "/validate",
            data={"description": "a zip file"},
            files={"file": ("archive.zip", b"PK\x03\x04", "application/zip")},
        )
        assert resp.status_code == 415

    def test_valid_png_returns_json_structure(self):
        png = self._png()
        with patch("main.analyse_image", return_value={
            "score": 80.0, "ocr_text": "", "clip_similarity": 80.0, "text_similarity": 80.0
        }):
            resp = client.post(
                "/validate",
                data={"description": "a grey square"},
                files={"file": ("grey.png", png, "image/png")},
            )
        assert resp.status_code == 200
        body = resp.json()
        for key in ("decision", "score", "message", "file_type"):
            assert key in body, f"Missing key: {key}"

    def test_jpeg_extension_routed_as_image(self):
        png = self._png()
        with patch("main.analyse_image", return_value={
            "score": 60.0, "ocr_text": "", "clip_similarity": 60.0, "text_similarity": 60.0
        }):
            resp = client.post(
                "/validate",
                data={"description": "some image"},
                files={"file": ("photo.jpg", png, "image/jpeg")},
            )
        assert resp.json()["file_type"] == "image"

    def test_pdf_routed_correctly(self):
        import fitz
        doc = fitz.open()
        doc.new_page()
        pdf_bytes = doc.tobytes()

        with patch("main.analyse_pdf", return_value={
            "score": 55.0, "ocr_text": "hello world", "clip_similarity": 55.0, "text_similarity": 55.0
        }):
            resp = client.post(
                "/validate",
                data={"description": "a blank pdf"},
                files={"file": ("doc.pdf", pdf_bytes, "application/pdf")},
            )
        assert resp.json()["file_type"] == "pdf"

    def test_mp4_routed_correctly(self):
        fake_mp4 = b"\x00" * 64  # won't be decoded — analyser is mocked
        with patch("main.analyse_video", return_value={
            "score": 30.0, "ocr_text": "", "clip_similarity": 30.0,
            "text_similarity": 30.0, "frames_analysed": 0
        }):
            resp = client.post(
                "/validate",
                data={"description": "a video about cats"},
                files={"file": ("clip.mp4", fake_mp4, "video/mp4")},
            )
        data = resp.json()
        assert data["file_type"] == "video"
        assert data["decision"] == "rejected"


# ─────────────────────────────────────────────────────────────────────────────
# Score accuracy smoke tests (mocked similarity functions)
# ─────────────────────────────────────────────────────────────────────────────

class TestScoreAccuracy:
    """
    These tests verify the scoring pipeline returns sensible values
    without requiring real models or GPU.
    """

    def test_high_similarity_gives_high_score(self):
        with patch("main.clip_image_text_similarity", return_value=0.9), \
             patch("main.sbert_similarity", return_value=0.9):
            from main import analyse_image
            from PIL import Image
            img_bytes = io.BytesIO()
            Image.new("RGB", (5, 5)).save(img_bytes, "PNG")
            result = analyse_image(img_bytes.getvalue(), "a test image")
            assert result["score"] >= 75

    def test_low_similarity_gives_low_score(self):
        with patch("main.clip_image_text_similarity", return_value=0.1), \
             patch("main.sbert_similarity", return_value=0.1):
            from main import analyse_image
            from PIL import Image
            img_bytes = io.BytesIO()
            Image.new("RGB", (5, 5)).save(img_bytes, "PNG")
            result = analyse_image(img_bytes.getvalue(), "completely unrelated text")
            assert result["score"] < 50
