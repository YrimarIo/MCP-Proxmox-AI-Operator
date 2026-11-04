from ollama import Client
from utils.logger import log

class AIBrain:
    def __init__(self, host, model_name, system_prompt):
        self.client = Client(host=host)
        self.model = model_name
        self.messages = [{'role': 'system', 'content': system_prompt}]
        self.tools = [
            {
                'type': 'function',
                'function': {
                    'name': 'create_vm',
                    'description': 'Erstellt eine neue VM mit Festplatte, optionaler ISO und optionalem Cloud-Init Drive.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'name': {'type': 'string', 'description': 'Name der VM'},
                            'cores': {'type': 'integer', 'description': 'Anzahl CPU-Kerne'},
                            'memory': {'type': 'integer', 'description': 'RAM in MB'},
                            'disk_gb': {'type': 'integer', 'description': 'Größe der Boot-Platte in GB'},
                            'iso': {'type': 'string', 'description': 'Name der ISO-Datei (z.B. ubuntu.iso). ISOs liegen IMMER im Storage "local".'},
                            'use_cloudinit': {
                                'type': 'boolean', 
                                'description': 'Setze diesen Wert auf True, wenn die VM Cloud-Init unterstützen soll (z.B. für User/Passwort-Setups).'
                            },
                            'node': {'type': 'string'},
                            'storage': {'type': 'string', 'description': 'Ziel-Storage für die VM-Disk.'},
                            'vlan': {'type': 'integer', 'description': 'Optionaler VLAN-Tag für das Netzwerk.'}
                        },
                        'required': ['name', 'disk_gb'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'list_vms',
                    'description': 'Listet alle VMs auf.',
                    'parameters': {
                        'type': 'object',
                        'properties': {'node': {'type': 'string'}},
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'delete_vm',
                    'description': 'Löscht eine VM anhand ihrer ID.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'integer'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid'],
                    },
                },
            },  
            {
                'type': 'function',
                'function': {
                    'name': 'start_vm',
                    'description': 'Startet eine VM anhand ihrer ID.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'integer', 'description': 'Die ID der VM'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'stop_vm',
                    'description': 'Fährt eine VM sicher herunter (Shutdown).',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'integer', 'description': 'Die ID der VM'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'add_vm_disk',
                    'description': 'Fügt einer VM sofort eine neue Festplatte hinzu. Parameter: vmid, size_gb.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'integer'},
                            'size_gb': {'type': 'integer'},
                            'node': {'type': 'string'},
                            'storage': {'type': 'string'}
                        },
                        'required': ['vmid', 'size_gb'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'get_vm_status',
                    'description': 'Ruft die aktuelle CPU- und RAM-Auslastung sowie die Uptime einer VM ab.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'Die ID oder der Name der VM'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'list_available_isos',
                    'description': 'Listet alle auf dem Proxmox-Server verfügbaren ISO-Dateien auf.',
                    'parameters': {
                        'type': 'object',
                        'properties': {'storage': {'type': 'string', 'default': 'local'}},
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'get_vm_status',
                    'description': 'Ruft die aktuelle CPU- und RAM-Auslastung sowie die Uptime einer VM ab.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'Die ID oder der Name der VM'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'list_available_isos',
                    'description': 'Listet alle auf dem Proxmox-Server verfügbaren ISO-Dateien im Speicher "local" auf.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'storage': {'type': 'string', 'default': 'local'}
                        },
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'create_snapshot',
                    'description': 'Erstellt einen Sicherungspunkt (Snapshot) einer VM. Sinnvoll vor riskanten Updates oder Änderungen.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'Die ID oder der Name der VM'},
                            'snapname': {'type': 'string', 'description': 'Ein kurzes Wort als Name (z.B. "vor_update")'},
                            'description': {'type': 'string', 'description': 'Längere Beschreibung, was gesichert wird'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid', 'snapname'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'rollback_snapshot',
                    'description': 'Setzt eine VM auf einen existierenden Snapshot zurück. ACHTUNG: Alle Daten nach dem Snapshot gehen verloren!',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'ID oder Name der VM'},
                            'snapname': {'type': 'string', 'description': 'Name des Snapshots, auf den zurückgesetzt werden soll'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid', 'snapname'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'list_snapshots',
                    'description': 'Listet alle verfügbaren Snapshots einer bestimmten VM auf.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'ID oder Name der VM'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'setup_cloudinit',
                    'description': 'Richtet User, Passwort und SSH-Keys für eine VM via Cloud-Init ein.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'ID oder Name der VM'},
                            'user': {'type': 'string', 'description': 'Benutzername (z.B. admin)'},
                            'password': {'type': 'string', 'description': 'Passwort für den User'},
                            'ssh_key': {'type': 'string', 'description': 'Öffentlicher SSH-Key'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid', 'user'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'add_cloudinit_drive',
                    'description': 'Fügt einer VM das benötigte Cloud-Init Laufwerk hinzu, falls dieses fehlt.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'ID oder Name der VM'},
                            'storage': {'type': 'string'}
                        },
                        'required': ['vmid'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'set_vm_vlan',
                    'description': 'Ändert den VLAN-Tag eines Netzwerk-Interfaces einer bestehenden VM.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'ID oder Name der VM'},
                            'vlan': {'type': 'integer', 'description': 'VLAN-ID (Tag)'},
                            'interface': {'type': 'string', 'default': 'net0'}
                        },
                        'required': ['vmid', 'vlan'],
                    },
                },
            },

            {
                'type': 'function',
                'function': {
                    'name': 'mount_iso',
                    'description': 'Legt eine ISO-Datei in das virtuelle CD-Laufwerk einer existierenden VM ein.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'ID oder Name der VM'},
                            'iso': {'type': 'string', 'description': 'Name der ISO (z.B. ubuntu)'}
                        },
                        'required': ['vmid', 'iso'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'eject_iso',
                    'description': 'Leert das virtuelle CD-Laufwerk einer VM (ISO auswerfen).',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'ID oder Name der VM'}
                        },
                        'required': ['vmid'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'get_vm_hardware',
                    'description': 'Liest die detaillierte Hardware-Konfiguration (CPU, RAM, Disks, Netz) einer VM aus.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'string', 'description': 'ID oder Name der VM'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'get_node_status',
                    'description': 'Prüft die aktuelle Auslastung des physischen Proxmox-Nodes (RAM/CPU).',
                    'parameters': {
                        'type': 'object',
                        'properties': {'node': {'type': 'string'}},
                    },
                },
            },
            
            
            # --- LXC (Container) Tools ---
            {
                'type': 'function',
                'function': {
                    'name': 'list_lxcs',
                    'description': 'Listet alle vorhandenen LXC Container auf einem Proxmox-Node auf.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'node': {'type': 'string', 'description': 'Optional: Name des spezifischen Nodes.'}
                        },
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'list_lxc_templates',
                    'description': 'Listet verfügbare LXC-Templates (z.B. Ubuntu, Debian) im Speicher "local" auf.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'storage': {'type': 'string', 'default': 'local', 'description': 'Speicherort der Templates.'},
                            'node': {'type': 'string'}
                        },
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'create_proxmox_lxc',
                    'description': 'Erstellt einen neuen LXC Container basierend auf einem Template.',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'hostname': {'type': 'string', 'description': 'Name/Hostname des neuen Containers.'},
                            'ostemplate': {'type': 'string', 'description': 'Vollständiger Name des Templates (z.B. local:vztmpl/ubuntu-22.04...).'},
                            'memory': {'type': 'integer', 'description': 'RAM in MB (Standard: 512).'},
                            'cores': {'type': 'integer', 'description': 'Anzahl der CPU Kerne.'},
                            'disk_gb': {'type': 'integer', 'description': 'Größe des Root-Dateisystems in GB.'},
                            'password': {'type': 'string', 'description': 'Initiales Root-Passwort.'},
                            'node': {'type': 'string'}
                        },
                        'required': ['hostname', 'ostemplate'],
                    },
                },
            },
            {
                'type': 'function',
                'function': {
                    'name': 'manage_lxc_status',
                    'description': 'Steuert den Status eines LXC (start, stop, shutdown).',
                    'parameters': {
                        'type': 'object',
                        'properties': {
                            'vmid': {'type': 'integer', 'description': 'Die ID des Containers.'},
                            'action': {'type': 'string', 'description': 'Aktion: start, stop oder shutdown.'},
                            'node': {'type': 'string'}
                        },
                        'required': ['vmid', 'action'],
                    },
                },
            },

        ]

    # JETZT RICHTIG EINGERÜCKT:
    def chat(self, user_input):
        """Nimmt die Benutzereingabe entgegen und fragt Ollama nach einer Aktion."""
        self.messages.append({'role': 'user', 'content': user_input})
        
        try:
            response = self.client.chat(
                model=self.model, 
                messages=self.messages, 
                tools=self.tools
            )
            return response.message
        except Exception as e:
            log.error(f"Fehler bei Ollama-Anfrage: {e}")
            return None

    def get_final_response(self):
        """Erlaubt der KI, basierend auf Tool-Ergebnissen weitere Tools zu rufen."""
        try:
            # WICHTIG: Hier müssen die 'tools' wieder mit rein!
            response = self.client.chat(
                model=self.model, 
                messages=self.messages, 
                tools=self.tools
            )
            return response.message
        except Exception as e:
            log.error(f"Fehler bei Folge-Antwort: {e}")
            return None