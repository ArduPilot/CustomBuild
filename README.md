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

   **Note:** When starting the application for the first time, it takes some time to initialize the ArduPilot Git repositories at the backend. This process also involves populating the list of available versions and releases using the GitHub API, so please be patient.

5. **Access the Web Interface:** 
   The application binds to port 11080 on your host machine by default. Open your web browser and go to `http://localhost:11080` to interact with the web interface. To change the port, set the `WEB_PORT` environment variable in the .env file mentioned in the _Configure Environment Variables_ section.

6. **Stopping the Application:**
   To stop the application, you can use the following command:
   ```bash
   sudo docker compose down
   ```
   This will stop and remove the containers, but it will not delete any built images or volumes, preserving your data for future use.

## Running Locally Without Docker on Ubuntu
To run the ArduPilot Custom Firmware Builder locally without Docker, ensure you have an environment capable of building ArduPilot. Refer to the [ArduPilot Environment Setup Guide](https://ardupilot.org/dev/docs/building-setup-linux.html) if necessary.

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
   pip install -r web/requirements.txt -r builder/requirements.txt
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

5. **Execute the Application:**
   - For a development environment, run:
     ```bash
     ./web/app.py
     ```
   - For a production environment, use:
     ```bash
     gunicorn web.wsgi:application
     ```

    During the coding and testing phases, use the development environment to easily debug and make changes. When deploying the app for end users, use the production environment to ensure better performance, scalability, and security.

    The application will automatically set up the required base directory at `./base` upon first execution. You may customize this path by using the `--basedir` option with the above commands or by setting the `CBS_BASEDIR` environment variable.

6. **Access the Web Interface:**

   Once the application is running, you can access the interface in your web browser at http://localhost:5000 if running directly using app.py (development environment), or at http://localhost:8000 if using Gunicorn (production environment).
   
   To change the default port when running with app.py, modify the `app.run()` call in web/app.py file by passing `port=<expected-port>` as an argument. For Gunicorn, refer to the [commonly used arguments](https://docs.gunicorn.org/en/latest/run.html#commonly-used-arguments) section of the Gunicorn documentation to specify a different port.

## Directory Structure
The default directory structure is established as follows:
```
/home/<username>
└── CustomBuild
    └── base
        ├── ardupilot            (used by the web component)
        ├── artifacts
        ├── configs
        |   └── remotes.json     (auto-generated, see examples/remotes.json.sample)
        ├── secrets
        |   └── reload_token     (optional)
        ├── tmp
            └── ardupilot        (used by the builder component)
```
The build artifacts are organized under the `base/artifacts` subdirectory.

## Acknowledgements
This project includes many valuable contributions made during the Google Summer of Code 2021. For more information, please see the [GSOC 2021 Blog Post](https://discuss.ardupilot.org/t/gsoc-2021-custom-firmware-builder/74946).
