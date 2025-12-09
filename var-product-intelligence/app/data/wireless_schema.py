"""Wireless Access Points category schema definition."""

from sqlalchemy.orm import Session

from app.models.category import Category

# Wireless AP attribute schema based on design document
WIRELESS_SCHEMA = {
    "type": "object",
    "properties": {
        "wifi_generation": {
            "type": "string",
            "enum": ["wifi5", "wifi6", "wifi6e", "wifi7"],
            "description": "WiFi standard generation",
            "label": "WiFi Generation",
        },
        "radio_config": {
            "type": "string",
            "description": "MIMO configuration (e.g., 4x4:4, 8x8:8)",
            "label": "Radio Configuration",
        },
        "max_throughput_mbps": {
            "type": "integer",
            "description": "Maximum throughput in Mbps",
            "label": "Max Throughput (Mbps)",
        },
        "concurrent_clients": {
            "type": "integer",
            "description": "Maximum concurrent client connections",
            "label": "Concurrent Clients",
        },
        "bands": {
            "type": "array",
            "items": {"type": "string", "enum": ["2.4ghz", "5ghz", "6ghz"]},
            "description": "Supported frequency bands",
            "label": "Frequency Bands",
        },
        "form_factor": {
            "type": "string",
            "enum": ["indoor", "outdoor", "ruggedized", "wall_plate"],
            "description": "Physical deployment type",
            "label": "Form Factor",
        },
        "uplink_speed": {
            "type": "string",
            "enum": ["1g", "2.5g", "5g", "10g"],
            "description": "Ethernet uplink speed",
            "label": "Uplink Speed",
        },
        "poe_requirement": {
            "type": "string",
            "enum": ["802.3af", "802.3at", "802.3bt"],
            "description": "Power over Ethernet standard required",
            "label": "PoE Requirement",
        },
        "management_type": {
            "type": "string",
            "enum": ["cloud", "controller", "on_prem", "standalone"],
            "description": "Management model",
            "label": "Management Type",
        },
        "subscription_required": {
            "type": "boolean",
            "description": "Whether a subscription is required",
            "label": "Subscription Required",
        },
        "annual_subscription_cost": {
            "type": "number",
            "description": "Annual license/subscription cost in USD",
            "label": "Annual Subscription Cost",
        },
        "wpa3_support": {
            "type": "boolean",
            "description": "WPA3 security support",
            "label": "WPA3 Support",
        },
        "iot_radios": {
            "type": "array",
            "items": {"type": "string", "enum": ["ble", "zigbee", "thread"]},
            "description": "Built-in IoT radio types",
            "label": "IoT Radios",
        },
        "location_services": {
            "type": "boolean",
            "description": "Location/positioning capabilities",
            "label": "Location Services",
        },
        "ai_optimization": {
            "type": "boolean",
            "description": "AI/ML-based RF optimization",
            "label": "AI Optimization",
        },
    },
}


def get_filterable_attributes() -> list[dict]:
    """Get list of filterable attributes from wireless schema.

    Returns list of attribute definitions suitable for API response.
    """
    attributes = []
    for key, prop in WIRELESS_SCHEMA["properties"].items():
        attr = {
            "key": key,
            "label": prop.get("label", key.replace("_", " ").title()),
            "type": prop["type"],
            "description": prop.get("description"),
        }
        if "enum" in prop:
            attr["values"] = prop["enum"]
        elif prop["type"] == "array" and "items" in prop and "enum" in prop["items"]:
            attr["values"] = prop["items"]["enum"]
        attributes.append(attr)
    return attributes


def ensure_wireless_category(db: Session) -> Category:
    """Ensure the wireless category exists in the database.

    Creates the category if it doesn't exist.

    Args:
        db: Database session

    Returns:
        The wireless category
    """
    category = db.query(Category).filter(Category.id == "wireless").first()

    if category is None:
        category = Category(
            id="wireless",
            name="Wireless Access Points",
            description="Enterprise wireless access points for indoor and outdoor deployments",
        )
        category.attribute_schema = WIRELESS_SCHEMA
        db.add(category)
        db.commit()
        db.refresh(category)

    return category
