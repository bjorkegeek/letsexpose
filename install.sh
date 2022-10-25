#!/bin/bash

confirm() {
  read -p 'Press ◀─┘ to continue, Ctrl-C to abort...'
}

check_config_file() {
  if [ ! -e config/config.yaml ]
  then
    echo "ERROR: Could not find config/config.yaml"
    echo "Make a copy of config/config.sample.yaml and edit it to your needs"
    exit 2
  fi
}

install_service_systemd() {
  DOCKER=`which docker`
  if [ ! -x "$DOCKER" ]
  then
    echo "ERROR: Could not find executable docker command"
    exit 2
  fi
  SERVICEFILE=/etc/systemd/system/letsexpose.service
  echo ""
  echo "Will install letsexpose service in $SERVICEFILE"
  echo "enable it at boot and start it now"
  confirm
  cat >$SERVICEFILE <<EOF
[Unit]
Description=letsexpose server
PartOf=docker.service
After=docker.service

[Service]
Type=oneshot
RemainAfterExit=true
WorkingDirectory=$PWD
ExecStart=$DOCKER compose up -d --remove-orphans
ExecStop=$DOCKER compose down
ExecStopPost=$DOCKER compose rm --force
ExecReload=$DOCKER compose exec letsexpose-nginx /reload.sh
[Install]
WantedBy=multi-user.target
EOF
  systemctl daemon-reload
  systemctl enable letsexpose.service --now
}


install_service() {
  if [ -d /etc/systemd/system ]
  then
    install_service_systemd
  else
    echo "ERROR: Could not find a supported init system"
    exit 2    
  fi
}

initialize() {
  echo ""
  echo "Will perform initial request for certbot certs"
  confirm
  docker compose run --rm letsexpose-certbot letsexpose_tool /letsexpose-config/config.yaml certbot-init
}

reload() {
  echo ""
  echo "Will reload to activate https servers"
  confirm
  docker compose exec letsexpose-nginx /reload.sh
}

install_cron_daily() {
  echo ""
  echo "Will install renewal script in /etc/cron.daily"
  confirm
  DOCKER=`which docker`
  cat > /etc/cron.daily/letsexpose <<EOF
#!/bin/sh
cd "$PWD"
$DOCKER compose run --rm letsexpose-certbot certbot renew
$DOCKER compose exec letsexpose-nginx /reload.sh
EOF
  chmod a+x /etc/cron.daily/letsexpose
}

install_cron() {
  if [ -d /etc/cron.daily ]
  then
    install_cron_daily
  else
    echo "ERROR: Could not find a supported way of installing daily cron jobs"
    exit 2    
  fi
}


cd `dirname $0`

check_config_file

echo "------------------------------------------------------------------"
echo ""
echo "This script will install letsexpose to run from"
echo -n "  "
pwd
echo ""
echo "Before every step, you will be requested to confirm."
confirm

install_service
initialize
reload
install_cron

echo "All done!"

