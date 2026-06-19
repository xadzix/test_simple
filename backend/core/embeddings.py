from django.conf import settings
from openai import OpenAI

MODEL = "text-embedding-3-small"
BATCH_SIZE = 100


def product_text(product):
    return f"{product.name} | ед.: {product.unit} | группа: {product.group}"


def position_text(name, unit):
    return f"{name} | ед.: {unit}"


def create_embeddings(texts):
    if not settings.OPENAI_API_KEY:
        raise RuntimeError("OPENAI_API_KEY не настроен")

    client = OpenAI(
        api_key=settings.OPENAI_API_KEY,
        timeout=30.0,
        max_retries=2,
    )
    vectors = []
    for start in range(0, len(texts), BATCH_SIZE):
        response = client.embeddings.create(
            model=MODEL,
            input=texts[start : start + BATCH_SIZE],
        )
        vectors.extend(
            item.embedding
            for item in sorted(response.data, key=lambda item: item.index)
        )
    return vectors
