# gtkrufs - GTK Recently Used FS
Some GTK programs' file picker lack the option to quickly navigate to recently used directories even though GTK does store them in `recently-used.xbel`

**gtkrufs** (GTK Recently Used FS) aims to solve this issue by parsing `recently-used.xbel` and listing it as a virtual filesystem that symlinks to those directories.

This allows you to easily navigate to the directories you have interacted with recently in GTK-based programs by bookmarking the virtual filesystem root directory

## Requirements
- Python ≥ 3.10
- FUSE3 installed

## Setup
Clone the repository, install using `pipx` and register the systemd user service
```bash
git clone https://github.com/ozelentok/gtkrufs
cd gtkrufs
pipx install .

mkdir -p ~/.config/systemd/user
cp gtkrufs.service ~/.config/systemd/user/
systemctl --user daemon-reload
systemctl --user enable --now gtkrufs
```
- Recently used directories should now be listed under `/run/user/${UID}/grufs`

