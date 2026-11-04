import os
from dotenv import load_dotenv
from core.proxmox_mgr import ProxmoxManager
from core.ai_brain import AIBrain
from utils.logger import log

load_dotenv()

def main():
    # 1. Initialize components
    proxmox = ProxmoxManager(
        os.getenv("PVE_HOST"), 
        os.getenv("PVE_USER"),
        os.getenv("PVE_TOKEN_NAME"), 
        os.getenv("PVE_TOKEN_VALUE")
    )
    
    ollama_host = os.getenv("OLLAMA_HOST")
    ollama_model = os.getenv("OLLAMA_MODEL")

    prompt = (
        f"You are a technical Proxmox expert. Node: {proxmox.default_node}. "
        f"Disks are placed into storage '{proxmox.default_storage}', "
        f"but ISO files are stored EXCLUSIVELY in storage 'local'.\n"
        "RULES FOR COMPLEX TASKS:\n"
        "1. Whenever you need to create a VM, ALWAYS search for the correct file using 'list_available_isos' first.\n"
        "2. Use the search result for the 'create_vm' command.\n"
        "3. If user data is provided, set 'use_cloudinit' to True and run 'setup_cloudinit' afterward.\n"
        "Proceed step by step and wait for the tool execution results."
    )
    brain = AIBrain(ollama_host, ollama_model, prompt)

    log.info(f"--- AI Operator ready (Ollama @ {ollama_host}) ---")
    
    while True:
        u_input = input("\nYou: ").strip()
        if u_input.lower() in ["exit", "quit", "end"]:
            print("Bot: See you soon!")
            break
        if not u_input:
            continue
        
        # 2. AI analyzes the input
        response_msg = brain.chat(u_input)
        
        if not response_msg:
            print("Bot: Sorry, I encountered an issue with your request.")
            continue

        # --- START TOOL CHAINING ---

        while response_msg and response_msg.tool_calls:
            brain.messages.append(response_msg)

            for tool in response_msg.tool_calls:
                t_name = tool.function.name
                t_args = tool.function.arguments
                log.info(f"AI action detected: {t_name}")

                result = ""
                
                # --- Tool mapping ---
                if t_name == "list_vms":
                    result = str(proxmox.list_vms(**t_args))

                elif t_name == "get_vm_status":
                    print(f"   [System]: Checking status for VM/Name: {t_args.get('vmid')}...")
                    result = proxmox.get_vm_status(**t_args)

                elif t_name == "list_available_isos":
                    print(f"   [System]: Scanning storage 'local' for ISOs...")
                    isos = proxmox.list_isos(**t_args)
                    result = f"Available ISOs: {', '.join(isos)}" if isos else "No ISOs found."

                elif t_name == "start_vm":
                    result = proxmox.start_vm(**t_args)

                elif t_name == "stop_vm":
                    result = proxmox.stop_vm(**t_args)

                elif t_name == "create_vm":
                    name = t_args.get('name')
                    ram = t_args.get('memory', 2048)
                    disk = t_args.get('disk_gb', 20)
                    iso = t_args.get('iso', 'None')
                    print(f"\n✨ VM PLANNING: {name} | {ram}MB | {disk}GB | ISO: {iso}")
                    conf = input("   Should I create this VM as configured? (y/n): ").lower()
                    result = proxmox.create_vm(**t_args) if conf == 'y' else "Aborted."

                elif t_name == "delete_vm":
                    vmid = t_args.get('vmid')
                    print(f"\n⚠️  DANGER: Really DELETE VM {vmid}?")
                    conf = input("   Confirm by typing 'yes': ").lower()
                    result = proxmox.delete_vm(**t_args) if conf == 'yes' else "Aborted."

                elif t_name == "add_vm_disk":
                    result = proxmox.add_vm_disk(**t_args)

                elif t_name == "create_snapshot":
                    result = proxmox.create_snapshot(**t_args)

                elif t_name == "rollback_snapshot":
                    conf = input(f"\n🛑 Confirm rollback to {t_args.get('snapname')} by typing 'rollback': ").lower()
                    result = proxmox.rollback_snapshot(**t_args) if conf == 'rollback' else "Aborted."

                elif t_name == "list_snapshots":
                    result = proxmox.list_snapshots(**t_args)

                elif t_name == "setup_cloudinit":
                    print(f"   [System]: Configuring Cloud-Init for user '{t_args.get('user')}'...")
                    result = proxmox.setup_cloudinit(**t_args)
                
                elif t_name == "add_cloudinit_drive":
                    result = proxmox.add_cloudinit_drive(**t_args)

                elif t_name == "set_vm_vlan":
                    print(f"   [System]: Setting VLAN {t_args.get('vlan')} for VM {t_args.get('vmid')}...")
                    result = proxmox.set_vm_vlan(**t_args)
                
                elif t_name == "mount_iso":
                    print(f"   [System]: Mounting ISO '{t_args.get('iso')}' into VM {t_args.get('vmid')}...")
                    result = proxmox.mount_iso(**t_args)

                elif t_name == "eject_iso":
                    print(f"   [System]: Ejecting ISO from VM {t_args.get('vmid')}...")
                    result = proxmox.eject_iso(**t_args)

                elif t_name == "get_vm_hardware":
                    print(f"   [System]: Loading hardware specifications for {t_args.get('vmid')}...")
                    result = proxmox.get_vm_hardware(**t_args)
                
                elif t_name == "get_node_status":
                    res = proxmox.get_node_resources(**t_args)
                    if res:
                        result = (f"Node Status ({res['node']}):\n"
                                  f"- Free RAM: {res['free_ram_mb']} MB (out of {res['total_ram_mb']} MB)\n"
                                  f"- CPU Load: {res['cpu_load_percent']}%")
                    else:
                        result = "Error retrieving node status."

                # --- New LXC Mapping Tools ---
                elif t_name == "list_lxcs":
                    print(f"   [System]: Listing LXC containers...")
                    result = str(proxmox.list_lxcs(**t_args))

                elif t_name == "list_lxc_templates":
                    print(f"   [System]: Scanning storage for LXC templates...")
                    templates = proxmox.list_lxc_templates(**t_args)
                    result = f"Available LXC templates: {', '.join(templates)}" if templates else "No templates found."

                elif t_name == "create_proxmox_lxc":
                    hostname = t_args.get('hostname')
                    template = t_args.get('ostemplate')
                    print(f"\n📦 LXC PLANNING: {hostname} | Template: {template}")
                    conf = input("   Should I create this container as configured? (y/n): ").lower()
                    result = proxmox.create_lxc(**t_args) if conf == 'y' else "Aborted."

                elif t_name == "manage_lxc_status":
                    action = t_args.get('action')
                    vmid = t_args.get('vmid')
                    print(f"   [System]: LXC {vmid} -> Action: {action}...")
                    result = proxmox.manage_lxc_power(**t_args)

                else:
                    result = f"Error: Tool '{t_name}' is not mapped."
                
                log.info(f"Tool result: {result}")
                brain.messages.append({'role': 'tool', 'content': result, 'name': t_name})
            
            # After executing the tools, ask the AI for the next step
            # (It can now see the tool results in its conversation history)
            response_msg = brain.get_final_response()
        # --- END TOOL CHAINING ---

        # Print the final text response (once no further tool calls are required)
        if response_msg and response_msg.content:
            print(f"\nBot: {response_msg.content}")
            brain.messages.append(response_msg)

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\n\nBot: Program interrupted by user. Goodbye!")
    except Exception as e:
        log.error(f"Unexpected error during startup: {e}")
        print(f"A critical error occurred: {e}")