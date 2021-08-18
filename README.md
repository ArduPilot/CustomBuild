# ArduPilot Custom Firmware Builder - GSoC 2021 Project

## Summary

This is a website that generates a downloadable custom ArduPilot firmware, based on user selection.  
Website: https://custom.ardupilot.org

## For developers

This website uses the Flask library. Flask must be installed before use.  
Directories: `ardupilot` must be within `base`, which must be in the same directory as `CustomBuild`.

To run:

```
./app.py
```

### For Apache web server on Ubuntu with WSGI

* Install mod_wsgi for python 3:
```
sudo apt-get install libapache2-mod-wsgi-py3 python-dev
```
* In `app.wsgi`, specify the app directory (`.../CustomBuild/`).
* Copy the config file to `/etc/apache2/sites-available/` and specify the correct directory.
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
