import copy
import re
from typing import Any, Dict, List, Optional


DEFAULT_SELECTED_PACK_IDS = ["core"]
CUSTOM_RELATIONSHIP_KEY_PATTERN = re.compile(r"^[a-z][a-z0-9_]{1,63}$")


RELATIONSHIP_PACKS: List[Dict[str, Any]] = [
    {
        "id": "core",
        "label": "Core",
        "description": "Default relationship classes used across architecture decisions.",
        "relationship_types": [
            "supersedes",
            "amends",
            "depends_on",
            "related_to",
            "conflicts_with",
        ],
        "default_selected": True,
    },
    {
        "id": "software",
        "label": "Software Delivery",
        "description": "Useful for engineering, platform, and software delivery decisions.",
        "relationship_types": [
            "implements",
            "blocks",
            "duplicates",
            "derived_from",
        ],
    },
    {
        "id": "data",
        "label": "Data & Analytics",
        "description": "Useful for data governance, analytics, and reporting decisions.",
        "relationship_types": [
            "feeds",
            "derived_from",
            "depends_on",
            "governs",
        ],
    },
    {
        "id": "security",
        "label": "Security & Risk",
        "description": "Useful for security architecture, compliance, and risk treatment decisions.",
        "relationship_types": [
            "mitigates",
            "accepts_risk_from",
            "governs",
            "conflicts_with",
        ],
    },
    {
        "id": "operations",
        "label": "Operations & Service",
        "description": "Useful for service management, reliability, and operational change records.",
        "relationship_types": [
            "blocks",
            "informs",
            "depends_on",
            "governs",
        ],
    },
]


BUILTIN_RELATIONSHIP_TYPES: Dict[str, Dict[str, Any]] = {
    "supersedes": {
        "key": "supersedes",
        "label": "Supersedes",
        "inverse_label": "Superseded by",
        "description": "Replaces an older decision and moves that older decision into superseded status.",
        "builtin": True,
        "directional": True,
        "has_status_effect": True,
    },
    "amends": {
        "key": "amends",
        "label": "Amends",
        "inverse_label": "Amended by",
        "description": "Adjusts or clarifies another decision without fully replacing it.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "depends_on": {
        "key": "depends_on",
        "label": "Depends on",
        "inverse_label": "Depended on by",
        "description": "Relies on another decision being in place.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "related_to": {
        "key": "related_to",
        "label": "Related to",
        "inverse_label": "Related to",
        "description": "Connected in context or scope, without a stronger dependency.",
        "builtin": True,
        "directional": False,
        "has_status_effect": False,
    },
    "conflicts_with": {
        "key": "conflicts_with",
        "label": "Conflicts with",
        "inverse_label": "Conflicts with",
        "description": "Represents a direct conflict or incompatibility with another decision.",
        "builtin": True,
        "directional": False,
        "has_status_effect": False,
    },
    "implements": {
        "key": "implements",
        "label": "Implements",
        "inverse_label": "Implemented by",
        "description": "Represents a decision that implements the intent of another decision.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "blocks": {
        "key": "blocks",
        "label": "Blocks",
        "inverse_label": "Blocked by",
        "description": "Represents a decision that prevents another decision from progressing.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "duplicates": {
        "key": "duplicates",
        "label": "Duplicates",
        "inverse_label": "Duplicated by",
        "description": "Represents overlapping decisions that cover the same concern.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "derived_from": {
        "key": "derived_from",
        "label": "Derived from",
        "inverse_label": "Basis for",
        "description": "Builds directly on another decision as an extension or derivative.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "feeds": {
        "key": "feeds",
        "label": "Feeds",
        "inverse_label": "Fed by",
        "description": "Represents one decision providing inputs or outputs to another.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "governs": {
        "key": "governs",
        "label": "Governs",
        "inverse_label": "Governed by",
        "description": "Represents a controlling or policy-setting relationship.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "mitigates": {
        "key": "mitigates",
        "label": "Mitigates",
        "inverse_label": "Mitigated by",
        "description": "Represents a decision that reduces the risk or impact created by another.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "accepts_risk_from": {
        "key": "accepts_risk_from",
        "label": "Accepts risk from",
        "inverse_label": "Risk accepted by",
        "description": "Represents an explicit risk acceptance tied to another decision.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
    "informs": {
        "key": "informs",
        "label": "Informs",
        "inverse_label": "Informed by",
        "description": "Provides context or evidence that informs another decision.",
        "builtin": True,
        "directional": True,
        "has_status_effect": False,
    },
}


PACK_INDEX = {pack["id"]: pack for pack in RELATIONSHIP_PACKS}


def _clone_type_definition(type_definition: Dict[str, Any]) -> Dict[str, Any]:
    return copy.deepcopy(type_definition)


def _collect_pack_ids_for_type(type_key: str) -> List[str]:
    pack_ids: List[str] = []
    for pack in RELATIONSHIP_PACKS:
        if type_key in pack["relationship_types"]:
            pack_ids.append(pack["id"])
    return pack_ids


def _serialize_pack(pack: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "id": pack["id"],
        "label": pack["label"],
        "description": pack["description"],
        "relationship_types": list(pack["relationship_types"]),
        "default_selected": bool(pack.get("default_selected")),
    }


def _serialize_builtin_type(type_key: str) -> Dict[str, Any]:
    type_definition = _clone_type_definition(BUILTIN_RELATIONSHIP_TYPES[type_key])
    type_definition["pack_ids"] = _collect_pack_ids_for_type(type_key)
    return type_definition


def _serialize_custom_type(custom_type: Dict[str, Any]) -> Dict[str, Any]:
    return {
        "key": custom_type["key"],
        "label": custom_type["label"],
        "inverse_label": custom_type.get("inverse_label") or custom_type["label"],
        "description": custom_type.get("description", ""),
        "builtin": False,
        "directional": (custom_type.get("inverse_label") or custom_type["label"]) != custom_type["label"],
        "has_status_effect": False,
        "pack_ids": ["custom"],
    }


def get_core_relationship_catalog() -> Dict[str, Any]:
    return {
        "packs": [_serialize_pack(pack) for pack in RELATIONSHIP_PACKS],
        "types": [_serialize_builtin_type(type_key) for type_key in BUILTIN_RELATIONSHIP_TYPES.keys()],
        "default_selected_pack_ids": list(DEFAULT_SELECTED_PACK_IDS),
    }


def _normalize_pack_ids(raw_pack_ids: Any) -> List[str]:
    if raw_pack_ids is None:
        return list(DEFAULT_SELECTED_PACK_IDS)

    if not isinstance(raw_pack_ids, list):
        raise ValueError("selected_pack_ids must be a list")

    normalized: List[str] = []
    for raw_pack_id in raw_pack_ids:
        pack_id = str(raw_pack_id or "").strip()
        if not pack_id:
            continue
        if pack_id not in PACK_INDEX:
            raise ValueError(f"Unknown relationship pack: {pack_id}")
        if pack_id not in normalized:
            normalized.append(pack_id)
    return normalized


def _normalize_custom_types(raw_custom_types: Any) -> List[Dict[str, Any]]:
    if raw_custom_types is None:
        return []

    if not isinstance(raw_custom_types, list):
        raise ValueError("custom_relationship_types must be a list")

    normalized: List[Dict[str, Any]] = []
    seen_keys = set()

    for index, raw_type in enumerate(raw_custom_types):
        if not isinstance(raw_type, dict):
            raise ValueError(f"custom_relationship_types[{index}] must be an object")

        key = str(raw_type.get("key") or "").strip().lower()
        label = str(raw_type.get("label") or "").strip()
        inverse_label = str(raw_type.get("inverse_label") or "").strip()
        description = str(raw_type.get("description") or "").strip()

        if not key:
            raise ValueError(f"custom_relationship_types[{index}].key is required")
        if not CUSTOM_RELATIONSHIP_KEY_PATTERN.match(key):
            raise ValueError(
                f"custom relationship key '{key}' must match {CUSTOM_RELATIONSHIP_KEY_PATTERN.pattern}"
            )
        if key in BUILTIN_RELATIONSHIP_TYPES:
            raise ValueError(f"custom relationship key '{key}' conflicts with a built-in relationship type")
        if key in seen_keys:
            raise ValueError(f"custom relationship key '{key}' is duplicated")
        if not label:
            raise ValueError(f"custom_relationship_types[{index}].label is required")

        seen_keys.add(key)
        normalized.append(
            {
                "key": key,
                "label": label,
                "inverse_label": inverse_label or label,
                "description": description,
            }
        )

    return normalized


def get_builtin_type_ids_for_packs(selected_pack_ids: Optional[List[str]]) -> List[str]:
    if selected_pack_ids is None:
        selected_pack_ids = list(DEFAULT_SELECTED_PACK_IDS)

    ordered_type_ids: List[str] = []
    seen_type_ids = set()
    for pack in RELATIONSHIP_PACKS:
        if pack["id"] not in selected_pack_ids:
            continue
        for type_id in pack["relationship_types"]:
            if type_id not in seen_type_ids:
                ordered_type_ids.append(type_id)
                seen_type_ids.add(type_id)
    return ordered_type_ids


def normalize_relationship_settings(config: Optional[Dict[str, Any]]) -> Dict[str, Any]:
    config = config or {}

    selected_pack_ids = _normalize_pack_ids(config.get("selected_pack_ids"))
    custom_relationship_types = _normalize_custom_types(config.get("custom_relationship_types"))
    builtin_type_ids = get_builtin_type_ids_for_packs(selected_pack_ids)
    custom_type_ids = [item["key"] for item in custom_relationship_types]
    allowed_type_ids = set(builtin_type_ids) | set(custom_type_ids)

    raw_enabled_types = config.get("enabled_relationship_types")
    if raw_enabled_types is None:
        enabled_relationship_types = builtin_type_ids + custom_type_ids
    else:
        if not isinstance(raw_enabled_types, list):
            raise ValueError("enabled_relationship_types must be a list")

        enabled_relationship_types = []
        seen_enabled = set()
        for raw_type_id in raw_enabled_types:
            type_id = str(raw_type_id or "").strip()
            if not type_id:
                continue
            if type_id not in allowed_type_ids:
                raise ValueError(f"Unknown or unavailable relationship type: {type_id}")
            if type_id not in seen_enabled:
                enabled_relationship_types.append(type_id)
                seen_enabled.add(type_id)

    return {
        "selected_pack_ids": selected_pack_ids,
        "enabled_relationship_types": enabled_relationship_types,
        "custom_relationship_types": custom_relationship_types,
    }


def get_effective_relationship_catalog(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    normalized_config = normalize_relationship_settings(config)
    selected_pack_ids = normalized_config["selected_pack_ids"]
    enabled_type_ids = set(normalized_config["enabled_relationship_types"])
    custom_types_by_key = {
        custom_type["key"]: custom_type
        for custom_type in normalized_config["custom_relationship_types"]
    }

    effective_types: List[Dict[str, Any]] = []
    for type_id in get_builtin_type_ids_for_packs(selected_pack_ids):
        if type_id in enabled_type_ids:
            effective_types.append(_serialize_builtin_type(type_id))

    for custom_type in normalized_config["custom_relationship_types"]:
        if custom_type["key"] in enabled_type_ids:
            effective_types.append(_serialize_custom_type(custom_type))

    type_map = {relationship_type["key"]: relationship_type for relationship_type in effective_types}

    return {
        "packs": [_serialize_pack(PACK_INDEX[pack_id]) for pack_id in selected_pack_ids],
        "types": effective_types,
        "type_map": type_map,
        "custom_types": {key: _serialize_custom_type(value) for key, value in custom_types_by_key.items()},
        "default_selected_pack_ids": list(DEFAULT_SELECTED_PACK_IDS),
    }


def get_relationship_type_config(
    relationship_type: str,
    config: Optional[Dict[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    effective_catalog = get_effective_relationship_catalog(config)
    return effective_catalog["type_map"].get(relationship_type)


def is_valid_relationship_type(
    relationship_type: str,
    config: Optional[Dict[str, Any]] = None,
) -> bool:
    return get_relationship_type_config(relationship_type, config=config) is not None


def build_relationship_settings_payload(config: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    normalized_config = normalize_relationship_settings(config)
    return {
        "config": normalized_config,
        "effective_catalog": {
            "packs": get_effective_relationship_catalog(normalized_config)["packs"],
            "types": get_effective_relationship_catalog(normalized_config)["types"],
            "default_selected_pack_ids": list(DEFAULT_SELECTED_PACK_IDS),
        },
        "available_catalog": get_core_relationship_catalog(),
    }
