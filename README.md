# ArduPilot Custom Firmware Builder

## Table of Contents
1. [Overview](#overview)
2. [Live Versions](#live-versions)
3. [Running Locally Using Docker](#running-locally-using-docker)
4. [Running Locally Without Docker on Ubuntu](#running-locally-without-docker-on-ubuntu)
5. [Directory Structure](#directory-structure)
6. [Acknowledgements](#acknowledgements)

## Overview
The ArduPilot Custom Firmware Builder is a web-based application designed to generate downloadable customized ArduPilot firmware, tailored to user specifications. This tool facilitates the customization and building of firmware by allowing users to select the options that best fit their needs, thus providing a streamlined interface for creating ArduPilot firmware.

## Live Versions
- **Stable Version:** The stable version of the ArduPilot Custom Firmware Builder can be accessed at [custom.ardupilot.org](https://custom.ardupilot.org).
- **Beta Version:** We maintain a beta version available at [custom-beta.ardupilot.org](https://custom-beta.ardupilot.org) where newly developed features are tested before they are rolled out in the stable version.

## Running Locally Using Docker
To minimize setup overhead and enhance ease of use, running this application in Docker containers is highly recommended. Follow the instructions below to run the application locally using Docker:

1. **Install Docker and Docker Compose:** Make sure Docker and Docker Compose are installed on your machine. For installation instructions, visit the [Docker website](https://docs.docker.com/engine/install).
   
2. **Clone the Repository:**
   ```bash
   git clone https://github.com/ardupilot/CustomBuild.git
   cd CustomBuild
   ```

3. **Configure Environment Variables:**
   Copy the `.env` file to the root of the cloned repository from `./examples/.env.sample` and configure the necessary parameters within it.

   ```bash
   cp ./examples/.env.sample .env
   ```

4. **Build and Start the Docker Containers:**
   - To build and start the application, run:
     ```bash
     sudo docker compose up --build
     ```
   - If you want to run the application with the last built image, simply execute:
     ```bash
     sudo docker compose up
     ```

   Use the `-d` flag to run the application in daemon mode:
   ```bash
   sudo docker compose up -d
   ```

   This starts Redis, the backend API, the builder, and the frontend. Only the frontend is published on the host; nginx serves the UI and proxies `/api` to the backend.

   **Note:** When starting the application for the first time, it takes some time to initialize the ArduPilot Git repositories at the backend. This process also involves populating the list of available versions and releases using the GitHub API, so please be patient.

5. **Access the Web Interface:** 
   The frontend binds to port 11080 on your host machine by default. Open your web browser and go to `http://localhost:11080` to interact with the web interface. To change the port, set the `WEB_PORT` environment variable in the `.env` file mentioned in the _Configure Environment Variables_ section.

6. **Stopping the Application:**
   To stop the application, you can use the following command:
   ```bash
   sudo docker compose down
   ```
   This will stop and remove the containers, but it will not delete any built images or volumes, preserving your data for future use.

## Running Locally Without Docker on Ubuntu
This setup is intended for **local development** only, not production. Ensure you have an environment capable of building ArduPilot. Refer to the [ArduPilot Environment Setup Guide](https://ardupilot.org/dev/docs/building-setup-linux.html) if necessary.

1. **Clone the Custom-Build Repository:**
   ```bash
   git clone https://github.com/ardupilot/CustomBuild.git
   cd CustomBuild
   ```
2. **Create and use a virtual environment:**
   ```bash
   python3 -m venv path/to/virtual/env
   source path/to/virtual/env/bin/activate
   ```

   If the python venv module is not installed, run:
   ```bash
   sudo apt install python3-venv
   ```

   To deactive the virtual environment, run:
   ```bash
   deactivate
   ```

3. **Install Dependencies:**
   ```bash
   pip install -r backend/requirements.txt -r builder/requirements.txt
   ```

   If pip is not installed, run:
   ```bash
   sudo apt install python3-pip
   ```

4. **Install and Run Redis:**
   Use your package manager to install Redis:
   ```bash
   sudo apt install redis-server
   ```
   Ensure the Redis server is running:
   ```bash
   sudo systemctl status redis-server
   ```

5. **Start the Backend and Frontend:**
   In one terminal, start the API (listens on port 8080 by default):
   ```bash
   python3 backend/main.py
   ```
   To use a different port, pass `--port` or set `BACKEND_PORT`. If you change it, update the Vite proxy target in `frontend/vite.config.ts` to match.

   In another terminal, start the UI:
   ```bash
   cd frontend
   npm install
   npm run dev
   ```

   The application will automatically set up the required base directory at `./base` upon first execution. You may customize this path by setting the `CBS_BASEDIR` environment variable.

6. **Access the Web Interface:**

   Open `http://localhost:5173` in your browser. Vite proxies `/api` requests to the backend, so you do not need nginx for local development.

## Directory Structure
The default directory structure is established as follows:
```
/home/<username>
└── CustomBuild
    ├── schemas
    │   └── config
    │       └── 0.0.1.json   (shared CustomBuild YAML schema)
    └── base
        ├── ardupilot            (used by the backend)
        ├── artifacts            (build bundles include custombuild.yaml)
        ├── configs
        |   └── remotes.json     (optional, see examples/remotes.json.sample)
        ├── secrets
        |   └── admin_token      (optional)
        ├── tmp
            └── ardupilot        (used by the builder component)
```
The build artifacts are organized under the `base/artifacts` subdirectory. Each completed build archive (`.tar.gz`) includes firmware binaries, `build.log`, `extra_hwdef.dat`, and a Builder-generated `custombuild.yaml` for rebuilding. Config schemas live under `schemas/config/` at the repo root (consumed by Builder, backend, and frontend).

## Acknowledgements
This project includes many valuable contributions made during the Google Summer of Code 2021. For more information, please see the [GSOC 2021 Blog Post](https://discuss.ardupilot.org/t/gsoc-2021-custom-firmware-builder/74946).
