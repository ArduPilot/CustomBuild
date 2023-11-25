# ArduPilot Custom Firmware Builder - GSoC 2021 Project

## Summary

This is a website that generates a downloadable custom ArduPilot firmware, based on user selection.
Website: https://custom.ardupilot.org
Blog post: https://discuss.ardupilot.org/t/gsoc-2021-custom-firmware-builder/74946

## How to build the server locally for testing

It is expected that you have an environment where ArduPilot can be built. Otherwise, see [https://ardupilot.org/dev/docs/building-setup-linux.html](https://ardupilot.org/dev/docs/building-setup-linux.html).

1. Fork and Clone the ArduPilot/CustomBuild repository

2. In the directory containing the CustomBuild repo just cloned, create a /base subdirectory and change to that directory.

3. Clone a fork of the ArduPilot/ardupilot repository.

### Detailed Instructions for Ubuntu

For example, here are the commands for Ubuntu.

If not already set up, [configure your Git username](https://git-scm.com/docs/git-config#Documentation/git-config.txt-credentialusername):
Substitute `your-github-account` with your Github username.
```
git config --global credential.username your-github-account
```

Next, clone the repositories:
```bash
git config credential.username your-github-account
cd ~
git clone git@github.com:$(git config credential.username)/CustomBuild.git
git clone --depth 1 git@github.com:$(git config credential.username)/ardupilot.git base/ardupilot
```

Finally, add the upstream ArduPilot to your remotes.
```bash
git -C base/ardupilot remote add upstream git@github.com:ardupilot/ardupilot.git
git -C base/ardupilot fetch --depth 1 upstream
```

### Directory structure

The default directory structure is as follows:
```
/home/<username>
-CustomBuild
-base
--ardupilot
```


### Install Dependencies

```bash
cd ~/CustomBuild
python3 -m pip install --user --upgrade --requirement requirements.txt
```

### Running

To run, in the CustomBuild directory execute the following command:

```bash
cd ~/CustomBuild
./app.py
```

Use `--basedir` to adjust the base directory. The default one is `base`.

Once running, you will be given a link to a local host port in which the interface is displayed for the build server. It can be run at this point. Output will NOT be accessible via the interface buttons for build directory. Builds are stored in the base/builds subdirectory

### For Apache web server on Ubuntu with WSGI
To create a full server with network access:

* Install mod_wsgi for python 3:
```bash
sudo apt-get install apache2 libapache2-mod-wsgi-py3 python3 python3-pip
```

* update /etc/apache2/envvars
1. set correct username and group (default is www-data)
2. add ```export PATH=/opt/gcc-arm-none-eabi-10-2020-q4-major/bin:$PATH``` to end of file (this is default location if you have followed the dev env setup instructions above)

* Copy the config file to `/etc/apache2/sites-available/` and specify the correct directory.

* Edit the file as necessary for your use case

* Enable the file:
```bash
sudo a2ensite CustomBuild.conf
```
* To restart Apache:
```bash
sudo apache2ctl graceful
```
* To stop Apache:
```bash
sudo apache2ctl stop
```
* To start Apache:
```bash
sudo apache2ctl start
```
Webpage: 127.0.0.1
