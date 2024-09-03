# FlowLauncher

## Overview

The `FlowLauncher` is a custom tool designed to launch AYON applications based on a specific protocol URL scheme. This tool is particularly useful for integrating with Flow and automating workflows by launching the appropriate AYON applications directly from custom action menu items within Flow.

## Components

### 1. `flow_launcher.py`

This Python script is the core of the FlowLauncher functionality. It parses a custom protocol URL, extracts necessary parameters (such as project names and task IDs), and launches the corresponding AYON application.

- **Key Features:**
  - Parses URLs in the format of `flow-launcher://action_name?project_name=<project>&ids=<task_id>&other_param=value`.
  - Connects to Flow to retrieve task-specific information.
  - Uses AYON's API to find and launch the appropriate application version.
  - Supports launching applications with different contexts based on the action specified in the URL.

- **Execution Flow:**
  1. The script is triggered by a custom protocol URL, passed as an argument.
  2. It checks the validity of the URL and extracts the action, project name, and task IDs.
  3. The script queries Flow for task details.
  4. It then identifies the corresponding AYON application and launches it using the `AddonsManager`.

### 2. `flow_launcher.install_handler`

This file automates the registration of the FlowLauncher as the protocol handler for flow-launcher:// URLs across different desktop environments.

- **Key Features:**
  - Automates the installation and registration process for both GNOME and KDE desktop environments.
  - Registers the flow-launcher protocol, ensuring any URL starting with flow-launcher:// will be handled by this application.
  - Provides an option for a staging environment to run the script under different conditions.

- **Installation Steps:**
  - GNOME: Registers the FlowLauncher as a URL handler using gconftool-2.
  - KDE: Creates and installs the necessary protocol file in the appropriate KDE directory.
  - XDG/Chrome: Installs the FlowLauncher as a protocol handler using the XDG desktop file, making it available for applications like Chrome.

- **Actions:**
  - **Standard Execution:** Runs the `flow_launcher.py` script when the `flow-launcher` protocol is triggered.
  - **Staging Environment:** Provides an alternative action to run the script in a staging environment.

## Installation

### 1. Run the Installation Script

To register the FlowLauncher as the protocol handler for your desktop environment, execute the flow_launcher.install_handler script. This script automates the entire setup process.

```bash
./flow_launcher.install_handler
```

The script will handle the registration process for GNOME, KDE, and XDG environments, ensuring that FlowLauncher is properly integrated into your system.

## Coreweave integration

The file is currently being ran automatically when Coreweave boots up through the AYON Ansible role at https://gitlab.alkemy-x.com/coreweave/infrastructure/virtual-servers/virtserver-ansible/-/tree/master/roles/ayon?ref_type=heads
