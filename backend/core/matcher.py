import re
from dataclasses import dataclass

from pgvector.django import CosineDistance

from .embeddings import create_embeddings, position_text, product_text
from .models import CatalogProduct

MIN_SIMILARITY = 0.78
MIN_MARGIN = 0.05


def normalize(value):
    value = (value or "").lower().replace("ё", "е")
    value = re.sub(r"[^a-zа-я0-9]+", " ", value)
    return " ".join(value.split())


@dataclass
class MatchResult:
    product: object | None
    confidence: float
    explanation: str


class ProductMatcher:
    def __init__(self, products):
        self.products = list(products)
        self.by_sku = {
            normalize(product.sku): product
            for product in self.products
            if product.sku
        }

    def _ensure_catalog_embeddings(self):
        missing = [
            product for product in self.products if product.embedding is None
        ]
        if not missing:
            return
        vectors = create_embeddings(
            [product_text(product) for product in missing]
        )
        for product, vector in zip(missing, vectors, strict=True):
            product.embedding = vector
        CatalogProduct.objects.bulk_update(missing, ["embedding"])

    def match_many(self, positions):
        results = [None] * len(positions)
        pending = []

        for index, (sku, name, unit) in enumerate(positions):
            normalized_sku = normalize(sku)
            if normalized_sku in self.by_sku:
                results[index] = MatchResult(
                    self.by_sku[normalized_sku],
                    100.0,
                    "Точное совпадение артикула",
                )
            elif normalized_sku:
                results[index] = MatchResult(
                    None, 0.0, "Артикул не найден в каталоге"
                )
            elif not normalize(name) or not self.products:
                results[index] = MatchResult(
                    None, 0.0, "Недостаточно данных для сопоставления"
                )
            else:
                pending.append((index, name, unit))

        if not pending:
            return results

        try:
            self._ensure_catalog_embeddings()
            vectors = create_embeddings(
                [position_text(name, unit) for _, name, unit in pending]
            )
        except Exception:
            for index, _, _ in pending:
                results[index] = MatchResult(
                    None, 0.0, "ИИ-сопоставление временно недоступно"
                )
            return results

        queryset = CatalogProduct.objects.filter(
            pk__in=[product.pk for product in self.products],
            embedding__isnull=False,
        )
        for (index, _, unit), vector in zip(pending, vectors, strict=True):
            candidates = list(
                queryset.annotate(
                    distance=CosineDistance("embedding", vector)
                ).order_by("distance")[:10]
            )
            scores = [
                (1 - float(candidate.distance), candidate)
                for candidate in candidates
                if not unit
                or not candidate.unit
                or normalize(unit) == normalize(candidate.unit)
            ]
            if not scores:
                results[index] = MatchResult(
                    None, 0.0, "Подходящий товар не найден"
                )
                continue

            best_score, product = scores[0]
            confidence = round(max(0.0, min(1.0, best_score)) * 100, 2)
            if best_score < MIN_SIMILARITY:
                results[index] = MatchResult(
                    None, confidence, "Сходство ниже безопасного порога"
                )
            elif len(scores) > 1 and best_score - scores[1][0] < MIN_MARGIN:
                results[index] = MatchResult(
                    None, confidence, "Найдено несколько похожих товаров"
                )
            else:
                results[index] = MatchResult(
                    product, confidence, "Семантическое сходство OpenAI"
                )

        return results

    def match(self, sku, name, unit=""):
        return self.match_many([(sku, name, unit)])[0]
