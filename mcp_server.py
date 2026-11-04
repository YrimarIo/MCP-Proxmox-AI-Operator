import os
from dotenv import load_dotenv

# IMPORTANT: Use this import path so the 'mcp dev' inspector works properly
from fastmcp import FastMCP 

from core.proxmox_mgr import ProxmoxManager

# 1. Load environment
load_dotenv()

# 2. Initialize MCP server
mcp = FastMCP("Proxmox-Operator")

# 3. Initialize Proxmox Manager
proxmox = ProxmoxManager(
    os.getenv("PVE_HOST"), 
    os.getenv("PVE_USER"),
    os.getenv("PVE_TOKEN_NAME"), 
    os.getenv("PVE_TOKEN_VALUE")
)

# --- MCP TOOLS ---

@mcp.tool()
def list_vms(node: str = None) -> str:
    """Lists all VMs on a Proxmox node."""
    return proxmox.list_vms(node=node)

@mcp.tool()
def get_vm_status(vmid: str, node: str = None) -> str:
    """Retrieves the current status (CPU, RAM, uptime) of a VM."""
    return proxmox.get_vm_status(vmid, node=node)

@mcp.tool()
def create_proxmox_vm(name: str, disk_gb: int, memory: int = 2048, cores: int = 1, iso: str = None, use_cloudinit: bool = False, vlan: int = None, storage: str = None) -> str:
    """
    Creates a new virtual machine.
    If Cloud-Init is required, set use_cloudinit to True.
    """
    return proxmox.create_vm(
        name=name, 
        disk_gb=disk_gb, 
        memory=memory, 
        cores=cores, 
        iso=iso, 
        use_cloudinit=use_cloudinit, 
        vlan=vlan,
        storage=storage
    )

@mcp.tool()
def delete_vm(vmid: int, node: str = None) -> str:
    """Permanently deletes a VM by its ID."""
    return proxmox.delete_vm(vmid=vmid, node=node)

@mcp.tool()
def manage_vm_power(vmid: str, action: str, node: str = None) -> str:
    """Controls the power state of a VM (start, stop)."""
    if action.lower() == "start":
        return proxmox.start_vm(vmid, node=node)
    elif action.lower() == "stop":
        return proxmox.stop_vm(vmid, node=node)
    return "Error: Action must be 'start' or 'stop'."

@mcp.tool()
def add_vm_disk(vmid: int, size_gb: int, node: str = None, storage: str = None) -> str:
    """Adds an additional disk to a VM."""
    return proxmox.add_vm_disk(vmid=vmid, size_gb=size_gb, node=node, storage=storage)

@mcp.tool()
def list_available_isos(storage: str = "local", node: str = None) -> str:
    """Lists all available ISO files on the server."""
    isos = proxmox.list_isos(storage=storage, node=node)
    return f"Available ISOs: {', '.join(isos)}" if isos else "No ISOs found."

@mcp.tool()
def create_snapshot(vmid: str, snapname: str, description: str = None, node: str = None) -> str:
    """Creates a snapshot of a VM."""
    return proxmox.create_snapshot(vmid=vmid, snapname=snapname, description=description, node=node)

@mcp.tool()
def rollback_snapshot(vmid: str, snapname: str, node: str = None) -> str:
    """Reverts a VM to an existing snapshot."""
    return proxmox.rollback_snapshot(vmid=vmid, snapname=snapname, node=node)

@mcp.tool()
def list_snapshots(vmid: str, node: str = None) -> str:
    """Lists all available snapshots of a specific VM."""
    return proxmox.list_snapshots(vmid=vmid, node=node)

@mcp.tool()
def setup_cloudinit(vmid: str, user: str, password: str = None, ssh_key: str = None, node: str = None) -> str:
    """Configures Cloud-Init parameters (user, password, SSH key) for a VM."""
    return proxmox.setup_cloudinit(vmid=vmid, user=user, password=password, ssh_key=ssh_key, node=node)

@mcp.tool()
def add_cloudinit_drive(vmid: str, storage: str = None, node: str = None) -> str:
    """Adds a Cloud-Init drive to a VM (required for Cloud-Init configuration)."""
    return proxmox.add_cloudinit_drive(vmid=vmid, storage=storage, node=node)

@mcp.tool()
def set_vm_vlan(vmid: str, vlan: int, interface: str = "net0", node: str = None) -> str:
    """Modifies the VLAN tag of a network interface on a VM."""
    return proxmox.set_vm_vlan(vmid=vmid, vlan=vlan, interface=interface, node=node)

@mcp.tool()
def mount_iso(vmid: str, iso: str, node: str = None) -> str:
    """Mounts an ISO file into a VM's virtual drive."""
    return proxmox.mount_iso(vmid=vmid, iso=iso, node=node)

@mcp.tool()
def eject_iso(vmid: str, node: str = None) -> str:
    """Ejects the ISO media from a VM's virtual drive."""
    return proxmox.eject_iso(vmid=vmid, node=node)

@mcp.tool()
def get_vm_hardware(vmid: str, node: str = None) -> str:
    """Retrieves detailed hardware configuration of a VM."""
    return proxmox.get_vm_hardware(vmid=vmid, node=node)

@mcp.tool()
def get_node_status(node: str = None) -> str:
    """Checks the current resource utilization (RAM/CPU) of the physical Proxmox node."""
    res = proxmox.get_node_resources(node=node)
    if res:
        return (f"Node status ({res['node']}):\n"
                f"- Free RAM: {res['free_ram_mb']} MB (out of {res['total_ram_mb']} MB)\n"
                f"- CPU Load: {res['cpu_load_percent']}%")
    return "Error retrieving node status."

# --- LXC TOOLS ---

@mcp.tool()
def list_lxcs(node: str = None) -> str:
    """Lists all LXC containers on the Proxmox server."""
    return proxmox.list_lxcs(node=node)

@mcp.tool()
def create_proxmox_lxc(hostname: str, ostemplate: str, memory: int = 512, cores: int = 1, disk_gb: int = 8, password: str = None) -> str:
    """
    Creates a new Linux Container (LXC).
    Note: ostemplate must be a valid file name from the local:vztmpl storage.
    """
    return proxmox.create_lxc(hostname=hostname, ostemplate=ostemplate, memory=memory, cores=cores, disk_gb=disk_gb, password=password)

@mcp.tool()
def manage_lxc_status(vmid: int, action: str, node: str = None) -> str:
    """Controls the status of an LXC container (start, stop, shutdown)."""
    return proxmox.manage_lxc_power(vmid=vmid, action=action, node=node)

@mcp.tool()
def list_lxc_templates(storage: str = "local") -> str:
    """Lists all available LXC container templates."""
    templates = proxmox.list_lxc_templates(storage=storage)
    return f"Available LXC templates: {', '.join(templates)}" if templates else "No templates found."


if __name__ == "__main__":
    # Starts the server in SSE mode on port 8000
    mcp.run(transport="sse", host="0.0.0.0", port=8000)