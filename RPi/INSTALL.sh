#!/bin/bash
# installation of modules needed by MySense.py
#
# $Id: INSTALL.sh,v 1.5 2019/01/10 11:31:11 teus Exp teus $
#

USER=${USER:-ios}
echo "You run this script as user $USER (preferrebly \"ios\" and install it from folder MySense).
You need to provide your password for root access.
Make sure this user is added at the sudoers list." 1>&2
#set -x

PATH=/sbin:/usr/sbin:/bin:/usr/bin:/usr/local/sbin:/usr/local/bin

declare -A HELP
declare -A DFLT
HELP[UPDATE]="Update will update the Pi OS and Debian packages One may skip this if done before."
DFLT[UPDATE]=N
function UPDATE() {
    /usr/bin/sudo apt-get update
    /usr/bin/sudo apt-get upgrade
    /usr/bin/sudo apt-get dist-upgrade
    /usr/bin/sudo apt-get autoremove
    # /usr/bin/sudo pip install --upgrade
}

# add a command to crontab of user executed at (re)boot
function AddCrontab() {
    local myUSER=${2:-root}
    local SUDO=''
    if [ -z "$1" ] ; then return 1 ; fi
    if [ "$myUSER" != "$USER" ] ; then SUDO=/usr/bin/sudo ; fi
    if ! $SUDO /usr/bin/crontab -u "$myUSER" -l 2>/dev/null | /bin/grep -q "^@reboot.*$1"
    then
        ($SUDO /usr/bin/crontab -u "$myUSER" -l 2>/dev/null ; echo "@reboot $1" ) | $SUDO /usr/bin/crontab -u "$myUSER" -
        echo "Added at (re)boot to execute $1 as $myUSER user."
    fi
    return $?
}

# function to install python modules via download from github.
function git_pip() {
    local PROJ=$1
    local PKG=$2
    local MOD=$1
    if [ -n "$3" ]
    then
        MOD=$3
    fi
    if [ ! -x /usr/bin/pip ]
    then
        if !  /usr/bin/sudo apt-get install python-pip
        then
            echo "Cannot install pip. Exiting." 1>&2
            exit 1
        fi
    fi
    if ! PIP_FORMAT=legacy /usr/bin/pip list 2>/dev/null | /bin/grep -q -i "^$MOD"
    then
        echo "Installing $MOD via pip"
        if [ -n "$2" ]
        then
            mkdir -p src
            /usr/bin/sudo /usr/bin/pip -q install -e "git+https://github.com/${PROJ}#egg=${PKG}"
            if [ -d src ]
            then
                /usr/bin/sudo /bin/chown -R $USER.$USER src/${PKG,,}
            fi
        else
            /usr/bin/sudo /usr/bin/pip -q install "$MOD"
        fi
    fi
    return $?
}

# check and install the package from apt, pip or github
function DEPENDS_ON() {
    case "${1^^}" in
    PYTHON|PIP)
        if ! git_pip "$2" $3 $4
        then
            echo "FAILURE: Unable to install $2 with pip." 1>&2
            return 1
        fi
    ;;
    APT)
        if [ ! -x /usr/bin/apt-get ]
        then
            echo "FATAL: need apt-get to install modules." 1>&2
            exit 1
        fi
        if ! /usr/bin/dpkg --get-selections | grep -q -i "$2"
        then
            echo "Installing $2 via apt"
            if ! /usr/bin/sudo /usr/bin/apt-get -y -q install "${2,,}"
            then
                echo "FAILURE: Unable to install $2 with apt-get" 1>&2
                return 1
            fi
        fi
    ;;
    GIT)
        if ! git_pip "$2" "$3" $4
        then
            echo "FAILURE: Unable to install $2 with pip in git modus." 1>&2
            return 1
        fi
    ;;
    *)
        echo UNKNOWN COMMAND "$1" 1>&2
        exit 1
    ;;
    esac
    return 0
}

INSTALLS=''
declare -A UNINSTALLS
PLUGINS=''

function ASK(){
    local ANS DF QRY="Do you want to install My ${1} and dependences?"
    if [ -z "${DFLT[${1}]}" ] ; then DFLT[${1}]=Y ; fi
    if [ "${DFLT[${1}]/N*/N}" = N  ] ; then DF="N|y" ; fi
    if [ "${DFLT[${1}]/Y*/Y}" = Y  ] ; then DF="Y|n" ; fi
    if [ -n "${HELP[${1}]}" ]
    then
        echo "    ${HELP[${1}]}" >/dev/stderr
    fi
    if [ "${DFLT[${1}]}" = none ] ; then return 0 ; fi
    if [ -n "$2" ] ; then QRY="$2" ; fi
    read -t 15 -p  "${QRY} [${DF}] " ANS
    DF=${DF/%??/}
    if [ -n "$ANS" ]
    then
        DF=$(echo "${ANS^^}" | sed 's/\(.\).*/\1/')
    fi
    if [ $DF = Y ] ; then return 0 ; else return 1 ; fi
}

function MYSENSE(){
    return $?
}

PLUGINS+=" MYSQL"
HELP[MYSQL]="MYSQL will install MySQL database client and Python modules."
function MYSQL(){
    DEPENDS_ON apt python-mysql.connector
    # mysql shell client command
    DEPENDS_ON  apt mysql-client
    # DEPENDS_ON apt mysql-navigator # GUI not really needed
    return $?
}

PLUGINS+=" DHT"
UNINSTALLS[DHT]+=' /usr/local/bin/set_gpio_perm.sh'
HELP[DHT]="Installation of DHT sensor libraries and general purpose IO use.
Please enable gpio via raspi-config command interfaces as root."
function DHT(){
    if [ ! -x /usr/local/bin/set_gpio_perm.sh ]
    then
        echo "Created the file /usr/local/bin/set_gio_perm.sh"
        /bin/cat >/tmp/perm.sh <<EOF
#!/bin/sh
chown root:gpio /dev/gpiomem
chmod g+rw /dev/gpiomem
EOF
        chmod +x /tmp/perm.sh
        /usr/bin/sudo mv /tmp/perm.sh /usr/local/bin/set_gpio_perm.sh
        /usr/bin/sudo chown root.root /usr/local/bin/set_gpio_perm.sh
        AddCrontab /usr/local/bin/set_gpio_perm.sh root
    fi

    local P
    for P in build-essential python-dev python-openssl python-rpi.gpio
    do
        DEPENDS_ON apt $P
    done
    if ! pip list | grep -q Adafruit-DHT
    then
        if ! wget -O Adafruit_Python_DHT-1.3.4.tar.gz https://github.com/adafruit/Adafruit_Python_DHT/archive/1.3.4.tar.gz
        then
            echo "Cannot find https://github.com/adafruit/Adafruit_Python_DHT/archive/1.3.4.tar.gz"
            return 1
        fi
        tar xpzf Adafruit_Python_DHT-1.3.4.tar.gz
        ( cd Adafruit_Python_DHT-1.3.4 ; sudo python setup.py install )
        # DEPENDS_ON pip adafruit/Adafruit_Python_DHT Adafruit_Python_DHT Adafruit-DHT
    fi
    return $?
}

PLUGINS+=" SHT31"
HELP[SHT31]="Installation of Sensirion SHT31 library script.
Please make sure I2C is activated: Use raspi-config command -> interfaces for this.
Use i2cdetect -y 1 and see if 044 is present"
function SHT31(){
    DEPENDS_ON pip adafruit/Adafruit_Python_GPIO.git Adafruit-GPIO
    #DEPENDS_ON pip https://github.com/ralf1070/Adafruit_Python_SHT31
    if ! pip list | grep -q Adafruit-SHT31
    then
        if git clone https://github.com/ralf1070/Adafruit_Python_SHT31
        then
            cd Adafruit_Python_SHT31
            sudo python setup.py install
            cd ..
            sudo rm -rf Adafruit_Python_SHT31
        else 
            echo "ERROR: Could not clone github.com/ralf1070/Adafruit_Python_SHT31" >/dev/stderr
            return 0
        fi
    fi
    return $?
}

PLUGINS+=" BME280"
HELP[BME280]="Installation of BME280 library and BME280 sleep/wakeup script.
Please make sure I2C is activated: Use raspi-config command -> interfaces for this."
function BME280() {
    DEPENDS_ON pip adafruit/Adafruit_Python_GPIO.git Adafruit-GPIO
    if [ ! -f ./Adafruit_Python_BME280.py ]
    then
        git clone https://github.com/adafruit/Adafruit_Python_BME280.git
        /bin/cp ./Adafruit_Python_BME280/Adafruit_BME280.py .
        /bin/cat >>Adafruit_BME280.py <<EOF

    # added by teus 2017-07-03 thanks to Thomas Telkamp
    # to avoid heating up the Bosch chip and so temp measurement raise
    def BME280_sleep(self):
        ''' put the Bosch chip in sleep modus '''
        self._device.write8(BME280_REGISTER_CONTROL,0x0)

    def BME280_wakeup(self):
        ''' wakeup the Bosch chip '''
        self._device.write8(BME280_REGISTER_CONTROL, 0x3F)

EOF
        /bin/rm -rf ./Adafruit_Python_BME280/
    fi
    return $?
}

INSTALLS+=" THREADING"
HELP[THREADING]="Using default multi threading for all input plugins (sensor modules)."
DFLT[THREADING]="none"
function THREADING(){
    #DEPENDS_ON pip threading
    return $?
}

PLUGINS+=" DYLOS"
HELP[DYLOS]="Using default serial python module"
DFLT[DYLOS]="none"
function DYLOS(){
    # DEPENDS_ON pip serial
    return $?
}

PLUGINS+=" GPS"
HELP[GPS]="Installing GPS Debian deamon and Python libraries via serial connection."
function GPS(){
    DEPENDS_ON apt gpsd         # GPS daemon service
    #DEPENDS_ON apt gps-client  # command line GPS client
    DEPENDS_ON apt python-gps   # python client module
    DEPENDS_ON pip gps3         # python gps client module
    return $?
}

# PLUGINS+=" GSPREAD"
HELP[GSPREAD]="Installing Google gspread connectivity. DEPRECATED"
DFLT[GSPRAED]=N
function GSPREAD(){
    echo Make sure you have the latest openssl version:
    echo See README.gspread and obtain Google credentials: https://console.developers.google.com/
    DEPENDS_ON pip oauth2client # auth2
    DEPENDS_ON pip gspread      # Google client module
    #   git clone https://github.com/burnash/gspread
    #   cd gspread; python setup.py install
    DEPENDS_ON  apt python-openssl
    return $?
}

PLUGINS+=" MQTTSUB"
HELP[MQTTSUB]="Installing Mosquitto (MQTT) subscriber (client) part. Usually not needed."
DFLT[MQTTSUB]=N
function MQTTSUB(){
    DEPENDS_ON pip paho-mqtt    # mosquitto client modules
    # DEPENDS_ON apt python-mosquitto
    return $?
}

PLUGINS+=" MQTTPUB"
HELP[MQTTPUB]="Installing Mosquitto (MQTT) publishing client to send measurements to MQTT server."
function MQTTPUB(){
    DEPENDS_ON pip paho-mqtt    # mosquitto client modules
    # DEPENDS_ON apt python-mosquitto
    return $?
}

PLUGINS+=" SDS011"
HELP[SDS011]="Installing Python dependences for Nova SDS011 PM (USB) sensor."
function SDS011(){
    DEPENDS_ON pip enum34
    return $?
}

PLUGINS+=" PMSN003"
HELP[PMSN003]="Installing Python dependences for Plantower PMS 5003 or 7003 USB sensor"
function PMSN003(){
    # DEPENDS_ON pip serial
    return $?
}

EXTRA+=" MQTT"
HELP[MQTT]="Installing Mosquitto server deamon or broker. Usually not needed."
DFLT[MQTT]=N
function MQTT(){
    echo "see README.mqtt for authentication provisions" >/dev/stderr
    #DEPENDS_ON apt mqtt
    DEPENDS_ON apt mosquitto
    return $?
}

EXTRA+=" AUTOSTART"
HELP[AUTOSTART]="Installing auto MySense startup at boot via MyStart.sh script."
UNINSTALLS[AUTOSTART]+=" MyStart.sh"
function AUTOSTART(){
    echo "Installing: auto MySense start on boot: MyStart.sh"
    WD=$(pwd | sed -e s@$HOME@@ -e 's/^//')
    cat >MyStart.sh <<EOF
#!/bin/bash
# if there is internet connectivity start MySense

LED=\${LED:-D6}
WD=\${DIR:-$WD}
D_ADDR=2017

if [ ! -d \$HOME/\$WD ] ; then exit 1 ; fi
if [ ! -f \$HOME/\$WD/MySense.conf -o ! -f \$HOME/\$WD/MySense.py ]
then
    echo -e "<clear>MySense ERROR\nnot properly installed" | /bin/nc -w 2 localhost \$D_ADDR
    exit 1
fi

CNT=0
if /usr/bin/awk '
    BEGIN { net = 0 ; host = 0 ; out = 0 ; }
    /^#/ { next ; }
    /^\[.*\]/ { if ( host  && out ) { net = 1 ; } ; host = 0 ; out = 0 ; }
    /(output|raw).*=.*[Tt][Rr][Uu][Ee]/ { out = 1 ; }
    /(hostname).*=/ { host = 1 ; }
    /(hostname).*=.*localhost/ { host = 0 ; }
    END {
        if ( host && out ) { net = 1 ; }
        if ( net ) { exit(1) ; }
    }
     ' \$HOME/\$WD/MySense.conf
then
    CNT=60
else
    while ! /bin/ping -q -w 2 -c 1 8.8.8.8 >/dev/null
    do  
        echo -e "<clear>No internet access\nfor \$CNT minutes" | /bin/nc -w 2 localhost \$D_ADDR
        CNT=\$((\$CNT+1))
        /usr/local/bin/MyLed.py --led \$LED --light ON
        sleep 1
        if [ \$CNT -gt 30 ] ; then break ; fi
        /usr/local/bin/MyLed.py --led \$LED --light OFF
        sleep 59
    done
fi
if [ \$CNT -gt 30 ]
then
    echo -e "<clear>STARTING up MySense\nin LOCAL modus\nWelcome to MySense" | /bin/nc -w 2 localhost \$D_ADDR
    /usr/local/bin/MyLed.py --led \$LED --light OFF
    LOCAL=--local
else
    echo -e "<clear>STARTING up MySense\nWelcome to MySense" | /bin/nc -w 2 localhost \$D_ADDR
    LOCAL=''
fi

cd \$HOME/\$WD
python \$HOME/\$WD/MySense.py \$LOCAL start
exit 0
EOF
    chmod +x MyStart.sh
    AddCrontab "$(pwd)/MyStart.sh" $USER
    /usr/bin/sudo /bin/chmod 4755 /bin/ping
}

EXTRA+=" DISPLAY"
HELP[DISPLAY]="Installing tiny Adafruit display support."
UNINSTALLS[DISPLAY]+=" /usr/local/bin/MyDisplayServer.py /usr/local/bin/MySSD1306_display.py"
DFLT[YB]=N
function DISPLAY(){
    # this needs to be tested
    echo "Installing Display service and plugin"
    DEPENDS_ON apt python-pil
    DEPENDS_ON pip Adafruit-GPIO
    DEPENDS_ON pip Adafruit-SSD1306
    # DEPENDS_ON pip Adafruit_BBIO
    DEPENDS_ON apt python-imaging
    DEPENDS_ON apt python-smbus
    local ANS=I2C
    local YB=''
    if ASK YB "Is Oled display a Yellow/Blue type of display?"
    then YB='-y'
    fi
    read -p "Please answer: SSD1306 display uses I2C or SPI bus? [I2C|SPI]: " ANS
    case X"$ANS" in
    XI2C|XSPI)
        ANS=$ANS
    ;;
    *)
        return 1
    ;;
    esac
    if [ "$ANS" = SPI ] && ! /bin/ls /dev/spi* 2>/dev/null | grep -q "spidev0.[01]"
    then
        echo "GPIO: Missing spidev: please use \"sudo rasp-config\" and enable SPI"
    fi
    local INS_DIR=$(pwd)
    if [ ! -f MyDisplayServer.py ]
    then
        echo "ERROR: cannot locate MyDisplayServer.py for display service/server"
        return 1
    fi
    sudo /bin/cp MyDisplayServer.py MySSD1306_display.py /usr/local/bin
    sudo /bin/chmod +x /usr/local/bin/{MyDisplayServer.py,MySSD1306_display.py}
    AddCrontab "/usr/local/bin/MyDisplayServer.py $YB -b $ANS start" $USER
    echo "Installed to activate ${ANS} display service on reboot."
    if ! /usr/bin/groups | grep -q ${ANS,,}
    then
        if ! /bin/grep "^${ANS,,}.*$USER" && ! /usr/sbin/useradd -G ${ANS,,} $USER
        then
            echo "Please add $USER or MYSense user to ${ANS,,} group: sudo nano /etc/group"
        else
            echo "Added $USER to ${ANS,,} group and to access ${ANS,,}"
        fi
    fi
    return $?
}

PLUGINS+=" INFLUX"
HELP[INFLUX]="Installing influx publishing and server support modules."
function INFLUX(){
    DEPENDS_ON pip influxdb
    DEPENDS_ON pip requests
    return $?
}

INSTALLS+=" GROVEPI"
HELP[GROVEPI]="Installing GrovePi+ shield support, needed for several types of sensors. Install this as user pi!"
# this will install the grovepi library
function GROVEPI(){
    DEPENDS_ON pip grovepi
    if PIP_FORMAT=legacy /usr/bin/pip list 2>/dev/null | /bin/grep -q grovepi ; then return ; fi
    echo "This will install Grove Pi shield dependencies. Can take 10 minutes."
    if [ "$USER" != pi ]
    then
        if [ ! -d /home/pi/Dexter ]
        then
            echo "Please install grovepi as user pi. And use the following command:"
            echo "curl -kL dexterindustries.com/update_grovepi | bash"
            echo "Please reboot and install the Grove shield"
            echo "Run sudo i2cdetect -y To see is GrovePi (44) is detected."
            echo "And proceed with INSTALL.sh"
            exit 1
        fi
        # user ios needs user access to gpio and i2c
        /usr/bin/sudo adduser $USER gpio
        /usr/bin/sudo adduser $USER i2c
    fi
    return
}

INSTALLS+=" USER"
HELP[USER]="Installing MySense main user (default ios) and needed IO permissions."
function USER(){
    local ANS=''
    if [ $(whoami) = ${USER} ]
    then
        echo "if not '${USER}' user owner of installation, provide new name or push <return" 1>&2
        read -p "new name: " -t 15 ANS
    fi
    if [ -z "$ANS" ] ; then return ; else USER=$ANS ;  fi
    if grep -q "$USER" /etc/passwd ; then return ; fi
    echo "Need to do this with root permissions."
    /usr/bin/sudo touch /dev/null
    echo "Adding user  $USER and password"
    /usr/bin/sudo adduser $USER 
    /usr/bin/sudo passwd $USER
    /usr/bin/sudo adduser $USER gpio
    /usr/bin/sudo adduser $USER i2c
    /usr/bin/sudo adduser $USER dialout
    if [ ! -f /etc/sudoers.d/020_${USER}-passwd ]
    then
        echo "$USER ALL=(ALL) PASSWD: ALL" >/tmp/US$$
        /usr/bin/sudo /bin/cp /tmp/US$$ /etc/sudoers.d/020_${USER}-passwd
        /bin/rm /tmp/US$$
        /usr/bin/sudo chmod 440 /etc/sudoers.d/020_${USER}-passwd
    fi
    /usr/bin/sudo update-rc.d ssh enable        # enable remote login
    /usr/bin/sudo service ssh restart
}

function RestoreOriginal() {
    local FILE ANS
    for FILE in $@
    do
    if [ -f "$FILE" ] || [ -d "$FILE" ]
    then
        if [ -f "$FILE.orig" ] || [ -d "$FILE.orig" ]
        then
            /usr/bin/sudo /bin/mv -f  "$FILE.orig" "$FILE"
	else
	    read -p "Want to keep $FILE? [Ny] " ANS
	    if [ -z "${ANS/[Nn]/}" ]
	    then
                if [ -f "$FILE" ]
                then
		    /usr/bin/sudo /bin/rm -f "$FILE"
                elif [ -d "$FILE" ]
                then
                    /usr/bin/sudo /bin/rm -rf "$FILE"
                fi
	    fi
	fi
    fi
    done
}

EXTRA+=' UNINSTALL'
function UNINSTALL() {
    for F in $UNINSTALLS
    do
	RestoreOriginal "$F"
    done
}

function KeepOriginal() {
    local FILE
    for FILE in $@
    do
    if [ -f $FILE ] && ! [ -f $FILE.orig ]
    then
        /usr/bin/sudo /bin/cp $FILE $FILE.orig
    elif [ -f $FILE ]
    then
        /usr/bin/sudo -b /bin/cp $FILE $FILE.bak
    fi
    done
}

WIFI=wlan0
LAN=eth0
# Debian has changed names for internet interfaces
function GetInterfaces(){
    if /sbin/ifconfig -a | /bin/grep -q '[ew][ln]x.*: flag'
    then
        WIFI=$(/sbin/ifconfig -a | /bin/grep 'wlx..*: flag' | /bin/sed 's/: .*//')
        LAN=$(/sbin/ifconfig -a | /bin/grep 'enx..*: flag' | /bin/sed 's/: .*//')
    else
        WIFI=$(/sbin/ifconfig -a | /bin/grep 'wlan.*: flag' | /bin/sed 's/: .*//')
        LAN=$(/sbin/ifconfig -a | /bin/grep 'eth..*: flag' | /bin/sed 's/: .*//')
    fi
    if [ -z "$WIFI" ] || [ -z "$LAN" ]
    then
        echo "WARNING: only ${WIFI:-no wifi} and ${LAN:-no lan} internet interface available. Correct it manualy e.g. in /etc/network/interfaces." >/dev/stderr
    fi
    WIFI=${WIFI:-wlan0}
    LAN=${LAN:-eth0}
}

EXTRA+=' WATCHDOG'
# setup a watchdog using the buildin hardware monitor
# the Pi may crash so use a watchdog
function WATCHDOG() {
    if !  /sbin/watchdog | grep -q bcm2708_wdog
    then
        /usr/bin/sudo /sbin/modprobe bcm2708_wdog
        if ! /bin/grep -q bcm2708_wdog /etc/rc.local
        then
            /usr/bin/sudo /bin/sh -c "echo '/sbin/modprobe bcm2708_wdog' >> /etc/rc.local"
        fi
    fi
    if [ ! -f /etc/init.d/watchdog ]
    then
        DEPENDS_ON apt watchdog chkconfig
        /usr/bin/sudo /bin/systemctl enable watchdog
        /etc/init.d/watchdog start
    fi
    if ! /bin/grep -q '^watchdog-device' /etc/watchdog.conf
    then
        /usr/bin/sudo /bin/sed -i '/^#watchdog-device/s/#//' /etc/watchdog.conf
    fi
}

#EXTRA+=' FIREWALL'
# setup a firewall
# allow only traffic from/to lo and gateway
function FIREWALL(){
    DEPENDS_ON apt iptables
    DEPENDS_ON apt iptables-persistent
    if [ ! -f /etc/iptables/rules.v4 ]
    then        # on reboot this will be activated
        cat >/tmp/FW$$ <<EOF
 :INPUT ACCEPT [0:0]
 :FORWARD ACCEPT [0:0]
 :OUTPUT ACCEPT [0:0]

# Allows all loopback (lo0) traffic and drop all traffic to 127/8 that doesn't use lo0
 -A INPUT -i lo -j ACCEPT
 -A INPUT ! -i lo -d 127.0.0.0/8 -j REJECT

# Accepts all established inbound connections
 -A INPUT -m state --state ESTABLISHED,RELATED -j ACCEPT

# Allows all outbound traffic
 # You could modify this to only allow certain traffic
 -A OUTPUT -j ACCEPT

# Allows SSH connections
 # The --dport number is the same as in /etc/ssh/sshd_config
 -A INPUT -p tcp -m state --state NEW --dport 22 -j ACCEPT

# log iptables denied calls (access via 'dmesg' command)
 -A INPUT -m limit --limit 5/min -j LOG --log-prefix "iptables denied: " --log-level 7

# Reject all other inbound - default deny unless explicitly allowed policy:
 -A INPUT -j REJECT
 -A FORWARD -j REJECT

# TO DO: Allow only traffic via gateway. This is tricky as gateway IP will change

COMMIT
EOF
        /usr/bin/sudo /bin/cp /tmp/FW$$ /etc/iptables/rules.v4
        /bin/rm -f /tmp/FW$$
    fi
}

INSTALLS+=" INTERNET"
HELP[INTERNET]="Installation of internet connectivity via LAN and/or WiFi.
If needed see /etc/network/interfaces for what has been configured."
UNINSTALLS[INTERNET]+=' /etc/network/if-post-up.d/wifi-gateway'
UNINSTALLS[INTERNET]+=' /etc/network/if-up.d/wifi-internet'
UNINSTALLS[INTERNET]+=' /etc/network/interfaces'
## wired line $LAN switch to wifi on reboot
# will bring up internet access via $LAN (high priority) or wifi $WIFI
function INTERNET() {
    GetInterfaces       # get names of internet devices
    KeepOriginal /etc/network/interfaces
    local WLAN=${1:-${WIFI:-wlan0}} INT=${2:-${LAN:-eth0}}
    #/etc/if-post-up.d/wifi-gateway  adjust routing tables
    /bin/cat >/tmp/EW$$ <<EOF
#!/bin/sh
if [ -z "\$1" ] || [ -z "\$2" ]
then
   exit 0
fi
INT=\$1
WLAN=\$2
sleep 5           # wait a little to establish dhcp routing
if echo "\$INT" | /bin/grep wlan
then
    if /sbin/route -n | /bin/grep -q -e '^0\.0\.0\.0.*'"\$INT"
    then
        /sbin/route del default dev "\$INT"
    fi
    exit 0
fi
if ! /sbin/route -n | /bin/grep -q -e '^0\.0\.0\.0.*'"\$WLAN"
then
    if /sbin/route -n | /bin/grep -q "\${WLAN}"
    then
        GW=\$(/sbin/route -n | /bin/sed -e '/^[A-Za-Z0]/d' -e /\${INT}/d -e '/^10\./d' -e 's/\.0[ \t].*//' | /usr/bin/head -1).1
        if [ -n "\$GW" ]
        then
            if /sbin/route -n | /bin/grep -q -e '^0\.0\.0\.0.*'"\$INT"
            then
                /sbin/route del default dev "\$INT"
            fi
            /sbin/route add default gw \${GW} dev "\$WLAN"
            exit \$?
        fi
    fi
else
    exit 0
fi
EOF
    /bin/chmod +x /tmp/EW$$
    /usr/bin/sudo /bin/mkdir -p /etc/network/if-post-up.d/
    /usr/bin/sudo /bin/cp /tmp/EW$$ /etc/network/if-post-up.d/wifi-gateway
    # /etc/network/if-up.d/wifi-internet bring the other down
    /bin/cat >/tmp/EW$$ <<EOF
#!/bin/sh
if [ -z "\$1" ] || [ -z "\$2" ]
then
    exit 0
fi
INT=\$1
ALT=\$2
if  echo "\${INT}" | /bin/grep -q eth    # give time for eth for dhcp exchange
then
   sleep 5
fi
if /bin/grep -q 'up' /sys/class/net/"\${INT}"/operstate
then
    if /sbin/ifconfig "\${INT}" | grep -q 'inet addr'
    then
        if ! /sbin/ifdown "\${ALT}"
        then
            /sbin/ip link set dev "\${ALT}" down
        fi
        if echo "\${ALT}" | /bin/grep -q  wlan ; then exit 0 ; fi
        exit 1
    fi
fi
exit 0
EOF
    /bin/chmod +x /tmp/EW$$
    /usr/bin/sudo /bin/cp /tmp/EW$$ /etc/network/if-up.d/wifi-internet
    /bin/cat >/tmp/EW$$ <<EOF
# interfaces(5) file used by ifup(8) and ifdown(8)

# Please note that this file is written to be used with dhcpcd
# For static IP, consult /etc/dhcpcd.conf and 'man dhcpcd.conf'

# Include files from /etc/network/interfaces.d:
source-directory /etc/network/interfaces.d

auto lo
iface lo inet loopback

allow-hotplug $INT
iface $INT inet dhcp
        pre-up /etc/network/if-up.d/wifi-internet $WLAN $WLAN
        post-up /etc/network/if-post-up.d/wifi-gateway $WLAN $WLAN

#auto $WLAN
allow-hotplug $WLAN
iface $WLAN inet dhcp
        pre-up /etc/network/if-up.d/wifi-internet $INT $WLAN
        post-up /etc/network/if-post-up.d/wifi-gateway $INT $WLAN
        wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

EOF
    /usr/bin/sudo /bin/cp /tmp/EW$$ /etc/network/interfaces
    /bin/rm -f /tmp/EW$$
}

# installs  network system admin web interface
INSTALLS+=" WEBMIN"
UNINSTALLS[WEBMIN]=" /etc/sudoers.d/webadmin /var/www/html /etc/raspap"
HELP[WEBMIN]="Installation of network system administration via web interface."
DFLT[WEBMIN]=Y
function WEBMIN() {
    DEPENDS_ON APT git
    DEPENDS_ON APT lighttpd
    if /bin/grep -q -P '(essie|heesy)' /etc/os-release
    then
        DEPENDS_ON APT php5-cgi
    else
        DEPENDS_ON APT php7.0-cgi
    fi
    if [ ! -x /usr/bin/php-cgi ]
    then # try again
        DEPENDS_ON APT php-cgi
    fi
    DEPENDS_ON APT hostapd
    DEPENDS_ON APT dnsmasq
    DEPENDS_ON APT vnstat
    /usr/bin/sudo lighttpd-enable-mod fastcgi-php
    /usr/bin/sudo systemctl restart lighttpd

    cat >/tmp/web$$ <<EOF
www-data ALL=(ALL) NOPASSWD:/sbin/ifdown wlan0
www-data ALL=(ALL) NOPASSWD:/sbin/ifup wlan0
www-data ALL=(ALL) NOPASSWD:/bin/cat /etc/wpa_supplicant/wpa_supplicant.conf
www-data ALL=(ALL) NOPASSWD:/bin/cp /tmp/wifidata /etc/wpa_supplicant/wpa_supplicant.conf
www-data ALL=(ALL) NOPASSWD:/sbin/wpa_cli scan_results
www-data ALL=(ALL) NOPASSWD:/sbin/wpa_cli scan
www-data ALL=(ALL) NOPASSWD:/sbin/wpa_cli reconfigure
www-data ALL=(ALL) NOPASSWD:/bin/cp /tmp/hostapddata /etc/hostapd/hostapd.conf
www-data ALL=(ALL) NOPASSWD:/etc/init.d/hostapd start
www-data ALL=(ALL) NOPASSWD:/etc/init.d/hostapd stop
www-data ALL=(ALL) NOPASSWD:/etc/init.d/dnsmasq start
www-data ALL=(ALL) NOPASSWD:/etc/init.d/dnsmasq stop
www-data ALL=(ALL) NOPASSWD:/bin/cp /tmp/dhcpddata /etc/dnsmasq.conf
www-data ALL=(ALL) NOPASSWD:/sbin/shutdown -h now
www-data ALL=(ALL) NOPASSWD:/sbin/reboot
www-data ALL=(ALL) NOPASSWD:/sbin/ip link set wlan0 down
www-data ALL=(ALL) NOPASSWD:/sbin/ip link set wlan0 up
www-data ALL=(ALL) NOPASSWD:/sbin/ip -s a f label wlan0
www-data ALL=(ALL) NOPASSWD:/bin/cp /etc/raspap/networking/dhcpcd.conf /etc/dhcpcd.conf
www-data ALL=(ALL) NOPASSWD:/etc/raspap/hostapd/enablelog.sh
www-data ALL=(ALL) NOPASSWD:/etc/raspap/hostapd/disablelog.sh
EOF

    /usr/bin/sudo /bin/chown root.root /tmp/web$$
    /usr/bin/sudo /bin/chmod 440 /tmp/web$$
    /usr/bin/sudo /bin/mv /tmp/web$$ /etc/sudoers.d/webadmin
    if ! /usr/bin/sudo /bin/grep -q '#includedir' /etc/sudoers
    then
        /usr/bin/sudo /bin/cat /etc/sudoers >/tmp/web$$
        echo "#includedir /etc/sudoers.d" >>/tmp/web$$
	/usr/bin/sudo /bin/chmod +w /etc/sudoers
        /usr/bin/sudo /bin/mv /tmp/web$$ /etc/sudoers
        /usr/bin/sudo /bin/chmod 440 /etc/sudoers
    fi
    local WWW
    if [ -d /var/www/html ]
    then
        WWW=/var/www/html
    else
        WWW=/var/www
    fi
    if [ ! -d $WWW.orig ]
    then
	/usr/bin/sudo /bin/mv $WWW $WWW.orig
	/usr/bin/sudo /bin/mkdir $WWW
    else
	/usr/bin/sudo /bin/rm -rf $WWW/*
    fi
    /usr/bin/sudo git clone https://github.com/billz/raspap-webgui $WWW
    if [ "$WWW" = /var/www ]
    then
	/usr/bin/sudo /bin/ln -s . html
    fi
    /usr/bin/sudo /bin/chgrp -R www-data $WWW
    /usr/bin/sudo /bin/mkdir /etc/raspap
    /usr/bin/sudo /bin/mv $WWW/raspap.php /etc/raspap/
    /usr/bin/sudo /bin/chown -R www-data:www-data /etc/raspap
    /usr/bin/sudo /bin/sed -i 's/RaspAP/MySense/g' $WWW/index.php
    echo 'Default user/passwd for raspap WEBMIN: admin/secret' >/dev/stderr
    return 0
}

# installs full system admin web interface on port 10000
# remote system admin (default via ssh)
#EXTRA+=' WEBMIN2'
#HELP[WEBMIN2]="Installation of full system administration via web interface (port 10000). Usually not needed."
#DFLT[WEBMIN2]=N
function WEBMIN2(){
    local ANS
    # DEPENDS_ON APT perl
    DEPENDS_ON APT libnet-ssleay-perl
    # DEPENDS_ON APT openssl
    DEPENDS_ON APT libauthen-pam-perl
    # DEPENDS_ON APT libpam-runtime
    DEPENDS_ON APT libio-pty-perl
    DEPENDS_ON APT apt-show-versions
    # DEPENDS_ON APT python

    /usr/bin/wget -O /tmp/webmin_1.831_all.deb http://prdownloads.sourceforge.net/webadmin/webmin_1.831_all.deb
    echo "Installation can take more as 5 minutes." 1>&2
    /usr/bin/sudo dpkg --install /tmp/webmin_1.831_all.deb
    /bin/rm  -f /tmp/webmin_1.831_all.deb
    /usr/bin/wget -O /tmp/jcameron-key.as http://www.webmin.com/jcameron-key.asc
    /usr/bin/sudo /usr/bin/apt-key add /tmp/jcameron-key.asc
    /bin/rm -f /tmp/jcameron-key.asc
    /usr/bin/sudo /bin/sh -c "echo 'deb http://download.webmin.com/download/repository sarge contrib' >> /etc/apt/sources.list"
}

# backdoor via Weaved service: the service gives you a tunnel by name
# the weaved daemon will connect to Weaved to build a tunnel to Weaved.
# Reminder: everybody knowing the port from Weaved and have Pi user credentials
# can login into your Pi
EXTRA+=' WEAVED'
HELP[WEAVED]="Installation of backdoor for remote access via the Waeved service. You need an account with Remo3.it."
DFLT[WEAVED]=N
function WEAVED(){
    local ANS
    echo "This will install a backdoor via the webservice from Weaved (remote3.it)." 1>&2
    echo "You may first register (free try) and obatain user/passwd through https://weaved.com" 1>&2
    DEPENDS_ON APT weavedconnectd
    echo "
Run the next configuring command for Weaved.
Use main menu: 1) Attach/reinstall to connect the Pi and enter a device name e.g. MySense-ssh
Use protocol selection menu 1) for ssh and 4) for webmin (enter http and 10000)
" 1>&2
    read -t 20 -p "Configure it now? [Yn] " ANS
    if [ -z "${ANS/[nN]/}" ] ; then return ; fi
    /usr/bin/sudo /usr/bin/weavedinstaller
}

# backdoor via ssh tunneling.
EXTRA+=' SSH_TUNNEL'
HELP[SSH_TUNNEL]="Besides a virtual desktop one can install a backdoor via ssh tunneling. If so install this script to create the tunnel."
DFLT[SSH_TUNNEL]=N
function SSH_TUNNEL(){
    local ANS
    echo "You need to have imported an ssh key of you as user@your-desktop-machine."
    echo "If not do this now: login into your laptop and authorize eg ios/IPnr.
        if there is not ~/.ssh private and public key in this directory:
        ssh-keygen   # no password, less secure it saves the trouble on each ssh run
        ssh-copy-id ios@IPnrPi # copy of key for ssh no passwd access"
    cat >/tmp/SH$$ <<EOF
#!/bin/bash
# note the identity should be for Pi user root in /root/.ssh/!
ME=\${1:-me}            # <--- your local user name
IP=\${2:-my-laptop-IP}  # <--- your local IP number, must be a static number
# generate/copy key as root first!
if ! /bin/nc -w 1 -z \${IP} 22 ; then exit 1 ; fi     # is there connectivity?
if ! /bin/ps ax | /bin/grep "ssh -R 10000:" | grep -q \$ME # is tunnel alive?
then
    /usr/bin/ssh -R 10000:localhost:10000 "\${ME}@\${IP}" -nTN & # webmin
    echo "Watchdog restart tunnel to \${ME}@\${IP}:10000 for webmin"
fi
if ! /bin/ps ax | /bin/grep "ssh -R 10001:" | grep -q "\$ME" # is tunnel alive?
then
    /usr/bin/ssh -R 10001:localhost:22 "\${ME}@${IP}" -nTN &    # ssh
    echo "Watchdog restart tunnel to \${ME}@\${IP}:10001 for ssh"
fi
exit 0
EOF
    cmod +x /tmp/SH$$
    sudo cp /tmp/SH$$ /usr/local/bin/watch_my_tunnel.sh
    echo "Add the following line to the crontab, by issuing 'crontab -e'"
    echo "Change USER HOSTIP by your user id and destop/laptop static IP number"
    echo "*/10 10-23 * * * /usr/local/bin/watch_my_tunnel.sh USER IPnr"
    sleep 5
    crontab -e
}
    
INSTALLS+=" WIFI"
HELP[WIFI]="Installation of WiFi access to the Pi: wifi for internet connectivity, wifi access point on connectivity failures."
####### wifi $WIFI for wifi internet access, uap0 (virtual device) for wifi AP
# wlan1 for USB wifi dongle (use this if wifi $WIFI fails and need wifi AP)
function AddChckInternet(){
    if [ -f /etc/network/if-pre-up.d/Check-internet ]
    then
	sudo cat <<EOF | sudo tee /etc/network/if-pre-up.d/Check-internet
#!/bin/bash
INT="\${1:-$LAN}"
WLAN=\$2
EXIT=0
if [ -z "\$2" ] ; then exit 0 ; fi
if /sbin/route -n | /bin/grep -q -P '^0.0.0.0.*'"\${INT}"
then
    EXIT=1      # do not bring up \${WLAN:-$WIFI} if not needed
fi
exit \$EXIT
EOF
	sudo chmod +x /etc/network/if-pre-up.d/Check-internet
    fi
}

function WIFI(){
    GetInterfaces
    KeepOriginal /etc/network/interfaces
    local AP=${1:-uap0} ADDR=${2:-192.168.2}
    # make sure $WIFI is getting activated
    cat >/tmp/Int$$ <<EOF
# virtual wifi AP
auto ${AP}
iface ${AP} inet static
    address ${ADDR}.1
    netmask 255.255.255.0
    network 192.168.2.0                                                              
    broadcast 192.168.2.255                                                          
    gateway 192.168.2.1
EOF
    sudo cp /tmp/Int$$ /etc/network/interfaces.d/UAP
    AddChckInternet
    cat >/tmp/Int$$ <<EOF
# interfaces(5) file used by ifup(8) and ifdown(8)

# Please note that this file is written to be used with dhcpcd

# Include files from /etc/network/interfaces.d:
source-directory /etc/network/interfaces.d

auto lo
iface lo inet loopback

auto $LAN
iface $LAN inet dhcp

auto $WIFI
iface $WIFI inet dhcp
    pre-up /etc/network/if-pre-up.d/Check-internet $LAN $WIFI
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

allow-hotplug wlan1
iface wlan1 inet manual
    wpa-conf /etc/wpa_supplicant/wpa_supplicant.conf

source interfaces.d/UAP
EOF
    sudo cp /tmp/Int$$ /etc/network/interfaces
    rm -f /tmp/Int$$
    echo "If wired and wifi wireless fail you need wifi AP access." 1>&2
    read -t 15 -p "You want wifi Access Point installed? [Y|n] " ANS
    if [ -n "${ANS/[yY]/}" ] ; then return ; fi
    echo "Installing virtual wifi interface on $AP for wifi AP" 1>&2
    local NAT=YES
    WIFI_HOSTAP ${AP}              # give access if $LAN and $WIFI fail
    DNSMASQ "${AP}" ${ADDR}
    read -p "You want wifi AP clients to reach internet? [y,N] " ANS
    if [ -n "${ANS/[nN]/}" ] ; then NAT=NO ; fi
    VIRTUAL "${AP}" ${ADDR} ${NAT}
    # /usr/bin/sudo /usr/sbin/service dnsmasq restart
    # /usr/bin/sudo /usr/sbin/service hostapd restart
}

INSTALLS+=" LOGGING"
HELP[LOGGING]="Installation of loggin rotation script for /var/log/MySense/MySense.log."
UNINSTALLS[LOGGING]+=' /etc/logrotate.d/MySense /var/log/MySense'
# logging, may be different due to MySense.conf configuration
function LOGGING(){
    /bin/cat >/tmp/logging$$ <<EOF
/var/log/MySense/MySense.log {
        rotate 3
        daily
        compress
        size 100k
        nocreate
        missingok
        # postrotate
        #       /usr/bin/killall -HUP MySense
        # endscript
}
EOF
    # rotate the MySense logging file
    sudo cp /tmp/logging$$ /etc/logrotate.d/MySense
    rm /tmp/logging$$
    sudo mkdir /var/log/MySense
    sudo chown ${USER}.adm /var/log/MySense
    return 0
}

UNINSTALLS[DNSMASQ]+=' /etc/dnsmasq.conf'
# make dsnmasq ready to operatie on wifi Access Point
# activate it from elsewhere
function DNSMASQ() {
    local WLAN=${1:-uap0} ADDR=${2:-192.168.2}
    KeepOriginal /etc/dnsmasq.conf
    /usr/bin/sudo /usr/sbin/service isc-dhcp-server stop
    /usr/bin/sudo /bin/systemctl disable isc-dhcp-server
    DEPENDS_ON APT dnsmasq
    /usr/bin/sudo /usr/sbin/service dnsmasq stop
    /usr/bin/sudo /bin/systemctl disable dnsmasq
    # provide dhcp on wifi channel
    /bin/cat >/tmp/hostap$$ <<EOF
interface=${WLAN}
# access for max 4 computers, max 12h lease time
dhcp-range=${WLAN},${ADDR}.2,${ADDR}.5,255.255.255.0,12h
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/dnsmasq.conf
    /bin/rm -f /tmp/hostap$$
    # /usr/bin/sudo /usr/sbin/service dnsmasq restart
}

INSTALLS+=" NAT"
HELP[NAT]="Installation of network address translation for internetaccess via wifi to internet. Usually not needed."
DFLT[NAT]=N
# TO DO: add support for IPV6
function NAT(){
    GetInterfaces
    local WLAN={1:-uap0} INT=${2:-$LAN}
    if /bin/grep -q net.ipv4.ip_forward=1 /etc/sysctl.conf ; then return ; fi
    echo "Installing NAT and internet forwarding for wifi $WLAN to $INT" 1>&2
    /usr/bin/sudo /bin/sh -c "echo net.ipv4.ip_forward=1 >>/etc/sysctl.conf"
    /usr/bin/sudo /bin/sh -c "echo 1 > /proc/sys/net/ipv4/ip_forward"
    /usr/bin/sudo /sbin/iptables -t nat -A POSTROUTING -o ${INT} -j MASQUERADE
    /usr/bin/sudo /sbin/iptables -A FORWARD -i ${INT} -o ${WLAN} -m state --state RELATED,ESTABLISHED -j ACCEPT
    /usr/bin/sudo /sbin/iptables -A FORWARD -i ${WLAN} -o ${INT} -j ACCEPT
    /usr/bin/sudo /bin/sh -c "/sbin/iptables-save > /etc/firewall.conf"
    /bin/cat >/tmp/hostap$$ <<EOF
#!/bin/sh
    if /bin/grep -q 'up' /sys/class/net/${INT}/operstate
    then
        INT=${INT}
        /sbin/ip link set dev ${WLAN} down
    else
        INT=${WLAN}
    fi
    if /sbin/ifconfig | /bin/grep -q uap0
    then
        WLAN=${WLAN}
        /sbin/iptables -t nat -A POSTROUTING -o \${INT} -j MASQUERADE
        /sbin/iptables -A FORWARD -i \${INT} -o \${WLAN} -m state --state RELATED,ESTABLISHED -j ACCEPT
        /sbin/iptables -A FORWARD -i \${WLAN} -o \${INT} -j ACCEPT
    fi
EOF
    /usr/bin/sudo /bin/cp /tmp/hostap$$ /etc/network/if-up.d/iptables
    /usr/bin/sudo /bin/chmod +x /etc/network/if-up.d/iptables
    /bin/rm -f /tmp/hostap$$
}

UNINSTALLS[VIRTUAL]+=' /usr/local/etc/start_wifi_AP /etc/udev/rules.d/90-wireless.rules'
# this will start wifi Access Point if $LAN and $WIFI have no internet access
# the virtual uap0 wifi will be combined with $WIFI (embedded in Pi3)
function VIRTUAL(){
    local WLAN=${1:-uap0} ADDR=${2:-192.168.2} NAT=${3:-YES}
    if [ $NAT = YES ]
    then
        NAT="/sbin/sysctl net.ipv4.ip_forward=1
/sbin/iptables -t nat -A POSTROUTING -s ${ADDR}.0/24 ! -d ${ADDR}.0/24 -j MASQUERADE"
    else
        NAT=""
    fi
    if [ ! -f /etc/udev/rules.d/90-wireless.rules ]
    then
        cat >/tmp/rules.$$ <<EOF
action=="add", SUBSYSTEM=="ieee80211", KERNEL=="Phy0", RUN+="/bin/iw phy %k interface add uap0 type __ap"
EOF
        /usr/sbin/sudo /bin/mv /tmp/rules.$$ /etc/udev/rules.d/90-wireless.rules
    fi
    /bin/cat >/tmp/hostap$$ <<EOF
#!/bin/bash
# this will check wired, wifi if there is a connectivity
# then try wifi client
# if search for wifi connectivity or no internet led will blink
# it will initiate wifi AP to login locally
# if needed it will bring oled display server alive

BUS=I2C		# bus type of oled display
D_ADDR=2017	# port for oled display server
YB=\${YB}        # yellow/blue oled type of display
if [ -n "\$1" -a "\$1" = '-y' ]
then
    YB=-y
    shift
fi
if [ -n "\$1" ]
then
    UAP=uap0	# bring up wifi AP, empty if disabled
else
    UAP=\${UAP}
fi
if [ -n "\$DEBUG" ]
then
    QUIET=/dev/stderr
else
    QUIET=/dev/null
fi

# led ON
if [ -x /usr/local/bin/MyLed.py ]
then
    /usr/local/bin/MyLed.py --led D6 --light ON
fi
if [ -x /usr/local/bin/MyDisplayServer.py ]
then
    if ! /bin/ps ax | grep MyDisplayServer | grep -q -v grep
    then
        /usr/bin/sudo -u ios /usr/local/bin/MyDisplayServer.py \${YB} -b \$BUS start 2>\$QUIET
        /bin/sleep 2
    fi
fi

function INTERNET() {
    local WLAN=\${1:-wlan0}
    local ADDR=''
    sleep 15
    if /sbin/ifconfig \$WLAN | grep -q 'inet.*cast'
    then
        ADDR=\$(/sbin/ifconfig \$WLAN | /bin/sed s/addr:// | /usr/bin/awk '/inet.*cast/{printf("%s",\$2); }')
	/sbin/ifdown \$WLAN 2>\$QUIET
	/sbin/ifup \$WLAN 2>\$QUIET ; sleep 5 # make sure routing has been done
        if /sbin/route -n | grep -q '^0.0.0.0.*'\${WLAN}
        then
            if ! ping -q -W 2 -c 2 8.8.8.8 >\$QUIET
            then
                # no outside connectivity
                return 1
            fi
            # led OFF
            if [ -x /usr/local/bin/MyLed.py ]
            then
                /usr/local/bin/MyLed.py --led D6 --light OFF
            fi
            echo "\$WLAN \$ADDR" | /bin/nc -w 2 localhost \$D_ADDR
            return 0
        fi
    fi
    return 1
}

# install and enable WiFi Access Point as added device to wlan0
# needs udev rule set for psy0 wireless device
function WiFiAP() {
    # try wifi AP
    WLAN=\${1}
    ADDR=\${2}
    if [ -z "\$WLAN" ] ; then return 1 ; fi
    if ! /sbin/ifconfig -a | /bin/grep -q wlan0 # no WiFi device
    then
	return 1
    fi
    # led ON-OFF-OFF-OFF-ON ...
    if [ -x /usr/local/bin/MyLed.py ]
    then
        kill %1 2>\$QUIET
        /usr/local/bin/MyLed.py --led D6 --blink 1,5,30 &
    fi
    # echo 'setup WiFi AP' | /bin/nc -w 2 localhost \$D_ADDR
    # echo "\$WLAN \$ADDR.1" | /bin/nc -w 2 localhost \$D_ADDR
    /sbin/ifdown wlan0 2>\$QUIET
    if ! /sbin/ifconfig -a | /bin/grep -q \${WLAN:-uap0}
    then
        if ! /sbin/iw phy phy0 interface add "\${WLAN:-uap0}" type __ap 2>\$QUIET
        then
            /sbin/ifup wlan0 2>\$QUIET
	    kill %1 2>\$QUIET
	    return 1
        fi
    fi
    #/sbin/ip link set "\${WLAN}" address \$(ifconfig  | /bin/grep HWadd | /bin/sed -e 's/.*HWaddr //' -e 's/:[^:]*\$/:0f/')
    /sbin/ifup \${WLAN:-uap0} 2>\$QUIET >\$QUIET   # ignore already exists error
    /sbin/sysctl net.ipv4.ip_forward=1
    if [ -n "\$ADDR" ]
    then
        /sbin/iptables -t nat -A POSTROUTING -s \$ADDR.0/24 ! -d \$ADDR.0/24 -j MASQUERADE
        /bin/systemctl restart hostapd 2>\$QUIET
    fi
    /sbin/route del default dev uap0 2>\$QUIET
    /sbin/ifup wlan0 2>\$QUIET
    /bin/systemctl restart dnsmasq 2>\$QUIET
    kill %1 2>\$QUIET
    echo "WiFi AP enabled"  | /bin/nc -w 2 localhost \$D_ADDR
    /bin/grep -e 'ssid=...' -e wpa_passphrase= /etc/hostapd/hostapd.conf | /bin/sed 's/.*phrase=/phrase /' | /bin/nc -w 2 localhost \$D_ADDR
    if [ -x /usr/local/bin/MyLed.py ]
    then
        /usr/local/bin/MyLed.py --led D6 --light OFF
    fi
    sleep 5
    return 0
}

function WiFiClient() {
    # no connectivity. Start wifi AP
    if /sbin/ifconfig | /bin/grep -q uap0
    then
        /sbin/ip link set dev uap0 down
        /sbin/ifdown eth0
        /sbin/ifup wlan0
    fi
    SSIDS=(\$(/sbin/wpa_cli scan_results | /bin/grep WPS | /usr/bin/sort -r -k3 | /usr/bin/awk '{ print \$1;}'))
    # try WPS on all BSSID's
    echo "<clear>Try WiFi WPS on:" | /bin/nc -w 2 localhost \$D_ADDR
    if [ -x /usr/local/bin/MyLed.py ]
    then
        /usr/local/bin/MyLed.py --led D6 --blink 1,1,15 &
    fi
    for BSSID in \${SSIDS[@]}
    do
        # try associated: led OFF-ON-OFF-ON...
        SSID=\$(/sbin/wpa_cli scan_results | /bin/grep \$BSSID | awk  -F '\t' '{ print \$5; exit(0); }')
        echo "  \$SSID" | /bin/nc -w 2 localhost \$D_ADDR
        if /sbin/wpa_cli wps_pbc "\$BSSID" | /bin/grep -q CTRL-EVENT-CONNECTED
        then
            echo "CONNECTED" | /bin/nc -w 2 localhost \$D_ADDR
            if [ -x /usr/local/bin/MyLed.py ]
            then
                kill %1
            fi
	    # on success this process will die on next call
            if INTERNET
	    then
                return 0
            fi
        fi
        # try next available SSID
        if [ -x /usr/local/bin/MyLed.py ]
        then
            /usr/local/bin/MyLed.py --led D6 --light ON
        fi
    done
    return 1
}

echo "<clear>network connect:" | /bin/nc -w 2 localhost \$D_ADDR
if ! INTERNET eth0	# try wired internet line
then
    if ! INTERNET wlan0  # try WiFi connectivity
    then
        if ! WiFiClient
	then
	    echo "No INTERNET"  | /bin/nc -w 2 localhost \$D_ADDR
	fi
    fi
fi
if ! WiFiAP uap0 192.168.2
then
    echo "Start WiFi AP failed" | /bin/nc -w 2 localhost \$D_ADDR
fi
EOF
    sudo cp /tmp/hostap$$ /usr/local/etc/start_wifi_AP
    sudo chmod +x /usr/local/etc/start_wifi_AP
    /bin/rm -f /tmp/hostap$$
    sudo sh -c /usr/local/etc/start_wifi_AP
    # may need to add YB oled display, or read uap OK
    local YB
    read -t 15 -p "The Oled display is a yellow/blue display (dflt=No)? [Ny]: " YB
    YB=${YB/[Nn]*/}
    local UAP
    read -t 15 -p "WiFi AP to be installed (dflt=No)? [Ny]: " UAP
    UAP=${UAP/[nN]*/}
    AddCrontab "/usr/local/etc/start_wifi_AP ${YB/[yY]*/-y} ${UAP/[yY]*/uap0}" root
}

INSTALLS+=" GPRS"
HELP[GPRS]="Installation of internet access via 3G/GPRS mobile network. Use of Huawei E3531 HPSA + USB dongle"
function GPRSppp() {
    local GSMMODEM=${1:-/dev/serial/by-path/usb-HUAWEI_HUAWEI_Mobile-if00-port0}
    DEPENDS_ON apt ppp
    if [ ! -f /etc/ppp/peers/gprs ]
    then
        if ! grep -q HUAWEI /var/log/syslog
        then
            echo "Make sure Huawei dongle is installed as modem! See documentation." >/dev/stderr
        fi
        echo "Make sure Huawei uses SIM card with code disabled." >/dev/stderr
        echo "Using Huawei gsmmodem as: $SGMMODEM" >/dev/stderr
        sudo cat <<EOF | sudo tee /etc/ppp/peers/gprs
user "ios"
connect "/usr/sbin/chat -v -f /etc/chatscripts/gprs -T em"
$GSMMODEM
noipdefault
defaultroute
replacedefaultroute
hide-password
noauth
persist
usepeerdns
EOF
    fi
    AddChckInternet
    if [ ! -f /etc/network/interfaces.d/gprs ]
    then
        sudo cat <<EOF | sudo tee /etc/network/interfaces.d/gprs
auto gprs
iface gprs inet ppp
    pre-up /etc/network/if-pre-up.d/Check-internet "(eth|wlan)" ppp
    provider gprs
EOF
        if ! grep -q gprs /etc/network/interfaces
        then
            /usr/bin/sudo /bin/sh -c "echo 'source interfaces.d/gprs' >>/etc/network/interfaces"
        fi
    fi
    if [ ! -f /usr/local/bin/gprs ]
    then
        sudo cat <<EOF | sudo tee /usr/local/bin/gprs
#!/bin/bash
# up GPRS internet connectivity only when no internet is available

if ! /bin/ping -q -w 2 -c 2 8.8.8.8
then
    if [ ! -f $GSMMODEM ]
    then
        echo "Unable to find gsmmodem as $GSMMODEM"
        exit 1
    fi
    /sbin/ifup gprs
    # maybe add chek if ppp is really successful
fi
EOF
        sudo chmod +x /usr/local/bin/gprs
    fi
    AddChckInternet
    AddCrontab /usr/local/bin/gprs root
    echo "GPRS will be initiated on no WiFi or Lan. Make sure SIM code is disabled. See gprs.md documentation." >/dev/stderr
}

# install SMS messages
INSTALLS+=" SMS"
HELP[SMS]="Installation of SMS mobile messages support. Need eg Huawei GPRS modem."
function SMS() {
    DEPENDS_ON APT gammu
    local GSMMODEM=${1:-/dev/serial/by-path/usb-HUAWEI_HUAWEI_Mobile-if00-port0}
    if [ ! -f ~/.gammurc ]
    then
       # may also use command gammu-config
       echo "Using ~root/.gammurc GSM modem path: $GSMMODEM" >/dev/stderrr
       cat <<EOF >~/.gammurc
[gammu]
port = $GSMMODEM
connection = at19200
model =
synchronizetime = yes
logfile =
logformat = nothing
use_locking =
gammuloc =
EOF
       sudo cp ~/.gammurc /home/root/.gammurc
       if [ ! -f /dev/gsmmodem ] || ! gammu --identify
       then
           echo "Make sure to install the Huawei dongle in modem mode!" >/dev/stderr
       fi
    fi
}

# make sure Huawei dongle is of type E3531
# change this if it is not (other types were not tested)
UNINSTALLS[GPRS]=" /etc/usb_modeswitch.d/12d1\:1f01 /etc/network/interfaces.d/gprs /etc/ppp/peers/gprs"
function GPRS() {
    DEPENDS_ON APT ppp
    DEPENDS_ON APT usb-modeswitch
    DEPENDS_ON APT usb-modeswitch-data
    echo "PLEASE make sure to INSERT Huawei GPRS dongle!" >/dev/stderr
    sleep 20
    local MP
    MP=$(/usr/bin/lsusb | /bin/grep "Huawei.*HSDPA" | /bin/sed -e 's/.*ID //' -e 's/ .*//')
    if [ -z "$MP" ] || [ 12d1 != "${MP/:*/}" ]
    then
        echo "Did not find Huawei GPRS dongle. INSTALLING default." >/dev/stderr
    elif [ 1f01 != "${MP/*:/}" ]
    then
        echo "Maybe Huawei dongle not inserted as modem. Will use default." >/dev/stderr
    fi
    MP='12d1:1f01'
    if [ ! -f /etc/usb_modeswitch.d/"$MP" ]
    then
        sudo cat <<EOF | sudo tee /etc/usb_modeswitch.d/"$MP"
# Huawei E353 (3.se)

TargetVendor=  0x${MP/*:/}
TargetProduct= 0x${MP/:*/}

MessageContent="55534243123456780000000000000011062000000100000000000000000000"
NoDriverLoading=1
EOF
    fi
    echo "Reboot with dongle attached and check if 'dmesg | grep USB.*GSM' shows modem activated"
    sleep 2
    local GSMMODEM=${1:-/dev/serial/by-path/usb-HUAWEI_HUAWEI_Mobile-if00-port0}
    GPRSppp "$GSMMODEM"
    DEPENDS_ON APT wvdial
    if [ -f /etc/wvdial.conf ] && grep -q 'modem.*ttyUSB' /etc/wvdial.conf
    then
        sudo sed -i "s#/dev/ttyUSB.*#$GSMMODEM#" /etc/wvdial.conf
    fi
}

INSTALLS+=" BUTTON"
HELP[BUTTON]="Installation of script to watch button presses and feedback via connected led. Use GrovePi Adafruit switch/led or DIY button for this."
UNINSTALLS[BUTTON]+=" /usr/local/bin/MyLed.py"
# install button/led/relay handler
function BUTTON(){
    local MYLED=/usr/local/bin/MyLed.py
    if [ -f $MYLED ] && [ -x $MYLED ] ; then return ; fi
    GROVEPI                # depends on govepi
    sudo cp MyLed.py /usr/local/bin/
    sudo chmod +x $MYLED
    cat >/tmp/poweroff$$ <<EOF
#!/bin/bash
# power off switch: press 15 seconds till led light up constantly
# button socket on Grove D5, led socket on Grove D6
SOCKET=\${1:-D5}
LED=\${2:-D6}
MYLED=$MYLED
D_ADDR=2017
if [ ! -x \$MYLED ] ; then exit 0 ; fi
\$MYLED --led \$LED --blink 1,2,1
while /bin/true
do
    "\$MYLED" --led \$LED --light OFF
    TIMING=\$("\$MYLED" --led \$LED --button \$SOCKET)
    TIMING=\$(echo "\$TIMING" | /bin/sed 's/[^0-9]//g')
    if [ -z "\$TIMING" ]
    then
        sleep 5
        continue
    fi
    if [ -n "\${TIMING}" -a "\$TIMING" -gt 20 ]
    then
         echo -e "<clear>POWERED OFF\n   MySense\n                     ..Bye..                     " | /bin/nc -w 2 localhost \$D_ADDR
        "\$MYLED" --led \$LED --blink 0.25,0.25,2 &
        /usr/bin/killall -r ".*MySense.*"
        /sbin/poweroff
    elif [ -n "\${TIMING}" -a "\$TIMING" -gt 10 ]
    then
         echo -e "<clear>REBOOT\n   MySense\n                     ..=|=..                     " | /bin/nc -w 2 localhost \$D_ADDR
        "\$MYLED" --led \$LED --blink 0.25,0.5,2 &
        /usr/bin/killall -r ".*MySense.*"
        /sbin/reboot
    elif [ "\${TIMING}" -gt 5 -a -x /usr/local/etc/start_wifi_AP ]
    then
        echo -e "<clear>WiFi reset\n   WiFi WPA\n   WiFi WPS" | /bin/nc -w 2 localhost \$D_ADDR
        /usr/local/bin/MyLed.py --led \$LED --blink 0.25,1.25,1 &
        /usr/local/etc/start_wifi_AP
    fi
done
EOF
    /usr/bin/sudo /bin/cp /tmp/poweroff$$ /usr/local/bin/poweroff.sh
    /usr/bin/sudo /bin/chmod +x /usr/local/bin/poweroff.sh
    AddCrontab /usr/local/bin/poweroff.sh root
}

HELP[BLUETOOTH]+="Installation of terminal access via BlueTooth."
UNINSTALLS[BLUETOOTH]+=" /usr/local/bin/BlueToothTerminal.sh"
# installs remote access via BlueTooth terminal service
function BLUETOOTH(){
    sudo cat <<EOF | sudo tee /usr/local/bin/BlueToothTerminal.sh
#!/bin/bash -e

# comes from: https://hacks.mozilla.org/2017/02/headless-raspberry-pi-configuration-over-bluetooth/

#Edit the display name of the RaspberryPi so you can distinguish
#your unit from others in the Bluetooth console
#(very useful in a class setting)

if [ ! -f /etc/machine-info ]
then
	echo PRETTY_HOSTNAME=MySense_\$(hostname -s) > /etc/machine-info
fi

# Edit /lib/systemd/system/bluetooth.service to enable BT services
if ! grep -q 'ExecStart=/usr/lib/bluetooth/bluetoothd.*-C' /lib/systemd/system/bluetooth.service
then
	sudo cp /lib/systemd/system/bluetooth.service /lib/systemd/system/bluetooth.service.orig
	sudo sed -i: 's|^Exec.*toothd$| \
ExecStart=/usr/lib/bluetooth/bluetoothd -C \
ExecStartPost=/usr/bin/sdptool add SP \
ExecStartPost=/bin/hciconfig hci0 piscan \
|g' /lib/systemd/system/bluetooth.service
fi

# create /etc/systemd/system/rfcomm.service to enable 
# the Bluetooth serial port from systemctl
if [ ! -f /etc/systemd/system/rfcomm.service ]
then
	sudo cat <<EOFI | sudo tee /etc/systemd/system/rfcomm.service > /dev/null
[Unit]
Description=RFCOMM service
After=bluetooth.service
Requires=bluetooth.service

[Service]
ExecStart=/usr/bin/rfcomm watch hci0 1 getty rfcomm0 115200 vt100 -a pi

[Install]
WantedBy=multi-user.target
EOFI

	# enable the new rfcomm service
	sudo systemctl enable rfcomm

	# start the rfcomm service
	sudo systemctl restart rfcomm
fi
cat <<EOFI >/dev/stderr
On your laptop make sure to have enabled BlueTooth and associate (automayically: security breach).
See which terminal device is Bluetooth connected by 'ls /dev/cu.'.
Open a window and connect: 'screen screen /dev/cu.MySense_\$(hostname -s)-SerialPort 115200'.
EOFI
EOF
    sudo /bin/chmod +x /usr/local/bin/BlueToothTerminal.sh
}

INSTALLS+=" WIFI_HOSTAP"
HELP[WIFI_HOSTAP]="Installation of WiFi Access Point service. Provides access via wifi to the Pi if the WiFi device supports this."
UNINSTALLS[WIFI_HOSTAP]+=' /etc/etc/hostapd/hostapd.conf'
UNINSTALLS[WIFI_HOSTAP]+=' /etc/systemd/system/hostapd.service'
# install hostapd daemon
function WIFI_HOSTAP(){
    local WLAN=${1:-uap0} SSID=MySense PASS=BehoudDeParel HIDE=1
    KeepOriginal \
        /etc/hostapd/hostapd.conf \
        /etc/systemd/system/hostapd.service
    # if [ -f /etc/hostapd/hostapd.conf ]
    # then /usr/bin/sudo /usr/bin/apt-get remove --purge hostapd -y
    # fi
    DEPENDS_ON APT hostapd
    /usr/bin/sudo /bin/systemctl stop hostapd
    # /usr/bin/sudo /bin/systemctl enable hostapd
    echo "wifi Access Point needs SSID (dflt ${SSID}) and" 1>&2
    echo "WPA password (dflt ${PASS:-acacadabra}):" 1>&2
    read -t 15 -p "wifi AP SSID (dflt ${SSID:-MySenseIOS}): " SSID
    read -t 15 -p "wifi AP WPA (dflt ${PASS:-acacadabra}): " PASS
    read -t 15 -p "Need to hide the SSID? [Y|n]: " HIDE
    if [ -n "${HIDE/[Yy]/}" ] ; then HIDE=0 ; else HIDE=1 ; fi
    KeepOriginal /etc/systemd/system/hostapd.service
    /bin/cat >/tmp/hostap$$ <<EOF
[Unit]
Description=Hostapd IEEE 802.11 Access Point
After=sys-subsystem-net-devices-${WLAN}.device
BindsTo=sys-subsystem-net-devices-${WLAN}.device
[Service]
Type=forking
EnvironmentFile=-/etc/default/hostapd
PIDFile=/var/run/hostapd.pid
ExecStart=/usr/sbin/hostapd -B /etc/hostapd/hostapd.conf -P /var/run/hostapd.pid
[Install]
WantedBy=multi-user.target
EOF
    /usr/bin/sudo /bin/mv /tmp/hostap$$ /etc/systemd/system/hostapd.service
    /bin/cat >/tmp/hostap$$ <<EOF
interface=${WLAN:-uap0}
ctrl_interface=/var/run/hostapd
ctrl_interface_group=0
beacon_int=100
hw_mode=g
channel=11
auth_algs=1
wpa=2
wpa_key_mgmt=WPA-PSK
wpa_pairwise=CCMP
rsn_pairwise=CCMP
macaddr_acl=0
ssid=${SSID:-MySense}
wpa_passphrase=${PASS:-acacadabra}
ignore_broadcast_ssid=${HIDE:-0}
country_code=NL
EOF
    /usr/bin/sudo /bin/mv /tmp/hostap$$ /etc/hostapd/hostapd.conf
}

INSTALLS+=" NEW_SSID"
HELP[NEW_SSID]="Installation of new WiFi SSID of WiFi Access Point at installation time (now)."
UNINSTALLS[NEW_SSID]+=' /etc/wpa_supplicant/wpa_supplicant.conf'
# add wifi ssid/WPA password to enable $WIFI for internet access via wifi
function NEW_SSID(){
    GetInterfaces
    local SSID PASS1=0 PASS2=1 WLAN=${1:-wlan}
    KeepOriginal /etc/wpa_supplicant/wpa_supplicant.conf
    SSID=$(/usr/bin/sudo /bin/grep ssid /etc/wpa_supplicant/wpa_supplicant.conf | /bin/sed -e 's/.*ssid=//' -e 's/"//g')
    if [ -n "$SSID" ]
    then
        echo "SSID's already defined in /etc/wpa_supplicant/wpa_supplicant.conf: $SSID"
    fi
    WLAN=$(/sbin/ifconfig | /usr/bin/awk "/$WLAN/{ print \$1; exit(0); }")
    if [ -z "$WLAN" ]
    then
        WLAN=$WIFI
        if ! /usr/bin/sudo /sbin/ip link set dev ${WLAN} up || ! \
	    /usr/bin/sudo wpa_supplicant -B -c/etc/wpa_supplicant/wpa_supplicant.conf -i"$WLAN" >/dev/null
        then
            echo "ERROR: cannot enable wifi $WLAN"
            return 1
        fi
    fi
    echo "Wifi access points near by:"
    /usr/bin/sudo /sbin/iw "$WLAN" scan | /bin/grep -e SSID: -e signal:
    echo -e "Enter SSID and password for accessing the internet wifi router.\nJust return to stop." 1>&2
    read -p "wifi SSID: " SSID
    if [ -z "$SSID" ] ; then return 1 ; fi
    while [ "$PASS1" != "$PASS2" ]
    do
        read -p "wifi password: " PASS1
        read -p "retype passwd: " PASS2
    done
    /usr/bin/sudo /bin/cp /etc/wpa_supplicant/wpa_supplicant.conf /tmp/wpa$$
    /usr/bin/sudo /bin/chown $USER /tmp/wpa$$
    if /bin/grep -q "ssid=\"*$SSID\"*" /tmp/wpa$$
    then
        ed - /tmp/wpa$$ <<EOF
/ssid="*$SSID"*/-1,/}/d
w
q
EOF
    fi
    /bin/cat >>/tmp/wpa$$ <<EOF
network={
    ssid="$SSID"
    psk="$PASS1"
    proto=RSN
    key_mgmt=WPA-PSK
    pairwise=CCMP
    auth_alg=OPEN
}
EOF
    /usr/bin/sudo /bin/cp /tmp/wpa$$ /etc/wpa_supplicant/wpa_supplicant.conf
    /bin/rm -f /tmp/wpa$$
    /usr/bin/sudo pkill -HUP wpa_supplicant    # try the new ssid/passwd
    /usr/bin/sudo /sbin/wpa_cli reconnect
    sleep 5
    if /usr/bin/sudo /sbin/wpa_cli status | /bin/grep -q "ssid=$SSID"
    then
        break
    else
        echo "FAILURE: cannot connect to $SSID."
        read  -p "Try another password? [Y|n] " PASS1
        if [ -z "${PASS1/[Yy]/}" ] ; then continue ; fi
        read  -p "Try another SSID? [y|N] " PASS1
        if [ -z "${PASS1/[Nn]/}" ] ; then return ; fi
        New_SSID ${WLAN}
        return
    fi
}
#New_SSID

if [ -n "$1" ] && [ "$1" = help -o x"$1" = x--help -o x"$1"  = x-h ]
then
   echo "Usage:
INSTALLS.sh will make the Pi ready for installing MySense.py by downloading and installing
all Python dependencies en services for MySense.py.
For the OS changes are available: $INSTALLS
For plugins are available: $PLUGINS
For extra\'s: $EXTRA
Calling INSTALL.sh without arguments will install all.
Calling INSTALL.sh USER DISPLAY WATCHDOG INTERNET WIFI WEBMIN
will install all OS modules to operate Pi via LAN, WLAN and remote webmin access.
"
    exit 0
fi

MODS=$@
if [ -z "$MODS" ]
then
    MODS="$INSTALLS $PLUGINS $EXTRA"
fi

# try to get latest updates for Debian distr
if ASK UPDATE "Update Debian OS and utilities" ; then UPDATE ; fi

for M in $MODS
do
    # TO BE ADDED: check config if the plugin is really used
    case M in
    mysql|MySQL) M=MYSQL
    ;;
    INFLUX*) M=INFLUX
    ;;
    esac
    if echo "$INSTALLS $PLUGINS $EXTRA" | grep -q -i "$M"
    then
        if echo "$INSTALLS" | /bin/grep -q "$M"
        then
            echo "System configuration for ${M^^}"
        elif echo "$PLUGINS" | /bin/grep -q "$M"
        then 
            echo "Plugin My${M^^}.py looking for missing modules/packages:" 
        else
            echo "For extra's not really needed  ${M^^} services:" 
        fi
        if ASK ${M^^}
        then
            if ! ${M^^}
            then
                echo "FAILED to complete needed modules/packages for My${M^^}.py." 1>&2
            fi
        else
            echo "Installation of ${M^^} skipped."
        fi
    else
        echo "Unknow plugin for $M. Skipped." 1>&2
    fi
done
