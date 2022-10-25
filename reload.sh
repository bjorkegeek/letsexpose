#!/bin/bash

cd `dirname $0`

docker compose exec letsexpose-nginx /reload.sh
