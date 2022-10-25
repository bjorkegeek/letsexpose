#!/bin/sh

letsexpose_tool /letsexpose-config/config.yaml update-nginx

nginx -s reload
