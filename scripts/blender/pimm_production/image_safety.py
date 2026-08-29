"""Pure pixel-level alpha safety analysis for PIMM proof and final gates."""

from __future__ import annotations

from dataclasses import asdict, dataclass
import math
from typing import Mapping


_EDGES = ("left", "top", "right", "bottom")
_EVIDENCE_FIELDS = {
    "canvas_size", "product_bounds", "shadow_bounds", "product_edge_fractions",
    "shadow_edge_fractions", "product_alpha_extrema", "shadow_alpha_extrema",
    "catcher_visible", "reasons", "passed",
}


@dataclass(frozen=True)
class AlphaSafetyEvidence:
    """Independent product and shadow alpha measurements for one rendered image."""

    canvas_size: tuple[int, int]
    product_bounds: tuple[int, int, int, int] | None
    shadow_bounds: tuple[int, int, int, int] | None
    product_edge_fractions: Mapping[str, float]
    shadow_edge_fractions: Mapping[str, float]
    product_alpha_extrema: tuple[int, int]
    shadow_alpha_extrema: tuple[int, int]
    catcher_visible: bool
    reasons: tuple[str, ...]

    @property
    def passed(self) -> bool:
        """Whether every measured safety invariant passed."""

        return not self.reasons

    def to_mapping(self) -> dict[str, object]:
        """Return deterministic JSON-safe evidence for an immutable proof manifest."""

        payload = asdict(self)
        for field in ("canvas_size", "product_bounds", "shadow_bounds", "product_alpha_extrema", "shadow_alpha_extrema", "reasons"):
            if payload[field] is not None:
                payload[field] = list(payload[field])
        payload["product_edge_fractions"] = dict(self.product_edge_fractions)
        payload["shadow_edge_fractions"] = dict(self.shadow_edge_fractions)
        payload["passed"] = self.passed
        return payload


def _rgba_pixels(image: object, label: str) -> tuple[int, int, list[tuple[int, int, int, int]]]:
    """Read one Pillow-compatible image as RGBA without depending on Blender."""

    if not hasattr(image, "convert") or not hasattr(image, "size"):
        raise ValueError(f"{label} must be a Pillow-compatible image")
    converted = image.convert("RGBA")
    size = converted.size
    if (
        not isinstance(size, tuple)
        or len(size) != 2
        or not all(isinstance(value, int) and value > 0 for value in size)
    ):
        raise ValueError(f"{label} dimensions must be positive integers")
    return size[0], size[1], list(converted.get_flattened_data())


def _bounds(alpha: list[int], width: int, height: int) -> tuple[int, int, int, int] | None:
    positions = [index for index, value in enumerate(alpha) if value > 0]
    if not positions:
        return None
    xs = [index % width for index in positions]
    ys = [index // width for index in positions]
    return min(xs), min(ys), max(xs), max(ys)


def _edge_fractions(alpha: list[int], width: int, height: int) -> dict[str, float]:
    """Return the fraction of each frame edge carrying non-transparent alpha."""

    return {
        "left": sum(alpha[row * width] > 0 for row in range(height)) / height,
        "top": sum(alpha[column] > 0 for column in range(width)) / width,
        "right": sum(alpha[row * width + width - 1] > 0 for row in range(height)) / height,
        "bottom": sum(alpha[(height - 1) * width + column] > 0 for column in range(width)) / width,
    }


def _clearance(bounds: tuple[int, int, int, int], width: int, height: int) -> dict[str, float]:
    return {
        "left": bounds[0] / width,
        "top": bounds[1] / height,
        "right": (width - 1 - bounds[2]) / width,
        "bottom": (height - 1 - bounds[3]) / height,
    }


def _margin(value: object, label: str) -> float:
    if not isinstance(value, (int, float)) or isinstance(value, bool) or not math.isfinite(value):
        raise ValueError(f"{label} margin must be a finite number")
    if not 0 <= float(value) < 0.5:
        raise ValueError(f"{label} margin must be between 0 and 0.5")
    return float(value)


def analyze_alpha_safety(
    product_rgba: object,
    shadow_rgba: object,
    product_margin: object,
    shadow_margin: object,
) -> AlphaSafetyEvidence:
    """Measure independent product/shadow passes and return every alpha safety failure.

    The caller supplies the product-only and shadow-only RGBA passes.  This keeps
    object extents, shadow extents, and transparent-background leakage measurable
    rather than inferred from a composited presentation image.
    """

    product_margin_value = _margin(product_margin, "product")
    shadow_margin_value = _margin(shadow_margin, "shadow")
    width, height, product_pixels = _rgba_pixels(product_rgba, "product_rgba")
    shadow_width, shadow_height, shadow_pixels = _rgba_pixels(shadow_rgba, "shadow_rgba")
    if (width, height) != (shadow_width, shadow_height):
        raise ValueError("product_rgba and shadow_rgba dimensions must match")

    product_alpha = [pixel[3] for pixel in product_pixels]
    shadow_alpha = [pixel[3] for pixel in shadow_pixels]
    product_bounds = _bounds(product_alpha, width, height)
    shadow_bounds = _bounds(shadow_alpha, width, height)
    product_edges = _edge_fractions(product_alpha, width, height)
    shadow_edges = _edge_fractions(shadow_alpha, width, height)
    catcher_visible = any(
        alpha == 0 and any(channel != 0 for channel in pixel[:3])
        for pixel, alpha in zip(product_pixels, product_alpha)
    )

    reasons: list[str] = []
    for label, bounds, edge_fractions, margin in (
        ("product", product_bounds, product_edges, product_margin_value),
        ("shadow", shadow_bounds, shadow_edges, shadow_margin_value),
    ):
        if bounds is None:
            reasons.append(f"{label} pixels are missing")
            continue
        for edge in _EDGES:
            if edge_fractions[edge] > 0:
                reasons.append(f"{label} alpha touches {edge} frame edge")
        if margin > 0:
            for edge, fraction in _clearance(bounds, width, height).items():
                if fraction < margin:
                    reasons.append(
                        f"{label} clearance at {edge} is below {margin:.2%}"
                    )
    if catcher_visible:
        reasons.append("visible catcher RGB exists outside product alpha")
    product_extrema = min(product_alpha), max(product_alpha)
    shadow_extrema = min(shadow_alpha), max(shadow_alpha)
    if product_extrema == (255, 255):
        reasons.append("product alpha is fully opaque")

    return AlphaSafetyEvidence(
        canvas_size=(width, height),
        product_bounds=product_bounds,
        shadow_bounds=shadow_bounds,
        product_edge_fractions=product_edges,
        shadow_edge_fractions=shadow_edges,
        product_alpha_extrema=product_extrema,
        shadow_alpha_extrema=shadow_extrema,
        catcher_visible=catcher_visible,
        reasons=tuple(reasons),
    )


def validate_alpha_safety_evidence(value: object) -> list[str]:
    """Validate serialized measured evidence without accepting self-declared pass state."""

    errors: list[str] = []
    if not isinstance(value, Mapping) or set(value) != _EVIDENCE_FIELDS:
        return ["alpha safety evidence must contain exactly the measured result fields"]
    canvas = value.get("canvas_size")
    if not isinstance(canvas, (list, tuple)) or len(canvas) != 2 or not all(
        isinstance(item, int) and not isinstance(item, bool) and item > 0 for item in canvas
    ):
        return ["alpha safety canvas_size must contain two positive integers"]
    width, height = canvas
    for label in ("product", "shadow"):
        bounds = value.get(f"{label}_bounds")
        if bounds is not None:
            if not isinstance(bounds, (list, tuple)) or len(bounds) != 4 or not all(
                isinstance(item, int) and not isinstance(item, bool) for item in bounds
            ):
                errors.append(f"alpha safety {label}_bounds must be null or four integers")
            elif not (0 <= bounds[0] <= bounds[2] < width and 0 <= bounds[1] <= bounds[3] < height):
                errors.append(f"alpha safety {label}_bounds must be inside canvas_size")
        fractions = value.get(f"{label}_edge_fractions")
        if not isinstance(fractions, Mapping) or set(fractions) != set(_EDGES):
            errors.append(f"alpha safety {label}_edge_fractions must contain every edge")
        elif not all(
            isinstance(item, (int, float)) and not isinstance(item, bool) and math.isfinite(float(item)) and 0 <= float(item) <= 1
            for item in fractions.values()
        ):
            errors.append(f"alpha safety {label}_edge_fractions must be fractions")
        elif bounds is not None:
            edge_bounds = {"left": bounds[0] == 0, "top": bounds[1] == 0, "right": bounds[2] == width - 1, "bottom": bounds[3] == height - 1}
            for edge, touches in edge_bounds.items():
                if touches and fractions[edge] == 0:
                    errors.append(f"alpha safety {label}_bounds contradicts {label} edge fractions")
    for label in ("product", "shadow"):
        extrema = value.get(f"{label}_alpha_extrema")
        if not isinstance(extrema, (list, tuple)) or len(extrema) != 2 or not all(
            isinstance(item, int) and not isinstance(item, bool) and 0 <= item <= 255 for item in extrema
        ) or extrema[0] > extrema[1]:
            errors.append(f"alpha safety {label}_alpha_extrema must be ordered bytes")
    reasons = value.get("reasons")
    if not isinstance(reasons, (list, tuple)) or not all(isinstance(item, str) and item for item in reasons):
        errors.append("alpha safety reasons must be a list of nonempty strings")
    elif value.get("passed") is not (not reasons):
        errors.append("alpha safety passed must equal the absence of reasons")
    if not isinstance(value.get("catcher_visible"), bool):
        errors.append("alpha safety catcher_visible must be boolean")
    return errors
