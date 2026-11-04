import os
from proxmoxer import ProxmoxAPI
import urllib3
from utils.logger import log

# Deaktiviert SSL-Warnungen für selbstsignierte Zertifikate
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)

class ProxmoxManager:
    def __init__(self, host, user, token_name, token_value):
        try:
            self.api = ProxmoxAPI(host, user=user, token_name=token_name, 
                                  token_value=token_value, verify_ssl=False)
            self.default_node = self._discover_node()
            self.default_storage = self._discover_storage(self.default_node)
            
            # Fester Speicherort für ISO-Dateien
            self.iso_storage = "local"
            
            log.info(f"Proxmox verbunden. Node: {self.default_node}, Disk-Storage: {self.default_storage}, ISO-Storage: {self.iso_storage}")
        except Exception as e:
            log.error(f"Kritischer Fehler bei der Proxmox-Verbindung: {e}")
            raise

    def _discover_node(self):
        """Findet den ersten verfügbaren Online-Node."""
        try:
            nodes = self.api.nodes.get()
            return next((n['node'] for n in nodes if n['status'] == 'online'), "pve")
        except:
            return "pve"

    def _discover_storage(self, node):
        """Findet den Standard-Storage für VM-Images."""
        try:
            storages = self.api.nodes(node).storage.get()
            # Bevorzugt Storage, der 'images' (VM-Platten) erlaubt
            return next((s['storage'] for s in storages if 'images' in s.get('content', '')), "local")
        except:
            return "local"

    # --- HILFSFUNKTIONEN ---

    def validate_node(self, node_name):
        """Prüft Node-Existenz oder gibt Standard zurück."""
        if not node_name:
            return self.default_node
        try:
            nodes = [n['node'] for n in self.api.nodes.get()]
            return node_name if node_name in nodes else self.default_node
        except:
            return self.default_node

    def get_vmid_by_name(self, name, node=None):
        """Sucht die VM-ID basierend auf dem Namen."""
        target_node = self.validate_node(node)
        try:
            vms = self.api.nodes(target_node).qemu.get()
            for vm in vms:
                if vm.get('name', '').lower() == name.lower():
                    return int(vm['vmid'])
        except:
            pass
        return None

    # --- HAUPTFUNKTIONEN (TOOLS) ---

    def list_vms(self, node=None):
        target = self.validate_node(node)
        try:
            vms = self.api.nodes(target).qemu.get()
            if not vms:
                return f"Keine VMs auf {target} gefunden."
            lines = [f"- {v.get('name', 'N/A')} (ID: {v['vmid']}, Status: {v['status']})" for v in vms]
            return f"VMs auf {target}:\n" + "\n".join(lines)
        except Exception as e:
            return f"Fehler beim Auflisten: {str(e)}"

    def create_vm(self, name, cores=1, memory=2048, disk_gb=20, iso=None, node=None, storage=None, use_cloudinit=False, vlan=None):
        """Erstellt eine VM mit Festplatte, optionaler ISO und optionalem Cloud-Init Drive."""
        target_node = self.validate_node(node)
        target_disk_storage = storage or self.default_storage

        is_safe, message = self.check_ram_safety(memory, target_node)
        if not is_safe:
            log.warning(f"VM Erstellung abgelehnt: {message}")
            return f"Fehler: {message}"
        
        best_match = None
        final_iso_path = None
        
        # 1. ISO-Suche (Intelligente Korrektur)
        if iso:
            best_match = self.find_best_iso(iso, storage=self.iso_storage, node=target_node)
            if best_match:
                final_iso_path = f"{self.iso_storage}:iso/{best_match}"
                log.info(f"ISO-Korrektur: Nutze {final_iso_path}")
            else:
                return f"Fehler: Keine passende ISO für '{iso}' im Storage '{self.iso_storage}' gefunden."

        try:
            # 2. Nächste freie VM-ID holen
            vmid = self.api.cluster.nextid.get()
            net_string = "virtio,bridge=vmbr0"
            if vlan:
                # Fügt den VLAN-Tag hinzu, falls einer angegeben wurde
                net_string += f",tag={vlan}"
                log.info(f"VLAN-Tag {vlan} wird für VM {vmid} konfiguriert.")
            
            # 3. Basis-Parameter zusammenstellen
            params = {
                'vmid': vmid,
                'name': name,
                'cores': cores,
                'memory': memory,
                'net0': net_string,
                'scsi0': f"{target_disk_storage}:{disk_gb}",
                'scsihw': 'virtio-scsi-pci',
                'boot': 'order=scsi0;ide2'
            }

            # 4. ISO einlegen falls vorhanden
            if final_iso_path:
                params['ide2'] = f"{final_iso_path},media=cdrom"
                
            # 5. Cloud-Init Drive hinzufügen falls gewünscht
            if use_cloudinit:
                # Nutzt den Disk-Storage auch für das Cloud-Init Drive
                params['ide3'] = f"{target_disk_storage}:cloudinit"
                log.info(f"Cloud-Init Drive (ide3) wird für VM {vmid} erstellt.")
            
            # 6. VM auf Proxmox erstellen
            self.api.nodes(target_node).qemu.create(**params)
            
            return (f"Erfolg: VM '{name}' (ID: {vmid}) auf Node '{target_node}' erstellt.\n"
                    f"- Disk: {disk_gb}GB ({target_disk_storage})\n"
                    f"- ISO: {best_match if iso else 'Keine'}\n"
                    f"- Cloud-Init: {'Aktiviert (ide3)' if use_cloudinit else 'Deaktiviert'}")
                    
        except Exception as e:
            log.error(f"API Fehler beim Erstellen der VM {name}: {e}")
            return f"Fehler beim Erstellen der VM: {str(e)}"

    def delete_vm(self, vmid, node=None):
        target_node = self.validate_node(node)
        try:
            # Versuch die VM zu stoppen, falls sie läuft
            try:
                self.api.nodes(target_node).qemu(vmid).status.stop.post()
            except:
                pass
            
            self.api.nodes(target_node).qemu(vmid).delete()
            return f"Erfolg: VM {vmid} wurde von {target_node} entfernt."
        except Exception as e:
            return f"Fehler beim Löschen: {str(e)}"

    def start_vm(self, vmid, node=None):
        target_node = self.validate_node(node)
        try:
            self.api.nodes(target_node).qemu(vmid).status.start.post()
            return f"Erfolg: VM {vmid} auf {target_node} wird gestartet."
        except Exception as e:
            if "already running" in str(e).lower():
                return f"Info: VM {vmid} läuft bereits."
            return f"Fehler beim Starten: {str(e)}"

    def stop_vm(self, vmid, node=None):
        target_node = self.validate_node(node)
        try:
            self.api.nodes(target_node).qemu(vmid).status.stop.post()
            return f"Erfolg: Shutdown-Befehl an VM {vmid} gesendet."
        except Exception as e:
            if "not running" in str(e).lower():
                return f"Info: VM {vmid} ist bereits aus."
            return f"Fehler beim Stoppen: {str(e)}"

    def add_vm_disk(self, vmid, size_gb, node=None, storage=None):
        target_node = self.validate_node(node)
        target_storage = storage or self.default_storage
        
        try:
            config = self.api.nodes(target_node).qemu(vmid).config.get()
            slot = 0
            while f"scsi{slot}" in config:
                slot += 1
            
            self.api.nodes(target_node).qemu(vmid).config.post(**{f"scsi{slot}": f"{target_storage}:{size_gb}"})
            return f"Erfolg: {size_gb}GB Disk als 'scsi{slot}' zu VM {vmid} hinzugefügt."
        except Exception as e:
            return f"API Fehler: {str(e)}"

    def get_vm_status(self, vmid, node=None):
        """Liest die aktuelle CPU- und RAM-Auslastung einer VM aus."""
        target_node = self.validate_node(node)
        
        # Namens-Auflösung zu ID
        if isinstance(vmid, str) and not vmid.isdigit():
            actual_id = self.get_vmid_by_name(vmid, target_node)
            if not actual_id:
                return f"Fehler: VM '{vmid}' nicht gefunden."
            vmid = actual_id

        try:
            status = self.api.nodes(target_node).qemu(vmid).status.current.get()
            
            if status.get('status') == 'stopped':
                return f"Die VM {vmid} ({status.get('name', 'N/A')}) ist aktuell ausgeschaltet."

            cpu_usage = round(status.get('cpu', 0) * 100, 2)
            mem_used = round(status.get('mem', 0) / 1024 / 1024, 2)
            mem_total = round(status.get('maxmem', 0) / 1024 / 1024, 2)
            uptime_days = round(status.get('uptime', 0) / 86400, 1)

            return (f"Status VM {vmid} ({status.get('name')}):\n"
                    f"- CPU-Last: {cpu_usage}%\n"
                    f"- RAM: {mem_used}MB von {mem_total}MB verwendet\n"
                    f"- Uptime: {uptime_days} Tage")
        except Exception as e:
            return f"Fehler beim Abrufen des Status: {str(e)}"

    def list_isos(self, storage=None, node=None):
        """Listet verfügbare ISOs auf dem gewählten oder Standard-ISO-Storage."""
        target_node = self.validate_node(node)
        target_storage = storage or self.iso_storage
        try:
            content = self.api.nodes(target_node).storage(target_storage).content.get()
            return [os.path.basename(item['volid']) for item in content if item.get('content') == 'iso']
        except Exception as e:
            log.error(f"Fehler beim Scannen der ISOs auf {target_storage}: {e}")
            return []

    def find_best_iso(self, search_term, storage=None, node=None):
        """Findet die ISO per Teilstring-Suche."""
        if not search_term:
            return None
        
        target_storage = storage or self.iso_storage
        all_isos = self.list_isos(target_storage, node)
        search_term = search_term.lower().replace(".iso", "")
        
        for iso in all_isos:
            if search_term in iso.lower():
                log.info(f"ISO-Treffer gefunden: '{iso}' für Suche '{search_term}'")
                return iso
        return None


    def create_snapshot(self, vmid, snapname, description=None, node=None):
        """Creates a snapshot of a VM."""
        target_node = self.validate_node(node)
        
        if isinstance(vmid, str) and not vmid.isdigit():
            actual_id = self.get_vmid_by_name(vmid, target_node)
            if not actual_id:
                return f"Error: VM '{vmid}' not found."
            vmid = actual_id

        try:
            clean_snapname = "".join(c for c in snapname if c.isalnum())
            params = {'snapname': clean_snapname}
            if description:
                params['description'] = description
            
            self.api.nodes(target_node).qemu(vmid).snapshot.post(**params)
            log.info(f"Snapshot '{clean_snapname}' for VM {vmid} started.")
            return f"Success: Snapshot '{clean_snapname}' for VM {vmid} is being created on {target_node}."
        except Exception as e:
            return f"Error creating snapshot: {str(e)}"

    def rollback_snapshot(self, vmid, snapname, node=None):
        """Reverts a VM to a specific snapshot."""
        target_node = self.validate_node(node)
        
        if isinstance(vmid, str) and not vmid.isdigit():
            vmid = self.get_vmid_by_name(vmid, target_node)

        try:
            self.api.nodes(target_node).qemu(vmid).snapshot(snapname).rollback.post()
            log.info(f"Rollback to snapshot '{snapname}' for VM {vmid} started.")
            return f"Success: VM {vmid} is reverting to snapshot '{snapname}'."
        except Exception as e:
            return f"Error during rollback: {str(e)}"


    def list_snapshots(self, vmid, node=None):
        """Listet alle Snapshots einer VM auf."""
        target_node = self.validate_node(node)
        
        if isinstance(vmid, str) and not vmid.isdigit():
            vmid = self.get_vmid_by_name(vmid, target_node)
            if not vmid: return f"Fehler: VM '{vmid}' nicht gefunden."

        try:
            # API-Abfrage für Snapshots
            snapshots = self.api.nodes(target_node).qemu(vmid).snapshot.get()
            
            if not snapshots or len(snapshots) <= 1: # Der 'current' State zählt oft als Snapshot mit
                return f"Für VM {vmid} wurden keine Snapshots gefunden."

            # Wir filtern den 'current' Eintrag heraus und formatieren den Rest
            lines = []
            for s in snapshots:
                name = s.get('name')
                if name == 'current': continue
                
                desc = s.get('description', 'Keine Beschreibung')
                # Zeitstempel umrechnen (Proxmox liefert Unix-Zeit)
                import datetime
                time_str = datetime.datetime.fromtimestamp(s.get('snaptime', 0)).strftime('%d.%m.%Y %H:%M')
                
                lines.append(f"- {name} (Erstellt am: {time_str}, Info: {desc})")
            
            return f"Verfügbare Snapshots für VM {vmid}:\n" + "\n".join(lines)
        except Exception as e:
            return f"Fehler beim Abrufen der Snapshots: {str(e)}"

    def setup_cloudinit(self, vmid, user=None, password=None, ssh_key=None, node=None):
        """Konfiguriert Cloud-Init Parameter für eine VM."""
        target_node = self.validate_node(node)
        
        if isinstance(vmid, str) and not vmid.isdigit():
            vmid = self.get_vmid_by_name(vmid, target_node)

        try:
            params = {}
            if user: params['ciuser'] = user
            if password: params['cipassword'] = password
            if ssh_key: params['sshkeys'] = ssh_key # Muss URL-encoded oder ein String sein
            
            # IP auf DHCP setzen (Standard für Cloud-Init VMs)
            params['ipconfig0'] = "ip=dhcp"

            # API Call an den Config-Endpunkt
            self.api.nodes(target_node).qemu(vmid).config.post(**params)
            
            log.info(f"Cloud-Init für VM {vmid} konfiguriert (User: {user})")
            return f"Erfolg: Cloud-Init für VM {vmid} gesetzt. User: {user}, IP: DHCP."
        except Exception as e:
            return f"Fehler bei Cloud-Init Konfiguration: {str(e)}"

    def add_cloudinit_drive(self, vmid, storage=None, node=None):
        """Fügt einer VM ein Cloud-Init Drive hinzu."""
        target_node = self.validate_node(node)
        target_storage = storage or self.default_storage
        
        if isinstance(vmid, str) and not vmid.isdigit():
            vmid = self.get_vmid_by_name(vmid, target_node)

        try:
            # Wir nutzen meist ide3, da ide2 oft für die normale ISO belegt ist
            params = {
                'ide3': f"{target_storage}:cloudinit"
            }
            self.api.nodes(target_node).qemu(vmid).config.post(**params)
            log.info(f"Cloud-Init Drive für VM {vmid} auf {target_storage} erstellt.")
            return f"Erfolg: Cloud-Init Drive zu VM {vmid} hinzugefügt (Slot: ide3)."
        except Exception as e:
            return f"Fehler beim Hinzufügen des Cloud-Init Drives: {str(e)}"

    def set_vm_vlan(self, vmid, vlan, interface="net0", node=None):
        """Setzt oder ändert den VLAN-Tag eines Netzwerk-Interfaces."""
        target_node = self.validate_node(node)
        if isinstance(vmid, str) and not vmid.isdigit():
            vmid = self.get_vmid_by_name(vmid, target_node)

        try:
            # Aktuelle Config holen, um den Rest der Netzwerk-Einstellungen (MAC, Bridge) nicht zu löschen
            config = self.api.nodes(target_node).qemu(vmid).config.get()
            current_net = config.get(interface)
            
            if not current_net:
                return f"Fehler: Interface {interface} nicht an VM {vmid} gefunden."

            # Wir filtern einen alten Tag raus und setzen den neuen
            parts = current_net.split(',')
            new_parts = [p for p in parts if not p.startswith('tag=')]
            if vlan: # Nur hinzufügen, wenn ein VLAN-Tag gesetzt werden soll
                new_parts.append(f"tag={vlan}")
            
            new_net_string = ",".join(new_parts)
            self.api.nodes(target_node).qemu(vmid).config.post(**{interface: new_net_string})
            
            return f"Erfolg: VLAN {vlan} für {interface} an VM {vmid} konfiguriert."
        except Exception as e:
            return f"Fehler beim VLAN-Setup: {str(e)}"

    def mount_iso(self, vmid, iso, node=None):
        """Legt eine ISO-Datei in das CD-Laufwerk (ide2) einer VM ein."""
        target_node = self.validate_node(node)
        if isinstance(vmid, str) and not vmid.isdigit():
            vmid = self.get_vmid_by_name(vmid, target_node)

        # Suche nach der besten passenden ISO
        best_match = self.find_best_iso(iso, storage=self.iso_storage, node=target_node)
        if not best_match:
            return f"Fehler: Keine passende ISO für '{iso}' im Storage '{self.iso_storage}' gefunden."

        try:
            # ide2 ist bei Proxmox Standard für das CD-Laufwerk
            iso_path = f"{self.iso_storage}:iso/{best_match}"
            self.api.nodes(target_node).qemu(vmid).config.post(ide2=f"{iso_path},media=cdrom")
            
            log.info(f"ISO '{best_match}' in VM {vmid} eingelegt.")
            return f"Erfolg: ISO '{best_match}' wurde in VM {vmid} (ide2) eingelegt."
        except Exception as e:
            return f"Fehler beim Mounten der ISO: {str(e)}"

    def eject_iso(self, vmid, node=None):
        """Wirft die aktuelle ISO aus dem CD-Laufwerk aus."""
        target_node = self.validate_node(node)
        if isinstance(vmid, str) and not vmid.isdigit():
            vmid = self.get_vmid_by_name(vmid, target_node)

        try:
            # 'none' wirft das Medium aus
            self.api.nodes(target_node).qemu(vmid).config.post(ide2="none,media=cdrom")
            return f"Erfolg: Das CD-Laufwerk von VM {vmid} wurde geleert."
        except Exception as e:
            return f"Fehler beim Auswerfen der ISO: {str(e)}"


    def get_vm_hardware(self, vmid, node=None):
        """Liest die detaillierte Hardware-Konfiguration einer VM aus."""
        target_node = self.validate_node(node)
        if isinstance(vmid, str) and not vmid.isdigit():
            vmid = self.get_vmid_by_name(vmid, target_node)
            if not vmid: return f"Fehler: VM '{vmid}' nicht gefunden."

        try:
            config = self.api.nodes(target_node).qemu(vmid).config.get()
            
            # Basis-Daten
            name = config.get('name', 'Unbekannt')
            memory = config.get('memory', 'N/A')
            cores = config.get('cores', 'N/A')
            sockets = config.get('sockets', 1)
            
            hw_info = [f"--- Hardware-Details für {name} (ID: {vmid}) ---"]
            hw_info.append(f"🖥️  CPU: {cores} Kern(e) / {sockets} Socket(s)")
            hw_info.append(f"🧠  RAM: {memory} MB")
            
            # Dynamisches Auslesen von Disks und Netzwerk
            disks = []
            networks = []
            
            for key, value in config.items():
                # Suche nach Festplatten (scsi, virtio, ide, sata)
                if any(x in key for x in ['scsi', 'virtio', 'ide', 'sata']) and 'cdrom' not in str(value):
                    disks.append(f"   - {key}: {value}")
                # Suche nach Netzwerk-Interfaces
                elif key.startswith('net'):
                    networks.append(f"   - {key}: {value}")

            if disks:
                hw_info.append("\n💾  Festplatten:")
                hw_info.extend(disks)
            
            if networks:
                hw_info.append("\n🌐  Netzwerk:")
                hw_info.extend(networks)
            
            # Boot-Reihenfolge & ISO
            hw_info.append(f"\n📂  Boot-Order: {config.get('boot', 'N/A')}")
            if 'ide2' in config and 'cdrom' in config['ide2']:
                hw_info.append(f"💿  CD-Laufwerk: {config['ide2']}")

            return "\n".join(hw_info)
        except Exception as e:
            log.error(f"Fehler beim Hardware-Check für VM {vmid}: {e}")
            return f"Fehler: Details konnten nicht geladen werden: {str(e)}"

    def get_node_resources(self, node=None):
        """Liest die physischen Ressourcen (RAM/CPU) des Nodes aus."""
        target_node = self.validate_node(node)
        try:
            status = self.api.nodes(target_node).status.get()
            
            # RAM Werte in MB umrechnen
            memory = status.get('memory', {})
            total_ram = round(memory.get('total', 0) / 1024 / 1024, 2)
            used_ram = round(memory.get('used', 0) / 1024 / 1024, 2)
            free_ram = total_ram - used_ram
            
            # CPU Last
            cpu_usage = round(status.get('cpu', 0) * 100, 1)
            
            return {
                "total_ram_mb": total_ram,
                "used_ram_mb": used_ram,
                "free_ram_mb": free_ram,
                "cpu_load_percent": cpu_usage,
                "node": target_node
            }
        except Exception as e:
            log.error(f"Fehler beim Lesen der Node-Ressourcen: {e}")
            return None

    def check_ram_safety(self, requested_mb, node=None):
        """Prüft, ob genug RAM für eine neue VM/Änderung frei ist (mit 1GB Sicherheitsreserve)."""
        resources = self.get_node_resources(node)
        if not resources:
            return False, "Konnte Host-Status nicht prüfen."
        
        # Wir lassen immer 1024 MB Reserve für das Proxmox-System selbst
        safe_limit = resources['free_ram_mb'] - 1024
        
        if requested_mb > safe_limit:
            return False, f"Zu wenig RAM! Frei: {round(resources['free_ram_mb'])}MB, benötigt inkl. Reserve: {requested_mb + 1024}MB."
        
        return True, "RAM verfügbar."
    
    
    
    
    # --- LXC SPEZIFISCHE FUNKTIONEN ---

    def list_lxcs(self, node=None):
        """Listet alle LXC Container auf einem Node auf."""
        target = self.validate_node(node)
        try:
            lxcs = self.api.nodes(target).lxc.get()
            if not lxcs:
                return f"Keine LXC Container auf {target} gefunden."
            lines = [f"- {l.get('hostname', 'N/A')} (ID: {l['vmid']}, Status: {l['status']})" for l in lxcs]
            return f"LXC Container auf {target}:\n" + "\n".join(lines)
        except Exception as e:
            return f"Fehler beim Auflisten der LXCs: {str(e)}"

    def create_lxc(self, hostname, ostemplate, vmid=None, cores=1, memory=512, disk_gb=8, node=None, storage=None, password=None, network="name=eth0,bridge=vmbr0,ip=dhcp"):
        """Erstellt einen neuen LXC Container."""
        target_node = self.validate_node(node)
        target_storage = storage or self.default_storage
        vmid = vmid or self.api.cluster.nextid.get()
        
        # Pfad-Korrektur für Templates (Standard Proxmox Format)
        if ":" not in ostemplate:
            ostemplate = f"local:vztmpl/{ostemplate}"

        try:
            params = {
                'vmid': vmid,
                'hostname': hostname,
                'ostemplate': ostemplate,
                'cores': cores,
                'memory': memory,
                'rootfs': f"{target_storage}:{disk_gb}",
                'net0': network,
            }
            if password:
                params['password'] = password
            
            self.api.nodes(target_node).lxc.create(**params)
            return f"Erfolg: LXC '{hostname}' (ID: {vmid}) auf {target_node} wird erstellt (Template: {ostemplate})."
        except Exception as e:
            return f"Fehler bei LXC Erstellung: {str(e)}"

    def manage_lxc_power(self, vmid, action, node=None):
        """Steuert den Status eines LXC Containers (start, stop, shutdown)."""
        target_node = self.validate_node(node)
        try:
            if action == "start":
                self.api.nodes(target_node).lxc(vmid).status.start.post()
            elif action == "stop":
                self.api.nodes(target_node).lxc(vmid).status.stop.post()
            elif action == "shutdown":
                self.api.nodes(target_node).lxc(vmid).status.shutdown.post()
            return f"Erfolg: Aktion '{action}' an LXC {vmid} gesendet."
        except Exception as e:
            return f"Fehler bei LXC Power-Aktion: {str(e)}"

    def list_lxc_templates(self, storage="local", node=None):
        """Listet verfügbare LXC-Templates im vztmpl-Verzeichnis auf."""
        target_node = self.validate_node(node)
        try:
            content = self.api.nodes(target_node).storage(storage).content.get()
            return [os.path.basename(item['volid']) for item in content if item.get('content') == 'vztmpl']
        except Exception as e:
            return []