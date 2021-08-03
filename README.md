# ArduPilot Custom Firmware Builder

## Summary

This is a website that generates a downloadable custom ArduPilot firmware, based on user selection.

## For developers

This website uses the flask library.

To run:

```
./app.py
```

For Apache web server http://localhost:8080 :

```
DocumentRoot "CustomBuild directory"
<Directory CustomBuild directory>
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
