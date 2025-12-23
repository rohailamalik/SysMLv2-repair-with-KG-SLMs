from vehicle_kg import TYPE_TO_DOMAIN, VALID_CONNECTIONS
import re


def get_domain_rules(code: str) -> str:
    """Scans code and retrieves relevant domain rules."""

    found_domains: set[str] = set()
    context_lines: list[str] = []
    
    # Find all matching types and their domains
    for type_name, domain in TYPE_TO_DOMAIN.items():
        if re.search(rf'\b{re.escape(type_name)}\b', code):
            context_lines.append(f"- '{type_name}' belongs to Domain: {domain}")
            found_domains.add(domain)
    
    # Add connection rules if domains were found
    if found_domains:
        context_lines.append("\nValid Connections Rules:")
        for domain in sorted(found_domains):  # Sort for consistency
            allowed = VALID_CONNECTIONS.get(domain, [])
            context_lines.append(f"- {domain} can ONLY connect to: {allowed}")
    
    rules = "Domain Rules:\n" + "\n".join(context_lines)

    return rules