# ArduPilot Custom Firmware Builder - GSoC 2021 Project

## Summary

This is a website that generates a downloadable custom ArduPilot firmware, based on user selection.  
Website: https://custom.ardupilot.org  
Blog post: https://discuss.ardupilot.org/t/gsoc-2021-custom-firmware-builder/74946

## How to build the server locally for testing

It is expected that you have an environment where ArduPilot can be built. Otherwise, see [https://ardupilot.org/dev/docs/building-setup-linux.html](https://ardupilot.org/dev/docs/building-setup-linux.html).

1. Fork and Clone the ArduPilot/CustomBuild repository

2. In the directory containg the CustomBuild repo just cloned, create a /base subdirectory and change to that directory.

3. Clone a fork of the ArduPilot/ardupilot repository. The structure should appear similar to that below:


### Directory structure
default directory structure is as follows
```
/home/<username>
-CustomBuild
-base
--ardupilot
```
### Install Flask
```
python3 -m pip install --user -U flask
```
Use `--basedir` to adjust the base directory, the default one is `base`.

### Running
To run, in the CustomBuild directory execute the following command:

```
./app.py
```
Once running, you will be given a link to a local host port in which the interface is displayed for the build server. It can be run at this point. Output will NOT be accessible via the interface buttons for build directory. Builds are stored in the base/builds subdirectory

### For Apache web server on Ubuntu with WSGI
To create a full server with network access:

* Install mod_wsgi for python 3:
```
sudo apt-get install apache2 libapache2-mod-wsgi-py3 python3 python3-pip
```

* update /etc/apache2/envvars
1. set correct username and group (default is www-data)
2. add ```export PATH=/opt/gcc-arm-none-eabi-10-2020-q4-major/bin:$PATH``` to end of file (this is default location if you have followed the dev env setup instructions above)

* Copy the config file to `/etc/apache2/sites-available/` and specify the correct directory.

* Edit the file as necessary for your use case

* Enable the file:
```
sudo a2ensite CustomBuild.conf
```
* To restart Apache:
```
sudo apache2ctl graceful
```
* To stop Apache:
```
sudo apache2ctl stop
```
* To start Apache:
```
sudo apache2ctl start
```
Webpage: 127.0.0.1
