# ArduPilot Custom Firmware Builder - GSoC 2021 Project

## Summary

This is a website that generates a downloadable custom ArduPilot firmware, based on user selection.  
Website: https://custom.ardupilot.org  
Blog post: https://discuss.ardupilot.org/t/gsoc-2021-custom-firmware-builder/74946

## For developers

This website uses the Flask library. Flask must be installed before use.  
Directories: `ardupilot` must be within `base`, which must be in the same directory as `CustomBuild`.

### Directory structure
default directory structure is as follows
```
/home/<username>
-CustomBuild
-base
--ardupilot
```

Use `--basedir` to adjust the base directory, the default one is `base`.
It is expected that you have an environment where ArduPilot can be built. Otherwise, see [https://ardupilot.org/dev/docs/building-setup-linux.html](https://ardupilot.org/dev/docs/building-setup-linux.html)

### Install Flask
```
python3 -m pip install --user -U flask
```

### Running
To run:

```
./app.py
```

### For Apache web server on Ubuntu with WSGI

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
