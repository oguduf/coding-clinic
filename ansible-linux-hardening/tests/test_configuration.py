from pathlib import Path

import yaml
from jinja2 import Environment, StrictUndefined


ROOT = Path(__file__).resolve().parents[1]
JINJA = Environment(undefined=StrictUndefined, autoescape=False)


def to_bool(value: object) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "yes", "on", "1"}


JINJA.filters["bool"] = to_bool


def load_yaml(path: Path):
    with path.open(encoding="utf-8") as stream:
        return yaml.safe_load(stream)


def render(relative_path: str, **context: object) -> str:
    template_path = ROOT / relative_path
    return JINJA.from_string(template_path.read_text(encoding="utf-8")).render(**context)


def test_project_yaml_files_parse():
    files = [
        *ROOT.rglob("*.yml"),
        *ROOT.rglob("*.yaml"),
    ]
    assert files
    for path in files:
        if ".git" not in path.parts and ".venv" not in path.parts:
            load_yaml(path)


def test_playbook_is_guarded_and_uses_all_three_roles():
    play = load_yaml(ROOT / "playbooks/harden-linux.yml")[0]
    assert play["hosts"] == "linux"
    assert play["gather_facts"] is False
    assert play["pre_tasks"][0]["delegate_to"] == "localhost"
    assert play["pre_tasks"][0]["run_once"] is True
    assert [entry["role"] for entry in play["roles"]] == [
        "ssh_hardening",
        "fail2ban",
        "security_updates",
    ]
    assert load_yaml(ROOT / "group_vars/all.yml")["hardening_approved"] is False


def test_all_inventory_addresses_are_documentation_only():
    inventories = list((ROOT / "inventories").rglob("hosts.yml"))
    assert {path.parent.name for path in inventories} == {"dev", "stage", "prod"}
    for path in inventories:
        text = path.read_text(encoding="utf-8")
        inventory = load_yaml(path)
        assert "ansible_private_key_file" not in text
        assert "ansible_password" not in text
        assert all(
            host["ansible_host"].startswith(("192.0.2.", "198.51.100."))
            for group in inventory["all"]["children"]["linux"]["children"].values()
            for host in group["hosts"].values()
        )


def test_environment_group_vars_demonstrate_distinct_policy():
    policies = {
        environment: load_yaml(ROOT / f"inventories/{environment}/group_vars/linux.yml")
        for environment in ("dev", "stage", "prod")
    }
    assert policies["dev"]["fail2ban_maxretry"] > policies["stage"]["fail2ban_maxretry"]
    assert policies["prod"]["fail2ban_maxretry"] < policies["stage"]["fail2ban_maxretry"]
    assert policies["prod"]["fail2ban_bantime"] > policies["stage"]["fail2ban_bantime"]
    assert all(policy["security_updates_auto_reboot"] is False for policy in policies.values())


def test_ssh_template_has_secure_baseline_and_safe_auth_default():
    defaults = load_yaml(ROOT / "roles/ssh_hardening/defaults/main.yml")
    assert defaults["ssh_hardening_password_authentication"] is True
    assert defaults["ssh_hardening_key_access_verified"] is False
    config = render("roles/ssh_hardening/templates/ssh-hardening.conf.j2", **defaults)
    assert "PermitRootLogin no" in config
    assert "PermitEmptyPasswords no" in config
    assert "PubkeyAuthentication yes" in config
    assert "PasswordAuthentication yes" in config
    assert "Protocol 2" not in config

    password_disabled = render(
        "roles/ssh_hardening/templates/ssh-hardening.conf.j2",
        **{**defaults, "ssh_hardening_password_authentication": False},
    )
    assert "PasswordAuthentication no" in password_disabled
    assert "AuthenticationMethods publickey" in password_disabled


def test_fail2ban_template_uses_journald_and_loopback_only_defaults():
    defaults = load_yaml(ROOT / "roles/fail2ban/defaults/main.yml")
    config = render("roles/fail2ban/templates/jail.local.j2", **defaults)
    assert "[sshd]" in config
    assert "enabled = true" in config
    assert "backend = systemd" in config
    assert "127.0.0.1/8 ::1" in config
    assert "0.0.0.0/0" not in config


def test_update_templates_disable_reboot_by_default():
    defaults = load_yaml(ROOT / "roles/security_updates/defaults/main.yml")
    apt_config = render("roles/security_updates/templates/unattended-upgrades.j2", **defaults)
    dnf_config = render("roles/security_updates/templates/automatic.conf.j2", **defaults)
    timer_config = render(
        "roles/security_updates/templates/dnf-automatic-install.timer.conf.j2", **defaults
    )
    assert 'Automatic-Reboot "false"' in apt_config
    assert "#clear Unattended-Upgrade::Allowed-Origins;" in apt_config
    assert "Unattended-Upgrade::Allowed-Origins" in apt_config
    assert "upgrade_type = security" in dnf_config
    assert "reboot = never" in dnf_config
    assert "OnCalendar=*-*-* 03:00:00" in timer_config


def test_role_meta_and_os_task_files_exist():
    for role in ("ssh_hardening", "fail2ban", "security_updates"):
        base = ROOT / "roles" / role
        assert (base / "defaults/main.yml").is_file()
        assert (base / "tasks/main.yml").is_file()
        assert (base / "tasks/ubuntu.yml").is_file()
        assert (base / "tasks/rhel.yml").is_file()
        assert (base / "handlers/main.yml").is_file()
        assert (base / "meta/main.yml").is_file()


def test_jinja_templates_parse():
    templates = list((ROOT / "roles").rglob("*.j2"))
    assert len(templates) >= 4
    for path in templates:
        JINJA.parse(path.read_text(encoding="utf-8"))

