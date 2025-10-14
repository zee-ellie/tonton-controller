# 吨吨鼠Controller | TonTonController

<div align="center">

![Version](https://img.shields.io/badge/version-0.1.0--alpha-blue)
![Platform](https://img.shields.io/badge/platform-Windows-lightgrey)
![Python](https://img.shields.io/badge/python-3.12-green)
![License](https://img.shields.io/badge/license-MIT-orange)

**阴阳师全自动助理 | Onmyoji Automation Assistant**
</div>

---
### 📖 About

TonTonController is an automation tool for Onmyoji (阴阳师) that provides a graphical interface for managing and automating various in-game tasks. Built with Python and packaged as a standalone Windows executable.

### ✨ Features

- **🎮 Game Mode Automation**
  - Solo mode automation
  - Realm Raid (结界突破) automation

- **🖱️ Coordinate Tracker (For Debugging Purposes)**
  - Built-in coordinate finder tool
  - Window position tracking

- **⚙️ Configuration System**
  - User-friendly config.ini editing
  - Persistent settings storage
  - Client-specific configurations

- **🖥️ Graphical Interface**
  - Modern dark theme UI (Cyborg theme)
  - Real-time status monitoring
  - Easy-to-use controls

- **🎯 Window Management**
  - Target window selection
  - Multi-instance support
  - Window settings management

### 📋 System Requirements

- **OS:** Windows 10/11
- **Permissions:** Administrator rights required
- **Onmyoji Display:** 1152x679 (default, configurable)

### 🚀 Quick Start

#### For Users (Pre-built Executable)

1. Download the latest release from [Releases](https://github.com/zee-ellie/tonton-controller/releases)
2. Extract `TonTonController_vX.X.X-alpha.zip` to any folder
3. Run `TonTonController.exe`
4. On first launch, `config.ini` will be created automatically
5. Launch (Make Sure Onmyoji is already launched) and enjoy!

### 🖱️ Click Modes
#### Solo Mode
- Clicks all active Onmyoji instances at the same time.
- Client position does not matter as long as the clients are not minimized.
- New clients added will automatically be put into the list to click.

#### Realm Raid Mode
- Users can select a single client to run the realm raid mode, while performing other tasks in the other clients without interruption.
- This mode will automatically resize the client back to default for accurate pixel reading.
- Auto-stop feature upon completion (running out of tickets). 
