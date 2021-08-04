# ArduPilot Custom Firmware Builder

## Summary

This is a website that generates a downloadable custom ArduPilot firmware, based on user selection.

## For developers

This website uses the flask library. The ardupilot directory must be in the same directory as the CustomBuild directory.

To run:

```
./app.py
```

For Apache web server:

Insert the CustomBuild directory location for DocumentRoot and Directory below.
Webpage: http://localhost:8080

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

To run server:

```
/usr/local/opt/httpd/bin/httpd -D FOREGROUND
```
