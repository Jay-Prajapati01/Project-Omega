"""Tests for configuration."""
from app.core.config import Settings


def test_default_settings():
    s = Settings()
    assert s.app_name == "MindMesh"
    assert s.environment == "development"
    assert s.llm_model == "qwen2.5:3b"
    assert s.embedding_model == "nomic-embed-text"
    assert s.embedding_dim == 768


def test_cors_origin_list():
    s = Settings(cors_origins="http://localhost:3000,http://127.0.0.1:3000")
    origins = s.cors_origin_list
    assert "http://localhost:3000" in origins
    assert "http://127.0.0.1:3000" in origins


def test_embedding_dim_for_model():
    s = Settings(embedding_model="nomic-embed-text")
    assert s.embedding_dim_for_model == 768

    s2 = Settings(embedding_model="bge-m3")
    assert s2.embedding_dim_for_model == 1024

    s3 = Settings(embedding_model="all-minilm")
    assert s3.embedding_dim_for_model == 384


def test_unknown_model_uses_default():
    s = Settings(embedding_model="unknown-model", embedding_dim=512)
    assert s.embedding_dim_for_model == 512
