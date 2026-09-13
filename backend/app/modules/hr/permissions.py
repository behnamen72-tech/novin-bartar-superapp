HR_READ = "hr.read"
HR_MANAGE = "hr.manage"

HR_PERMISSION_DEFINITIONS: tuple[tuple[str, str, str], ...] = (
    (
        HR_READ,
        "Read HR foundation",
        "View HR job profiles, planned positions, and employment records within authorized organization scope.",
    ),
    (
        HR_MANAGE,
        "Manage HR foundation",
        "Create and manage HR job profiles, positions, and employment records within authorized organization scope.",
    ),
)
