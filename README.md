# uBlock Origin Falkon Port

A port of uBlock Origin for the Falkon browser as a Python plugin.

## Installation

### Prerequisites
- Falkon 26.04.2+
- `pyside6` package (`sudo pacman -S pyside6`)

### Install

```bash
# Copy the extension to the Falkon plugins directory
cp -r extension /usr/lib/qt6/plugins/falkon/ublock-origin
```

Or for a single user:
```bash
mkdir -p ~/.local/share/falkon/plugins
cp -r extension ~/.local/share/falkon/plugins/ublock-origin
```

### Activation

1. Open Falkon
2. Go to **Tools → Extensions**
3. Find **uBlock Origin** in the list
4. Check the box to enable it

**Note:** Python/QML plugins in Falkon do not auto-load at startup. They must be activated through the Extensions manager UI.

## Features

- Network request blocking using EasyList + EasyPrivacy filter lists
- Cosmetic filter (element hiding) injection via UserScripts
- Automatic filter list updates
- Persistent settings
- Context menu "Block element" support
- Per-tab URL interception

## Development

### Building a C++ Plugin

For better performance and auto-loading, a C++ Qt plugin can be built. Requirements:
- Falkon development headers
- Qt6 WebEngine
- CMake

### Project Structure

```
ublock-origin-falkon-port/
├── extension/
│   ├── __init__.py        # Python plugin entry point
│   ├── main.qml           # QML interface (future use)
│   └── metadata.desktop   # Falkon plugin descriptor
├── AGENTS.md              # Development guidelines
└── README.md
```
