# windows-setup

## Overview

Setup script for quickly setting up Windows installations for a more efficient work computer.

## Perquisites

Install winget from:

<https://learn.microsoft.com/en-us/windows/package-manager/winget/>

Install `python3.11`:

```shell
winget install Python.Python.3.11
```

Install Git:

```shell
winget install git.git
```

Make sure to have an SSH keypair:

```shell
ssh-keygen
```

Prepare setup:

```shell
mkdir %userprofile%/dev
cd %userprofile%/dev
git clone git@github.com:doronz88/windowssetup.git
cd windowssetup
python3.11 -m pip install -r requirements.txt
```

# Usage

```shell
# pass -a/--automated for doing everything without prompting (unless certain removals are required)
python3.11 install_windows.py everything
```