#!/bin/bash
echo "---------- $0 start ----------"

# this script is run by the root user in the virtual machine

set -e
set -x

who=$(whoami)
echo "Initial setup of SITL-vagrant instance."
if [ $who != 'root' ]; then
    echo "SORRY, MUST RUN THIS SCRIPT AS ROOT, GIVING UP"
    exit 1
fi

VAGRANT_USER=ubuntu
if [ -e /home/vagrant ]; then
    # prefer vagrant user
    VAGRANT_USER=vagrant
fi
echo USING VAGRANT_USER:$VAGRANT_USER

cd /home/$VAGRANT_USER


# artful rootfs is 2GB without resize:
resize2fs /dev/sda1

apt-get update

apt-get install -y python3-pip

pip3 install flask

apt-get install -y apache2
apt-get install -y libapache2-mod-wsgi-py3 python-dev

CUSTOM_CONF="/etc/apache2/sites-available//CustomBuild.conf"
#cp /vagrant/CustomBuild.conf "$CUSTOM_CONF"
#perl -pe 's%/home/custom/CustomBuild%/vagrant%' -i "$CUSTOM_CONF"

sudo -H -u $VAGRANT_USER mkdir -p /home/vagrant/base/builds

# TODO: work out how to do custom certs here

cat >"$CUSTOM_CONF" <<EOF
<VirtualHost *:8888>
#       ServerName custom.ardupilot.org
			       
       WSGIDaemonProcess app threads=5

       WSGIScriptAlias / /vagrant/app.wsgi
       WSGIScriptAlias /generate /vagrant/app.wsgi
       <Directory /vagrant/>
       Options FollowSymLinks
       AllowOverride None
       Require all granted
       </Directory>

       Alias /builds /base/builds
       <Directory /base/>
       Options FollowSymLinks Indexes
       AllowOverride None
       Require all granted
       </Directory>

       ErrorLog \${APACHE_LOG_DIR}/error.log
       LogLevel warn
       CustomLog \${APACHE_LOG_DIR}/access.log combined
</VirtualHost>
EOF

# add the arm tools into the path for Apache:
cat >>/etc/apache2/envvars <<EOF
export PATH=/opt/gcc-arm-none-eabi-10-2020-q4-major/bin:\$PATH
EOF

cp /vagrant/app.wsgi /etc/apache2/sites-available/

a2ensite CustomBuild.conf
a2dissite 000-default

cat >>/etc/apache2/ports.conf <<EOF
Listen 8888
EOF

for PKG in empy future ; do
    pip install --upgrade $PKG
done

systemctl reload apache2

# apache isn't run as root, so can't run app as vagrant user.
USER=www-data
GROUP=www-data

# create and change permissions of /base - need to work out how to
# effectively pass in --basedir to the WSGI at some stage
for DIR in /base /base/builds /base/tmp; do
  mkdir $DIR
  chown $USER.$GROUP $DIR
  chmod 777 $DIR  # TODO: tidy permissions
done

cd /base
sudo -H -u $USER ln -s /home//vagrant/ardupilot /base/ardupilot

pushd /home/$VAGRANT_USER
if [ ! -e ardupilot ]; then
    sudo -H -u $VAGRANT_USER git clone --recursive https://github.com/ardupilot/ardupilot
fi

pushd ardupilot
sudo -u $VAGRANT_USER ./Tools/environment_install/install-prereqs-ubuntu.sh -y
popd

chown -R $USER.$GROUP ardupilot

popd

systemctl stop apache2 && systemctl start apache2


# enable permissive ptrace:
perl -pe 's/kernel.yama.ptrace_scope = ./kernel.yama.ptrace_scope = 0/' -i /etc/sysctl.d/10-ptrace.conf
echo 0 > /proc/sys/kernel/yama/ptrace_scope

# the 8888 here comes from Vagrantfile, it's a forwarded port
echo "Check web address: http://127.0.0.1:8888/"

# Now you can run
# vagrant ssh -c "screen -d -R"
echo "---------- $0 end ----------"

