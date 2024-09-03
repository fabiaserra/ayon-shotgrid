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

### 2. `FlowLauncher.desktop`

This `.desktop` file integrates the FlowLauncher with the Linux desktop environment, allowing it to handle URLs with the custom `flow-launcher` protocol. 

- **Key Features:**
  - Registers the `flow-launcher` protocol, so any URL starting with `flow-launcher://` will be handled by this application.
  - Defines actions for both normal and staging environments.
  - Specifies the AYON icon and executable paths.
  - Includes a fallback action (`TryExec`) to ensure compatibility.

- **Actions:**
  - **Standard Execution:** Runs the `flow_launcher.py` script when the `flow-launcher` protocol is triggered.
  - **Staging Environment:** Provides an alternative action to run the script in a staging environment.

## Installation

### 1. Copy the `.desktop` file

Place the `FlowLauncher.desktop` file in the appropriate directory to register the custom protocol with your desktop environment. This is typically `~/.local/share/applications/` for user-specific configurations or `/usr/share/applications/` for system-wide configuration.

```bash
cp FlowLauncher.desktop ~/.local/share/applications/
