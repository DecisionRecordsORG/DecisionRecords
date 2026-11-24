"""Decision templates and the industry list that suggests one.

A template changes how a decision is presented: the headings and guidance of
the three text sections, example titles, a list of decision types and the
relationship packs suggested with it. It never changes what is stored. Every
template's three sections keep the meaning of the stored fields ``context``,
``decision`` and ``consequences``, so text written under one template still
belongs under the matching heading of any other.

The industry list is the 22 top-level sections of NACE Rev. 2.1 (Eurostat),
with their official English titles unchanged. Only the section letter is
stored for a tenant. A section suggests a template; an administrator may
choose any template.

Static data, shaped like ``decision_relationships.py``. The web app reads it
through the API, so this module is the only copy.
"""
import copy
from typing import Any, Dict, List, Optional

from decision_relationships import PACK_INDEX, get_builtin_type_ids_for_packs


DEFAULT_TEMPLATE_ID = "general"
SECTION_KEYS = ("context", "decision", "consequences")
DECISION_TYPE_MAX_LENGTH = 100

# Shown wherever a template can be changed.
TEMPLATE_CHANGE_GUARANTEE = (
    "Changing the template changes headings and prompts only. "
    "Your decisions are not altered, and you can change back at any time."
)

INDUSTRY_CREDIT = "Industry sections: NACE Rev. 2.1, Eurostat, CC BY 4.0"

# NACE Rev. 2.1 sections, as published by Eurostat. Do not reword, merge or
# reorder: the titles are quoted, and the letter is what is stored.
NACE_SECTIONS: List[Dict[str, str]] = [
    {"code": "A", "title": "Agriculture, forestry and fishing"},
    {"code": "B", "title": "Mining and quarrying"},
    {"code": "C", "title": "Manufacturing"},
    {"code": "D", "title": "Electricity, gas, steam and air conditioning supply"},
    {"code": "E", "title": "Water supply; sewerage, waste management and remediation activities"},
    {"code": "F", "title": "Construction"},
    {"code": "G", "title": "Wholesale and retail trade"},
    {"code": "H", "title": "Transportation and storage"},
    {"code": "I", "title": "Accommodation and food service activities"},
    {"code": "J", "title": "Publishing, broadcasting, and content production and distribution activities"},
    {
        "code": "K",
        "title": (
            "Telecommunication, computer programming, consulting, computing infrastructure "
            "and other information service activities"
        ),
    },
    {"code": "L", "title": "Financial and insurance activities"},
    {"code": "M", "title": "Real estate activities"},
    {"code": "N", "title": "Professional, scientific and technical activities"},
    {"code": "O", "title": "Administrative and support service activities"},
    {"code": "P", "title": "Public administration and defence; compulsory social security"},
    {"code": "Q", "title": "Education"},
    {"code": "R", "title": "Human health and social work activities"},
    {"code": "S", "title": "Arts, sports and recreation"},
    {"code": "T", "title": "Other service activities"},
    {
        "code": "U",
        "title": (
            "Activities of households as employers and undifferentiated goods- and "
            "service-producing activities of households for own use"
        ),
    },
    {"code": "V", "title": "Activities of extraterritorial organisations and bodies"},
]

NACE_SECTION_INDEX = {section["code"]: section for section in NACE_SECTIONS}

# Which template each section suggests. A section that is not listed here, and
# a tenant that has not chosen a section, gets the default template.
SECTION_TEMPLATE_IDS: Dict[str, str] = {
    "B": "controlled_change",
    "C": "controlled_change",
    "D": "controlled_change",
    "E": "controlled_change",
    "F": "controlled_change",
    "K": "software",
    "L": "investment",
    "P": "governance",
    "Q": "governance",
    "R": "governance",
    "V": "governance",
}


DECISION_TEMPLATES: List[Dict[str, Any]] = [
    {
        "id": "general",
        "label": "General",
        "description": "Fits any kind of decision. This is the layout every organisation starts with.",
        "title": {
            "placeholder": "For example: Move to quarterly pricing reviews",
            "hint": "A short name people will recognise in a list.",
        },
        "sections": {
            "context": {
                "label": "Context",
                "placeholder": (
                    "What prompted this decision? Describe the situation, the problem and "
                    "anything that limits your options."
                ),
                "hint": "The background someone needs to understand why this came up.",
            },
            "decision": {
                "label": "Decision",
                "placeholder": (
                    "What did you decide? State the choice plainly and mention the options you turned down."
                ),
                "hint": "What was decided, in words that make sense on their own.",
            },
            "consequences": {
                "label": "Consequences",
                "placeholder": (
                    "What changes because of this? Include the benefits, the costs and the risks you accept."
                ),
                "hint": "What follows from the decision, good and bad.",
            },
        },
        "decision_types": [
            "Policy",
            "Pricing and commercial terms",
            "Supplier or partner",
            "People and hiring",
            "Process or way of working",
            "Spending",
            "Customer commitment",
        ],
        "suggested_pack_ids": ["core", "people", "finance", "product"],
        "example_titles": [
            "Move to quarterly pricing reviews",
            "Appoint a second packaging supplier for the autumn range",
        ],
        "caution": None,
    },
    {
        "id": "software",
        "label": "Software and technology",
        "description": (
            "For software, IT and platform teams. The headings are the same as General; "
            "the prompts, decision types and suggested packs follow the usual architecture decision record."
        ),
        "title": {
            "placeholder": "For example: Use PostgreSQL for the orders service",
            "hint": "A short name people will recognise in a list.",
        },
        "sections": {
            "context": {
                "label": "Context",
                "placeholder": (
                    "What problem are you solving? Describe the forces at play and the options you considered."
                ),
                "hint": "The problem, the forces at play and the options considered.",
            },
            "decision": {
                "label": "Decision",
                "placeholder": "Which option did you choose, and why did it win?",
                "hint": "The option chosen and why it won.",
            },
            "consequences": {
                "label": "Consequences",
                "placeholder": (
                    "What becomes easier or harder? Note the follow-up work and how you will confirm it worked."
                ),
                "hint": "What becomes easier or harder, follow-up work, and how you will confirm it worked.",
            },
        },
        "decision_types": [
            "Architecture",
            "Technology or vendor choice",
            "Data and storage",
            "Security",
            "Infrastructure and operations",
            "API or interface",
            "Standards and conventions",
            "Build or buy",
        ],
        "suggested_pack_ids": ["core", "software", "data", "security", "operations"],
        "example_titles": [
            "Use PostgreSQL for the orders service",
            "Retire the v1 public API on 30 June",
        ],
        "caution": None,
    },
    {
        "id": "controlled_change",
        "label": "Controlled change",
        "description": (
            "For changes to a product, process, plant, drawing or contract that are assessed and "
            "approved before they are made. A layout based on how change records are commonly written."
        ),
        "title": {
            "placeholder": "For example: Change the seal material on pump P-204 to FKM",
            "hint": "A short name people will recognise in a list.",
        },
        "sections": {
            "context": {
                "label": "Change and reason",
                "placeholder": (
                    "What is proposed to change, and what does it affect (product, process, plant, drawing, "
                    "contract)? Say why it is needed and, if it is temporary, how long it applies."
                ),
                "hint": "What is proposed to change, what it affects and why it is needed.",
            },
            "decision": {
                "label": "Decision and approval",
                "placeholder": (
                    "Approved, approved with conditions or rejected? Say who approved it and on what basis, "
                    "and what was turned down."
                ),
                "hint": "The outcome, who approved it and on what basis.",
            },
            "consequences": {
                "label": "Impact and follow-up",
                "placeholder": (
                    "What is the effect on safety, quality, cost and schedule? List the documents and "
                    "procedures to update, the training needed, and how and when the change will be "
                    "checked afterwards."
                ),
                "hint": "Effect on safety, quality, cost and schedule, and what has to follow.",
            },
        },
        "decision_types": [
            "Design or specification change",
            "Process or procedure change",
            "Supplier or material change",
            "Equipment or plant modification",
            "Temporary change or deviation",
            "Concession or waiver",
            "Contract variation (cost or time)",
            "Corrective action",
        ],
        "suggested_pack_ids": ["core", "operations", "security"],
        "example_titles": [
            "Change the seal material on pump P-204 to FKM",
            "Accept variation 17: revised fire-stopping detail on levels 3 to 6",
        ],
        "caution": (
            "This layout follows common change-record practice. "
            "It does not replace your quality or safety management system."
        ),
    },
    {
        "id": "governance",
        "label": "Governance and committee",
        "description": (
            "For boards, trustees, committees and officers who decide under a stated authority, "
            "in any kind of organisation. A layout based on how decision records and minutes are commonly written."
        ),
        "title": {
            "placeholder": "For example: Adopt the revised safeguarding policy from 1 September",
            "hint": "A short name people will recognise in a list.",
        },
        "sections": {
            "context": {
                "label": "Matter and background",
                "placeholder": (
                    "What was put for decision, and by whom? Note the information relied on and any advice taken."
                ),
                "hint": "What was put for decision, by whom, and the information and advice relied on.",
            },
            "decision": {
                "label": "Decision and reasons",
                "placeholder": (
                    "Give the decision or resolution in its exact wording, the body or officer who took it "
                    "and under what authority, and the reasons."
                ),
                "hint": "The exact wording, who decided under what authority, and the reasons.",
            },
            "consequences": {
                "label": "Alternatives, interests and implications",
                "placeholder": (
                    "Which alternatives were considered and rejected? Record conflicts of interest declared "
                    "and how they were handled, the financial, legal and equality implications, and the "
                    "actions and review date."
                ),
                "hint": "Alternatives rejected, interests declared, implications, actions and review date.",
            },
        },
        "decision_types": [
            "Policy adoption or change",
            "Budget and spending approval",
            "Appointment",
            "Delegated officer decision",
            "Procurement or contract award",
            "Service change",
            "Curriculum or programme approval",
            "Clinical governance (pathway, formulary, protocol)",
        ],
        "suggested_pack_ids": ["core", "people", "finance"],
        "example_titles": [
            "Adopt the revised safeguarding policy from 1 September",
            "Award the grounds maintenance contract for 2027 to 2030",
        ],
        "caution": "Do not record decisions about identifiable patients, pupils or service users here.",
    },
    {
        "id": "investment",
        "label": "Investment and approval",
        "description": (
            "For investment, credit and large spending decisions taken under a mandate. "
            "A layout based on how committee papers for such approvals are commonly written."
        ),
        "title": {
            "placeholder": "For example: Approve a EUR 2m revolving facility for Northwind Logistics, valid 90 days",
            "hint": "A short name people will recognise in a list.",
        },
        "sections": {
            "context": {
                "label": "Proposal and assessment",
                "placeholder": (
                    "What is proposed? Give the amount and counterparty, the analysis, and the case for and against."
                ),
                "hint": "What is proposed, the amount and counterparty, and the analysis.",
            },
            "decision": {
                "label": "Decision and conditions",
                "placeholder": (
                    "Approved, declined or deferred? Say by whom and under which authority, the terms, "
                    "conditions and pre-conditions, and how long the approval is valid."
                ),
                "hint": "The outcome, the authority, the conditions and how long the approval is valid.",
            },
            "consequences": {
                "label": "Risks and monitoring",
                "placeholder": (
                    "Which risks are accepted? Note limits and exposure, exceptions to policy, and how it "
                    "will be monitored and reviewed."
                ),
                "hint": "Risks accepted, limits and exceptions, and how it will be monitored.",
            },
        },
        "decision_types": [
            "Investment",
            "Credit approval",
            "Policy exception",
            "Limit or mandate change",
            "Product approval",
            "Counterparty or vendor approval",
            "Write-off or provision",
        ],
        "suggested_pack_ids": ["core", "finance", "security"],
        "example_titles": [
            "Approve a EUR 2m revolving facility for Northwind Logistics, valid 90 days",
            "Decline the follow-on investment in Fund IV",
        ],
        "caution": None,
    },
]

TEMPLATE_INDEX = {template["id"]: template for template in DECISION_TEMPLATES}


def _serialize_template(template: Dict[str, Any]) -> Dict[str, Any]:
    data = copy.deepcopy(template)
    data["is_default"] = template["id"] == DEFAULT_TEMPLATE_ID
    data["suggested_packs"] = [
        {"id": pack_id, "label": PACK_INDEX[pack_id]["label"]}
        for pack_id in template["suggested_pack_ids"]
    ]
    return data


def suggested_template_id(industry: Optional[str]) -> str:
    """The template a NACE section suggests; the default for none or an unknown one."""
    return SECTION_TEMPLATE_IDS.get(industry or "", DEFAULT_TEMPLATE_ID)


def normalize_template_id(raw_template_id: Any) -> Optional[str]:
    """A known template id, or None for "not chosen". Raises ValueError for anything else."""
    if raw_template_id is None:
        return None
    if not isinstance(raw_template_id, str):
        raise ValueError("Unknown decision template")
    template_id = raw_template_id.strip()
    if not template_id:
        return None
    if template_id not in TEMPLATE_INDEX:
        raise ValueError(f"Unknown decision template: {template_id[:64]}")
    return template_id


def normalize_industry(raw_industry: Any) -> Optional[str]:
    """A NACE section letter, or None for "not chosen". Raises ValueError for anything else."""
    if raw_industry is None:
        return None
    if not isinstance(raw_industry, str):
        raise ValueError("Unknown industry section")
    industry = raw_industry.strip().upper()
    if not industry:
        return None
    if industry not in NACE_SECTION_INDEX:
        raise ValueError(f"Unknown industry section: {industry[:8]}")
    return industry


def get_template(template_id: Optional[str]) -> Dict[str, Any]:
    """The template for a stored id. A missing or no longer known id gives the default."""
    template = TEMPLATE_INDEX.get(template_id or DEFAULT_TEMPLATE_ID) or TEMPLATE_INDEX[DEFAULT_TEMPLATE_ID]
    return _serialize_template(template)


def get_decision_types(template_id: Optional[str]) -> List[str]:
    template = TEMPLATE_INDEX.get(template_id or DEFAULT_TEMPLATE_ID) or TEMPLATE_INDEX[DEFAULT_TEMPLATE_ID]
    return list(template["decision_types"])


def normalize_decision_type(raw_type: Any, template_id: Optional[str], stored_type: Optional[str] = None) -> Optional[str]:
    """Validate a decision type against a template.

    None or an empty string means "no type". Otherwise the value must be one
    of the template's types, or the value already stored on the decision (a
    type kept from an earlier template stays valid for that decision).
    """
    if raw_type is None:
        return None
    if not isinstance(raw_type, str):
        raise ValueError("Decision type must be text")
    decision_type = raw_type.strip()
    if not decision_type:
        return None
    if stored_type is not None and decision_type == stored_type:
        return decision_type
    if len(decision_type) > DECISION_TYPE_MAX_LENGTH or decision_type not in get_decision_types(template_id):
        raise ValueError("Decision type is not one of the types of the current decision template")
    return decision_type


def add_suggested_packs(relationship_config: Dict[str, Any], template_id: Optional[str]):
    """A tenant's relationship settings with a template's suggested packs switched on.

    Takes and returns the normalised settings of decision_relationships.py.
    Packs are only added. A relationship class the tenant could already use
    keeps the state it has, so a class that was switched off stays off; the
    classes that come new with an added pack are switched on.

    Returns (settings, ids of the packs that were added).
    """
    selected = list(relationship_config["selected_pack_ids"])
    added = [pack_id for pack_id in get_template(template_id)["suggested_pack_ids"] if pack_id not in selected]
    if not added:
        return relationship_config, []

    already_available = set(get_builtin_type_ids_for_packs(selected))
    custom_keys = {item["key"] for item in relationship_config["custom_relationship_types"]}
    enabled = list(relationship_config["enabled_relationship_types"])
    for type_id in get_builtin_type_ids_for_packs(selected + added):
        if type_id not in already_available and type_id not in custom_keys and type_id not in enabled:
            enabled.append(type_id)

    return {
        "selected_pack_ids": selected + added,
        "enabled_relationship_types": enabled,
        "custom_relationship_types": relationship_config["custom_relationship_types"],
    }, added


def get_decision_template_catalog() -> Dict[str, Any]:
    return {
        "templates": [_serialize_template(template) for template in DECISION_TEMPLATES],
        "default_template_id": DEFAULT_TEMPLATE_ID,
        "industries": [
            {
                "code": section["code"],
                "title": section["title"],
                "suggested_template_id": suggested_template_id(section["code"]),
            }
            for section in NACE_SECTIONS
        ],
        "industry_credit": INDUSTRY_CREDIT,
        "guarantee": TEMPLATE_CHANGE_GUARANTEE,
    }


def build_tenant_template_payload(template_id: Optional[str], industry: Optional[str]) -> Dict[str, Any]:
    """What a tenant's members need to show decisions: the effective template and the industry."""
    template = get_template(template_id)
    section = NACE_SECTION_INDEX.get(industry or "")
    return {
        "template_id": template["id"],
        "template_chosen": bool(template_id) and template_id in TEMPLATE_INDEX,
        "template": template,
        "industry": section["code"] if section else None,
        "industry_title": section["title"] if section else None,
        "suggested_template_id": suggested_template_id(section["code"] if section else None),
        "guarantee": TEMPLATE_CHANGE_GUARANTEE,
    }
