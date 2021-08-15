# ArduPilot Custom Firmware Builder

## Summary

This is a website that generates a downloadable custom ArduPilot firmware, based on user selection.

## For developers

This website uses the flask library.

### Directory structure
The ardupilot directory must be in the same directory as the CustomBuild directory.


`╭─khancyr@pop-os ~/Workspace/ardupilot_custom_build
╰─$ tree -d -L 1
.
├── ardupilot
└── CustomBuild`

Use `--basedir` to adjust the base directory, the default one is `base`.
It is expected that you have an environement where ArduPilot can be built. Otherwise, see [https://ardupilot.org/dev/docs/building-setup-linux.html](https://ardupilot.org/dev/docs/building-setup-linux.html)

### Install Flask
```
python3 -m pip install --user -U flask
```

### Running
To run:

```
./app.py
```

### For Apache web server on Ubuntu with wsgi

* Install mod_wsgi for python 3:
```
sudo apt-get install libapache2-mod-wsgi-py3 python-dev
```
* In `app.wsgi`, specify the app directory (`.../CustomBuild/`).
* Copy the config file to `/etc/apache2/sites-available/` and specify the correct directory, user and group.
* Enable the file:
```
sudo a2ensite CustomBuild.conf
```
* Open `envvars`, and specify the user and group.
```
sudo vim /etc/apache/envvars
```
* To stop Apache:
```
sudo apache2ctl stop
```
* To start Apache:
```
sudo apache2ctl start
```
Webpage: 127.0.0.1/CustomBuild/

### Without wsgi

Insert the CustomBuild directory location for DocumentRoot and Directory below.
```
DocumentRoot "CustomBuild directory location"
<Directory CustomBuild directory location>
				Options Indexes FollowSymLinks MultiViews
				AllowOverride None
				Order allow,deny
				allow from all
Require all granted
</Directory>
```
To run the server:
```
/usr/local/opt/httpd/bin/httpd -D FOREGROUND
```
